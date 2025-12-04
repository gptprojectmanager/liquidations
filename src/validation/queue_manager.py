"""
Validation queue manager with FIFO processing.

Manages validation run queue with size limits and overflow handling.
"""

import threading
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Deque, Optional

from src.validation.logger import logger


class QueueStatus(str, Enum):
    """Validation queue item status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    """Validation queue item."""

    queue_id: str
    run_id: str
    model_name: str
    triggered_by: str
    status: QueueStatus
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ValidationQueue:
    """
    FIFO queue for validation runs.

    Manages validation run queue with:
    - FIFO processing order
    - Maximum queue size limit
    - Concurrent run prevention
    - Queue overflow handling
    """

    def __init__(self, max_size: int = 10):
        """
        Initialize validation queue.

        Args:
            max_size: Maximum queue size (default: 10)
        """
        self.max_size = max_size
        self._queue: Deque[QueueItem] = deque(maxlen=max_size)
        self._processing: Optional[QueueItem] = None
        self._lock = threading.Lock()
        self._history: Deque[QueueItem] = deque(maxlen=100)  # Keep last 100

        logger.info(f"ValidationQueue initialized with max_size={max_size}")

    def enqueue(
        self,
        run_id: str,
        model_name: str,
        triggered_by: str = "api",
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Add validation run to queue.

        Args:
            run_id: Validation run ID
            model_name: Model to validate
            triggered_by: User or system identifier

        Returns:
            Tuple of (success, queue_id, error_message)
        """
        with self._lock:
            # Check if queue is full
            if len(self._queue) >= self.max_size:
                logger.warning(
                    f"Queue full ({len(self._queue)}/{self.max_size}) - rejecting run {run_id}"
                )
                return False, None, f"Queue full ({self.max_size} items)"

            # Check if already queued or processing
            if self._is_duplicate(run_id):
                logger.warning(f"Run {run_id} already queued or processing")
                return False, None, "Run already queued or in progress"

            # Create queue item
            queue_id = str(uuid.uuid4())
            item = QueueItem(
                queue_id=queue_id,
                run_id=run_id,
                model_name=model_name,
                triggered_by=triggered_by,
                status=QueueStatus.QUEUED,
                queued_at=datetime.utcnow(),
            )

            # Add to queue
            self._queue.append(item)

            logger.info(
                f"Queued validation run: queue_id={queue_id}, run_id={run_id}, "
                f"model={model_name}, position={len(self._queue)}"
            )

            return True, queue_id, None

    def dequeue(self) -> Optional[QueueItem]:
        """
        Remove and return next item from queue (FIFO).

        Returns:
            QueueItem if available, None if queue empty or processing
        """
        with self._lock:
            # Don't dequeue if already processing
            if self._processing is not None:
                logger.debug("Cannot dequeue - validation already in progress")
                return None

            # Check if queue empty
            if not self._queue:
                logger.debug("Queue is empty")
                return None

            # Get next item (FIFO)
            item = self._queue.popleft()
            item.status = QueueStatus.PROCESSING
            item.started_at = datetime.utcnow()

            # Mark as processing
            self._processing = item

            logger.info(
                f"Dequeued validation run: queue_id={item.queue_id}, "
                f"run_id={item.run_id}, remaining={len(self._queue)}"
            )

            return item

    def complete(
        self,
        queue_id: str,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Mark queue item as completed or failed.

        Args:
            queue_id: Queue item ID
            success: Whether validation succeeded
            error_message: Error message if failed

        Returns:
            True if item was found and updated
        """
        with self._lock:
            # Check if this is the processing item
            if not self._processing or self._processing.queue_id != queue_id:
                logger.warning(
                    f"Cannot complete queue_id={queue_id} - "
                    f"not currently processing (processing={self._processing})"
                )
                return False

            # Update status
            self._processing.status = QueueStatus.COMPLETED if success else QueueStatus.FAILED
            self._processing.completed_at = datetime.utcnow()
            if error_message:
                self._processing.error_message = error_message

            # Move to history
            self._history.append(self._processing)

            logger.info(
                f"Completed validation run: queue_id={queue_id}, "
                f"success={success}, duration={(self._processing.completed_at - self._processing.started_at).total_seconds():.1f}s"
            )

            # Clear processing
            self._processing = None

            return True

    def cancel(self, queue_id: str) -> bool:
        """
        Cancel queued validation run.

        Args:
            queue_id: Queue item ID to cancel

        Returns:
            True if item was found and cancelled
        """
        with self._lock:
            # Check if it's the processing item
            if self._processing and self._processing.queue_id == queue_id:
                logger.warning(f"Cannot cancel queue_id={queue_id} - already processing")
                return False

            # Find and remove from queue
            for i, item in enumerate(self._queue):
                if item.queue_id == queue_id:
                    item.status = QueueStatus.CANCELLED
                    item.completed_at = datetime.utcnow()

                    # Remove from queue and add to history
                    del self._queue[i]
                    self._history.append(item)

                    logger.info(f"Cancelled validation run: queue_id={queue_id}")
                    return True

            logger.warning(f"Queue item not found: queue_id={queue_id}")
            return False

    def get_status(self, queue_id: str) -> Optional[QueueItem]:
        """
        Get status of queue item.

        Args:
            queue_id: Queue item ID

        Returns:
            QueueItem if found, None otherwise
        """
        with self._lock:
            # Check if processing
            if self._processing and self._processing.queue_id == queue_id:
                return self._processing

            # Check queue
            for item in self._queue:
                if item.queue_id == queue_id:
                    return item

            # Check history
            for item in self._history:
                if item.queue_id == queue_id:
                    return item

            return None

    def size(self) -> int:
        """
        Get current queue size.

        Returns:
            Number of items in queue
        """
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """
        Check if queue is empty.

        Returns:
            True if queue has no items
        """
        with self._lock:
            return len(self._queue) == 0

    def is_processing(self) -> bool:
        """
        Check if an item is currently being processed.

        Returns:
            True if an item is being processed
        """
        with self._lock:
            return self._processing is not None

    def fail(self, queue_id: str, error_message: str = "") -> bool:
        """
        Mark processing item as failed.

        Args:
            queue_id: Queue item ID to fail
            error_message: Optional error message

        Returns:
            True if item was found and marked as failed
        """
        with self._lock:
            if self._processing and self._processing.queue_id == queue_id:
                self._processing.status = QueueStatus.FAILED
                self._processing.completed_at = datetime.utcnow()
                self._processing.error_message = error_message

                # Calculate duration
                duration = (
                    self._processing.completed_at - self._processing.queued_at
                ).total_seconds()

                logger.error(
                    f"Failed validation run: queue_id={queue_id}, "
                    f"error={error_message}, duration={duration:.1f}s"
                )

                # Move to history
                self._history.append(self._processing)
                self._processing = None

                return True

            return False

    def get_stats(self) -> dict:
        """
        Get queue statistics.

        Returns:
            Dict with queue statistics
        """
        with self._lock:
            completed_items = [
                item for item in self._history if item.status == QueueStatus.COMPLETED
            ]
            failed_items = [item for item in self._history if item.status == QueueStatus.FAILED]
            cancelled_items = [
                item for item in self._history if item.status == QueueStatus.CANCELLED
            ]

            return {
                "queue_size": len(self._queue),
                "queued_count": len(self._queue),
                "max_size": self.max_size,
                "processing_count": 1 if self._processing is not None else 0,
                "completed_count": len(completed_items),
                "failed_count": len(failed_items),
                "cancelled_count": len(cancelled_items),
                "history_size": len(self._history),
            }

    def get_queue_info(self) -> dict:
        """
        Get current queue information.

        Returns:
            Dict with queue statistics
        """
        with self._lock:
            queued_items = list(self._queue)
            processing_item = self._processing

            return {
                "queue_size": len(queued_items),
                "max_size": self.max_size,
                "is_full": len(queued_items) >= self.max_size,
                "processing": processing_item.run_id if processing_item else None,
                "queued_runs": [
                    {
                        "queue_id": item.queue_id,
                        "run_id": item.run_id,
                        "model_name": item.model_name,
                        "queued_at": item.queued_at.isoformat(),
                        "position": i + 1,
                    }
                    for i, item in enumerate(queued_items)
                ],
            }

    def clear(self) -> int:
        """
        Clear all queued items (not processing).

        Returns:
            Number of items cleared
        """
        with self._lock:
            count = len(self._queue)

            # Move all to history as cancelled
            while self._queue:
                item = self._queue.popleft()
                item.status = QueueStatus.CANCELLED
                item.completed_at = datetime.utcnow()
                self._history.append(item)

            logger.warning(f"Cleared {count} items from queue")
            return count

    def _is_duplicate(self, run_id: str) -> bool:
        """
        Check if run_id is already queued or processing.

        Args:
            run_id: Validation run ID

        Returns:
            True if duplicate found
        """
        # Check processing
        if self._processing and self._processing.run_id == run_id:
            return True

        # Check queue
        for item in self._queue:
            if item.run_id == run_id:
                return True

        return False


# Global queue instance
_global_queue: Optional[ValidationQueue] = None
_queue_lock = threading.Lock()


def get_validation_queue() -> ValidationQueue:
    """
    Get global validation queue instance (singleton).

    Returns:
        ValidationQueue instance
    """
    global _global_queue

    if _global_queue is None:
        with _queue_lock:
            if _global_queue is None:
                _global_queue = ValidationQueue(max_size=10)

    return _global_queue
