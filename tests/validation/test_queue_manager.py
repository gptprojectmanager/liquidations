"""
Tests for queue_manager.py - FIFO queue management.

Tests cover:
- FIFO ordering
- Queue size limits
- Duplicate detection
- Thread safety
- Queue statistics
"""

import threading
import time
from datetime import datetime

from src.validation.queue_manager import (
    QueueItem,
    QueueStatus,
    ValidationQueue,
    get_validation_queue,
)


class TestValidationQueue:
    """Test ValidationQueue functionality."""

    def test_initialization_with_default_size(self):
        """Queue should initialize with default max size."""
        # Act
        queue = ValidationQueue()

        # Assert
        assert queue.max_size == 10
        assert queue.size() == 0
        assert queue.is_empty() is True

    def test_initialization_with_custom_size(self):
        """Queue should accept custom max size."""
        # Act
        queue = ValidationQueue(max_size=5)

        # Assert
        assert queue.max_size == 5

    def test_enqueue_adds_item_to_queue(self):
        """Enqueue should add item to queue successfully."""
        # Arrange
        queue = ValidationQueue()

        # Act
        success, queue_id, error = queue.enqueue(
            run_id="run-1",
            model_name="test_model",
            triggered_by="user@test.com",
        )

        # Assert
        assert success is True
        assert queue_id is not None
        assert error is None
        assert queue.size() == 1
        assert queue.is_empty() is False

    def test_enqueue_rejects_when_queue_full(self):
        """Enqueue should reject items when queue is full."""
        # Arrange
        queue = ValidationQueue(max_size=2)

        # Fill queue
        queue.enqueue("run-1", "model1", "user")
        queue.enqueue("run-2", "model2", "user")

        # Act
        success, queue_id, error = queue.enqueue("run-3", "model3", "user")

        # Assert
        assert success is False
        assert queue_id is None
        assert "full" in error.lower()
        assert queue.size() == 2

    def test_enqueue_rejects_duplicate_run_id(self):
        """Enqueue should reject duplicate run IDs."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model", "user")

        # Act
        success, queue_id, error = queue.enqueue("run-1", "model", "user")

        # Assert
        assert success is False
        assert "duplicate" in error.lower() or "already" in error.lower()

    def test_dequeue_returns_oldest_item_first(self):
        """Dequeue should return items in FIFO order."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model1", "user")
        time.sleep(0.01)  # Ensure timestamp difference
        queue.enqueue("run-2", "model2", "user")

        # Act
        item1 = queue.dequeue()
        item2 = queue.dequeue()

        # Assert
        assert item1 is not None
        assert item1.run_id == "run-1"
        assert item2 is not None
        assert item2.run_id == "run-2"

    def test_dequeue_returns_none_when_empty(self):
        """Dequeue should return None when queue is empty."""
        # Arrange
        queue = ValidationQueue()

        # Act
        item = queue.dequeue()

        # Assert
        assert item is None

    def test_dequeue_blocks_when_item_in_progress(self):
        """Dequeue should return None when an item is already processing."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model1", "user")
        queue.enqueue("run-2", "model2", "user")

        # Dequeue first item (now processing)
        item1 = queue.dequeue()

        # Act
        item2 = queue.dequeue()  # Should return None since item1 is still processing

        # Assert
        assert item1 is not None
        assert item2 is None  # Cannot dequeue while processing

    def test_complete_marks_item_as_completed(self):
        """Complete should mark processing item as completed."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model", "user")
        item = queue.dequeue()

        # Act
        result = queue.complete(item.queue_id)

        # Assert
        assert result is True
        assert queue.is_processing() is False

    def test_complete_allows_next_dequeue(self):
        """Complete should allow next item to be dequeued."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model1", "user")
        queue.enqueue("run-2", "model2", "user")

        item1 = queue.dequeue()
        queue.complete(item1.queue_id)

        # Act
        item2 = queue.dequeue()

        # Assert
        assert item2 is not None
        assert item2.run_id == "run-2"

    def test_fail_marks_item_as_failed(self):
        """Fail should mark processing item as failed."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model", "user")
        item = queue.dequeue()

        # Act
        result = queue.fail(item.queue_id, "Test error")

        # Assert
        assert result is True
        assert queue.is_processing() is False

    def test_get_stats_returns_accurate_statistics(self):
        """get_stats should return current queue statistics."""
        # Arrange
        queue = ValidationQueue(max_size=5)
        queue.enqueue("run-1", "model1", "user")
        queue.enqueue("run-2", "model2", "user")

        # Act
        stats = queue.get_stats()

        # Assert
        assert stats["queued_count"] == 2
        assert stats["max_size"] == 5
        assert stats["processing_count"] == 0

    def test_clear_removes_all_items(self):
        """Clear should remove all queued items."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model1", "user")
        queue.enqueue("run-2", "model2", "user")

        # Act
        cleared = queue.clear()

        # Assert
        assert cleared == 2
        assert queue.size() == 0
        assert queue.is_empty() is True

    def test_thread_safety_with_concurrent_enqueues(self):
        """Queue should handle concurrent enqueues safely."""
        # Arrange
        queue = ValidationQueue(max_size=100)
        results = []

        def enqueue_item(run_id):
            success, _, _ = queue.enqueue(run_id, "model", "user")
            results.append(success)

        # Act
        threads = [threading.Thread(target=enqueue_item, args=(f"run-{i}",)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert
        assert len([r for r in results if r]) == 50  # All successful
        assert queue.size() == 50

    def test_get_validation_queue_returns_singleton(self):
        """get_validation_queue should return same instance."""
        # Act
        queue1 = get_validation_queue()
        queue2 = get_validation_queue()

        # Assert
        assert queue1 is queue2

    def test_queue_item_has_correct_initial_status(self):
        """QueueItem should have QUEUED status initially."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue("run-1", "model", "user")

        # Act
        stats = queue.get_stats()

        # Assert
        assert stats["queued_count"] == 1
        assert stats["processing_count"] == 0

    def test_queue_preserves_metadata(self):
        """Queue should preserve item metadata."""
        # Arrange
        queue = ValidationQueue()
        queue.enqueue(
            run_id="run-1",
            model_name="test_model_v2",
            triggered_by="admin@test.com",
        )

        # Act
        item = queue.dequeue()

        # Assert
        assert item.run_id == "run-1"
        assert item.model_name == "test_model_v2"
        assert item.triggered_by == "admin@test.com"


class TestQueueItem:
    """Test QueueItem dataclass."""

    def test_queue_item_creation(self):
        """QueueItem should be created with all fields."""
        # Act
        item = QueueItem(
            queue_id="q-123",
            run_id="run-1",
            model_name="test_model",
            triggered_by="user@test.com",
            status=QueueStatus.QUEUED,
            queued_at=datetime.utcnow(),
        )

        # Assert
        assert item.queue_id == "q-123"
        assert item.run_id == "run-1"
        assert item.status == QueueStatus.QUEUED

    def test_queue_status_enum_values(self):
        """QueueStatus should have expected values."""
        # Assert
        assert QueueStatus.QUEUED.value == "queued"
        assert QueueStatus.PROCESSING.value == "processing"
        assert QueueStatus.COMPLETED.value == "completed"
        assert QueueStatus.FAILED.value == "failed"
