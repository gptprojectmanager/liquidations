"""
Queue configuration and overflow handling.

Defines queue size limits and overflow policies.
"""

from enum import Enum

from src.validation.logger import logger


class OverflowPolicy(str, Enum):
    """Policy for handling queue overflow."""

    REJECT = "reject"  # Reject new items when queue full
    DROP_OLDEST = "drop_oldest"  # Drop oldest queued item
    DROP_NEWEST = "drop_newest"  # Drop newest (incoming) item


class QueueConfig:
    """
    Configuration for validation queue.

    Defines queue limits and overflow handling behavior.
    """

    # Queue size limits
    DEFAULT_MAX_SIZE = 10
    MIN_SIZE = 1
    MAX_SIZE = 50

    # Overflow handling
    DEFAULT_OVERFLOW_POLICY = OverflowPolicy.REJECT

    # Processing limits
    MAX_CONCURRENT_RUNS = 1  # Only one validation at a time
    MAX_RETRY_ATTEMPTS = 3

    # Timeouts
    QUEUE_TIMEOUT_SECONDS = 3600  # 1 hour max in queue
    PROCESSING_TIMEOUT_SECONDS = 600  # 10 minutes max processing

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        overflow_policy: OverflowPolicy = DEFAULT_OVERFLOW_POLICY,
    ):
        """
        Initialize queue configuration.

        Args:
            max_size: Maximum queue size (1-50)
            overflow_policy: Policy for handling queue overflow
        """
        # Validate and set max_size
        if max_size < self.MIN_SIZE or max_size > self.MAX_SIZE:
            logger.warning(f"Invalid max_size {max_size}, using default {self.DEFAULT_MAX_SIZE}")
            max_size = self.DEFAULT_MAX_SIZE

        self.max_size = max_size
        self.overflow_policy = overflow_policy

        logger.info(
            f"QueueConfig initialized: max_size={max_size}, overflow_policy={overflow_policy.value}"
        )

    def should_accept(self, current_size: int) -> bool:
        """
        Check if queue should accept new item.

        Args:
            current_size: Current queue size

        Returns:
            True if new item can be accepted
        """
        if current_size < self.max_size:
            return True

        # Queue is full - check overflow policy
        if self.overflow_policy == OverflowPolicy.REJECT:
            logger.warning(f"Queue full ({current_size}/{self.max_size}) - rejecting")
            return False

        # Other policies allow acceptance (with overflow handling)
        return True

    def handle_overflow(self, queue_items: list) -> list:
        """
        Handle queue overflow based on policy.

        Args:
            queue_items: Current queue items

        Returns:
            Updated queue items after overflow handling
        """
        if len(queue_items) <= self.max_size:
            # No overflow
            return queue_items

        if self.overflow_policy == OverflowPolicy.REJECT:
            # Should not reach here - reject happens before enqueue
            logger.error("Overflow handling called with REJECT policy")
            return queue_items[: self.max_size]

        elif self.overflow_policy == OverflowPolicy.DROP_OLDEST:
            # Drop oldest items (from front)
            dropped = len(queue_items) - self.max_size
            logger.warning(
                f"Queue overflow - dropping {dropped} oldest items (policy: DROP_OLDEST)"
            )
            return queue_items[dropped:]

        elif self.overflow_policy == OverflowPolicy.DROP_NEWEST:
            # Keep oldest items (drop from end)
            dropped = len(queue_items) - self.max_size
            logger.warning(
                f"Queue overflow - dropping {dropped} newest items (policy: DROP_NEWEST)"
            )
            return queue_items[: self.max_size]

        else:
            logger.error(f"Unknown overflow policy: {self.overflow_policy}")
            return queue_items[: self.max_size]

    def is_timeout(self, queued_seconds: float) -> bool:
        """
        Check if item has exceeded queue timeout.

        Args:
            queued_seconds: Seconds item has been in queue

        Returns:
            True if timeout exceeded
        """
        return queued_seconds > self.QUEUE_TIMEOUT_SECONDS

    def is_processing_timeout(self, processing_seconds: float) -> bool:
        """
        Check if item has exceeded processing timeout.

        Args:
            processing_seconds: Seconds item has been processing

        Returns:
            True if timeout exceeded
        """
        return processing_seconds > self.PROCESSING_TIMEOUT_SECONDS


# Global configuration instance
_global_config: QueueConfig = QueueConfig()


def get_queue_config() -> QueueConfig:
    """
    Get global queue configuration.

    Returns:
        QueueConfig instance
    """
    return _global_config


def set_queue_config(config: QueueConfig) -> None:
    """
    Set global queue configuration.

    Args:
        config: QueueConfig instance
    """
    global _global_config
    _global_config = config
    logger.info("Global queue configuration updated")
