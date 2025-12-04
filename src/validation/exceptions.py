"""
Custom exceptions for validation suite.

Provides specific error types for validation failures and data issues.
"""


class ValidationError(Exception):
    """Base exception for validation suite errors."""

    pass


class DataFetchError(ValidationError):
    """Raised when data fetching fails."""

    pass


class InsufficientDataError(ValidationError):
    """Raised when data completeness is below threshold."""

    pass


class TestExecutionError(ValidationError):
    """Raised when a validation test fails to execute."""

    pass


class ReportGenerationError(ValidationError):
    """Raised when report generation fails."""

    pass


class StorageError(ValidationError):
    """Raised when database storage operations fail."""

    pass


class QueueFullError(ValidationError):
    """Raised when validation queue is full."""

    pass


class ValidationTimeoutError(ValidationError):
    """Raised when validation exceeds time limit."""

    pass
