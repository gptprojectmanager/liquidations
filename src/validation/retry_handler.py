"""
Retry logic with exponential backoff for validation suite.

Handles transient failures with automatic retry and backoff.
"""

import time
from functools import wraps
from typing import Any, Callable

from src.validation.constants import (
    MAX_BACKOFF_TIME,
    MAX_RETRY_ATTEMPTS,
    RETRY_BACKOFF_BASE,
)
from src.validation.exceptions import ValidationTimeoutError
from src.validation.logger import logger


def retry_with_backoff(
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    backoff_base: float = RETRY_BACKOFF_BASE,
    max_backoff: float = MAX_BACKOFF_TIME,
    exceptions: tuple = (Exception,),
):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        backoff_base: Base seconds for backoff calculation
        max_backoff: Maximum backoff time in seconds
        exceptions: Tuple of exception types to catch

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    attempt += 1

                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate backoff time: 2^attempt * backoff_base
                    backoff_time = min(backoff_base * (2**attempt), max_backoff)

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {backoff_time:.1f}s..."
                    )

                    time.sleep(backoff_time)

            raise ValidationTimeoutError(f"Function {func.__name__} exceeded max retry attempts")

        return wrapper

    return decorator


class RetryHandler:
    """
    Retry handler for validation operations.

    Provides retry logic with exponential backoff for transient failures.
    """

    def __init__(
        self,
        max_attempts: int = MAX_RETRY_ATTEMPTS,
        backoff_base: float = RETRY_BACKOFF_BASE,
        max_backoff: float = MAX_BACKOFF_TIME,
    ):
        """
        Initialize retry handler.

        Args:
            max_attempts: Maximum retry attempts
            backoff_base: Base seconds for backoff
            max_backoff: Maximum backoff time
        """
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff

    def execute_with_retry(
        self, func: Callable, *args, exceptions: tuple = (Exception,), **kwargs
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            exceptions: Exceptions to catch and retry
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retry attempts fail
        """
        attempt = 0

        while attempt < self.max_attempts:
            try:
                return func(*args, **kwargs)

            except exceptions as e:
                attempt += 1

                if attempt >= self.max_attempts:
                    logger.error(
                        f"Function {func.__name__} failed after {self.max_attempts} attempts: {e}"
                    )
                    raise

                # Exponential backoff
                backoff_time = min(self.backoff_base * (2 ** (attempt - 1)), self.max_backoff)

                logger.warning(
                    f"Attempt {attempt}/{self.max_attempts} failed: {e}. "
                    f"Retrying in {backoff_time:.1f}s..."
                )

                time.sleep(backoff_time)

        raise ValidationTimeoutError(f"Max retry attempts ({self.max_attempts}) exceeded")


# Example usage with decorator
@retry_with_backoff(max_attempts=3, backoff_base=2, exceptions=(ConnectionError, TimeoutError))
def fetch_data_with_retry(url: str):
    """Example function with retry logic."""
    # Would implement actual data fetching here
    pass
