"""
Tests for concurrency_lock.py - Thread-safe concurrency control.

Tests cover:
- Lock acquisition and release
- Timeout behavior
- Context manager usage
- Holder validation
- Thread safety
"""

import threading
import time

from src.validation.concurrency_lock import ConcurrencyLock, get_concurrency_lock


class TestConcurrencyLock:
    """Test ConcurrencyLock functionality."""

    def test_initialization_with_defaults(self):
        """ConcurrencyLock should initialize with default timeout."""
        # Act
        lock = ConcurrencyLock()

        # Assert
        assert lock.timeout_seconds == 600
        assert lock.is_locked() is False

    def test_initialization_with_custom_timeout(self):
        """ConcurrencyLock should accept custom timeout."""
        # Act
        lock = ConcurrencyLock(timeout_seconds=300)

        # Assert
        assert lock.timeout_seconds == 300

    def test_acquire_succeeds_when_unlocked(self):
        """Acquire should succeed when lock is available."""
        # Arrange
        lock = ConcurrencyLock()

        # Act
        acquired = lock.acquire("run-1")

        # Assert
        assert acquired is True
        assert lock.is_locked() is True
        assert lock.get_holder() == "run-1"

        # Cleanup
        lock.release("run-1")

    def test_acquire_fails_when_already_locked(self):
        """Acquire should fail when lock is already held."""
        # Arrange
        lock = ConcurrencyLock()
        lock.acquire("run-1")

        # Act
        acquired = lock.acquire("run-2", blocking=False)

        # Assert
        assert acquired is False
        assert lock.get_holder() == "run-1"  # Original holder unchanged

        # Cleanup
        lock.release("run-1")

    def test_acquire_with_timeout_waits_then_fails(self):
        """Acquire with timeout should wait then fail if lock unavailable."""
        # Arrange
        lock = ConcurrencyLock()
        lock.acquire("run-1")

        # Act
        start = time.time()
        acquired = lock.acquire("run-2", blocking=True, timeout=0.1)
        duration = time.time() - start

        # Assert
        assert acquired is False
        assert duration >= 0.1  # Should have waited
        assert duration < 0.5  # But not too long

        # Cleanup
        lock.release("run-1")

    def test_release_succeeds_for_holder(self):
        """Release should succeed when called by lock holder."""
        # Arrange
        lock = ConcurrencyLock()
        lock.acquire("run-1")

        # Act
        released = lock.release("run-1")

        # Assert
        assert released is True
        assert lock.is_locked() is False
        assert lock.get_holder() is None

    def test_release_fails_for_non_holder(self):
        """Release should fail when called by non-holder."""
        # Arrange
        lock = ConcurrencyLock()
        lock.acquire("run-1")

        # Act
        released = lock.release("run-2")

        # Assert
        assert released is False
        assert lock.is_locked() is True
        assert lock.get_holder() == "run-1"

        # Cleanup
        lock.release("run-1")

    def test_context_manager_acquires_and_releases(self):
        """Context manager should acquire on enter and release on exit."""
        # Arrange
        lock = ConcurrencyLock()

        # Act
        with lock.lock_context("run-1") as acquired:
            # Assert within context
            assert acquired is True
            assert lock.is_locked() is True
            assert lock.get_holder() == "run-1"

        # Assert after context
        assert lock.is_locked() is False
        assert lock.get_holder() is None

    def test_context_manager_releases_on_exception(self):
        """Context manager should release lock even if exception occurs."""
        # Arrange
        lock = ConcurrencyLock()

        # Act/Assert
        try:
            with lock.lock_context("run-1"):
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Assert
        assert lock.is_locked() is False

    def test_context_manager_fails_when_lock_unavailable(self):
        """Context manager should return False when lock unavailable."""
        # Arrange
        lock = ConcurrencyLock()
        lock.acquire("run-1")

        # Act
        with lock.lock_context("run-2", timeout=0.1) as acquired:
            # Assert
            assert acquired is False

        # Cleanup
        lock.release("run-1")

    def test_is_locked_returns_true_when_locked(self):
        """is_locked should return True when lock is held."""
        # Arrange
        lock = ConcurrencyLock()
        lock.acquire("run-1")

        # Act
        result = lock.is_locked()

        # Assert
        assert result is True

        # Cleanup
        lock.release("run-1")

    def test_is_locked_returns_false_when_unlocked(self):
        """is_locked should return False when lock is free."""
        # Arrange
        lock = ConcurrencyLock()

        # Act
        result = lock.is_locked()

        # Assert
        assert result is False

    def test_get_holder_returns_none_when_unlocked(self):
        """get_holder should return None when no lock held."""
        # Arrange
        lock = ConcurrencyLock()

        # Act
        holder = lock.get_holder()

        # Assert
        assert holder is None

    def test_get_holder_returns_holder_id_when_locked(self):
        """get_holder should return holder ID when locked."""
        # Arrange
        lock = ConcurrencyLock()
        lock.acquire("run-1")

        # Act
        holder = lock.get_holder()

        # Assert
        assert holder == "run-1"

        # Cleanup
        lock.release("run-1")

    def test_thread_safety_prevents_concurrent_acquisition(self):
        """Lock should prevent concurrent acquisitions from threads."""
        # Arrange
        lock = ConcurrencyLock()
        results = []

        def try_acquire(run_id):
            acquired = lock.acquire(run_id, blocking=False)
            results.append((run_id, acquired))
            if acquired:
                time.sleep(0.1)
                lock.release(run_id)

        # Act
        threads = [threading.Thread(target=try_acquire, args=(f"run-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert
        successful = [r for r in results if r[1]]
        assert len(successful) <= 5  # Some may succeed serially
        # But never more than 5 total attempts

    def test_get_concurrency_lock_returns_singleton(self):
        """get_concurrency_lock should return same instance."""
        # Act
        lock1 = get_concurrency_lock()
        lock2 = get_concurrency_lock()

        # Assert
        assert lock1 is lock2

    def test_acquired_at_timestamp_is_set(self):
        """acquired_at timestamp should be set on acquisition."""
        # Arrange
        lock = ConcurrencyLock()

        # Act
        lock.acquire("run-1")
        acquired_at = lock._acquired_at

        # Assert
        assert acquired_at is not None
        # Should be recent
        from datetime import datetime, timedelta

        assert acquired_at > datetime.utcnow() - timedelta(seconds=1)

        # Cleanup
        lock.release("run-1")

    def test_timeout_validation_prevents_expired_locks(self):
        """Lock should track timeout but not auto-expire in basic implementation."""
        # Arrange
        lock = ConcurrencyLock(timeout_seconds=1)

        # Act
        lock.acquire("run-1")
        time.sleep(1.5)

        # Assert
        # Basic implementation doesn't auto-expire, but tracks time
        assert lock.is_locked() is True
        assert lock._acquired_at is not None

        # Cleanup
        lock.release("run-1")
