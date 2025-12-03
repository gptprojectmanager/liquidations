"""Simple retry logic for database operations (KISS approach)."""

import logging
import time
from typing import Callable, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


def retry_on_error(func: Callable[[], T], max_attempts: int = 3, backoff_seconds: float = 1.0) -> T:
    """Retry a function on error with exponential backoff.

    KISS approach: Simple function wrapper, no complex decorators.

    Args:
        func: Function to retry (zero-argument callable)
        max_attempts: Maximum number of attempts (default: 3)
        backoff_seconds: Initial backoff time in seconds (default: 1.0)

    Returns:
        Result of successful function call

    Raises:
        Last exception if all attempts fail

    Example:
        >>> result = retry_on_error(lambda: db.conn.execute(query))
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                sleep_time = backoff_seconds * (2**attempt)  # 1s, 2s, 4s
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {e}. Retrying in {sleep_time}s..."
                )
                time.sleep(sleep_time)
            else:
                logger.error(f"All {max_attempts} attempts failed. Last error: {e}")

    raise last_exception
