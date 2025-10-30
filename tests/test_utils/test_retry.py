"""Tests for retry logic decorator."""

from src.liquidationheatmap.utils.retry import retry_with_backoff


class TestRetryWithBackoff:
    """Test retry decorator with exponential backoff."""

    def test_retry_succeeds_on_first_attempt(self):
        """Test that function succeeding on first attempt returns immediately."""
        call_count = []

        @retry_with_backoff(max_attempts=3, backoff_seconds=[0.01, 0.02])
        def success_function():
            call_count.append(1)
            return "success"

        result = success_function()

        assert result == "success"
        assert len(call_count) == 1  # Called only once
