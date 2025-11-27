"""
Concurrency lock for validation runs.

Prevents multiple validation runs from executing simultaneously.
"""

import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from src.validation.logger import logger


class ConcurrencyLock:
    """
    Lock to prevent concurrent validation runs.

    Ensures only one validation run executes at a time,
    preventing resource conflicts and data corruption.
    """

    def __init__(self, timeout_seconds: int = 600):
        """
        Initialize concurrency lock.

        Args:
            timeout_seconds: Maximum lock hold time (default: 10 minutes)
        """
        self._lock = threading.Lock()
        self._holder: Optional[str] = None  # run_id of lock holder
        self._acquired_at: Optional[datetime] = None
        self.timeout_seconds = timeout_seconds

        logger.info(f"ConcurrencyLock initialized with timeout={timeout_seconds}s")

    def acquire(self, run_id: str, blocking: bool = True, timeout: float = -1) -> bool:
        """
        Acquire lock for validation run.

        Args:
            run_id: Validation run ID
            blocking: Whether to block waiting for lock
            timeout: Timeout in seconds (-1 for infinite)

        Returns:
            True if lock acquired, False otherwise
        """
        acquired = self._lock.acquire(blocking=blocking, timeout=timeout if timeout >= 0 else None)

        if acquired:
            self._holder = run_id
            self._acquired_at = datetime.utcnow()

            logger.info(f"Lock acquired by run_id={run_id}")
            return True
        else:
            logger.warning(f"Lock acquisition failed for run_id={run_id} (holder={self._holder})")
            return False

    def release(self, run_id: str) -> bool:
        """
        Release lock for validation run.

        Args:
            run_id: Validation run ID

        Returns:
            True if lock released, False if not holder
        """
        # Verify caller is lock holder
        if self._holder != run_id:
            logger.error(
                f"Lock release failed: run_id={run_id} is not holder (holder={self._holder})"
            )
            return False

        try:
            # Calculate hold duration
            if self._acquired_at:
                hold_duration = (datetime.utcnow() - self._acquired_at).total_seconds()
                logger.info(f"Lock released by run_id={run_id} (held for {hold_duration:.1f}s)")

            # Clear holder
            self._holder = None
            self._acquired_at = None

            # Release lock
            self._lock.release()

            return True

        except Exception as e:
            logger.error(f"Error releasing lock: {e}", exc_info=True)
            return False

    def force_release(self) -> bool:
        """
        Force release lock (emergency use only).

        Returns:
            True if lock was held and released
        """
        if not self._lock.locked():
            logger.warning("Force release called but lock not held")
            return False

        try:
            holder = self._holder
            logger.warning(f"Force releasing lock (previous holder={holder})")

            self._holder = None
            self._acquired_at = None
            self._lock.release()

            return True

        except Exception as e:
            logger.error(f"Error force releasing lock: {e}", exc_info=True)
            return False

    def is_locked(self) -> bool:
        """
        Check if lock is currently held.

        Returns:
            True if lock is held
        """
        return self._lock.locked()

    def get_holder(self) -> Optional[str]:
        """
        Get current lock holder.

        Returns:
            run_id of holder, or None if not locked
        """
        return self._holder

    def check_timeout(self) -> bool:
        """
        Check if lock has been held beyond timeout.

        Returns:
            True if lock is timed out
        """
        if not self._acquired_at:
            return False

        hold_duration = (datetime.utcnow() - self._acquired_at).total_seconds()

        if hold_duration > self.timeout_seconds:
            logger.error(
                f"Lock timeout detected: holder={self._holder}, "
                f"duration={hold_duration:.1f}s (timeout={self.timeout_seconds}s)"
            )
            return True

        return False

    def get_lock_info(self) -> dict:
        """
        Get lock status information.

        Returns:
            Dict with lock details
        """
        if not self._lock.locked():
            return {
                "locked": False,
                "holder": None,
                "acquired_at": None,
                "hold_duration": None,
            }

        hold_duration = None
        if self._acquired_at:
            hold_duration = (datetime.utcnow() - self._acquired_at).total_seconds()

        return {
            "locked": True,
            "holder": self._holder,
            "acquired_at": self._acquired_at.isoformat() if self._acquired_at else None,
            "hold_duration": hold_duration,
            "is_timeout": self.check_timeout(),
        }

    @contextmanager
    def lock_context(self, run_id: str, timeout: float = -1):
        """
        Context manager for automatic lock acquisition/release.

        Args:
            run_id: Validation run ID
            timeout: Acquisition timeout in seconds

        Yields:
            True if lock acquired

        Example:
            with lock.lock_context("run-123") as acquired:
                if acquired:
                    # Do validation work
                    pass
        """
        acquired = self.acquire(run_id, blocking=True, timeout=timeout)

        try:
            yield acquired
        finally:
            if acquired:
                self.release(run_id)


# Global lock instance
_global_lock: Optional[ConcurrencyLock] = None
_lock_init = threading.Lock()


def get_concurrency_lock() -> ConcurrencyLock:
    """
    Get global concurrency lock instance (singleton).

    Returns:
        ConcurrencyLock instance
    """
    global _global_lock

    if _global_lock is None:
        with _lock_init:
            if _global_lock is None:
                _global_lock = ConcurrencyLock(timeout_seconds=600)

    return _global_lock
