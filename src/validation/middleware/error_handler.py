"""
Production-safe error handling.

KISS approach: Don't expose stack traces in production.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.validation.logger import logger
from src.validation.security_config import get_security_settings


async def production_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle exceptions in production-safe manner.

    Args:
        request: FastAPI request
        exc: Exception raised

    Returns:
        JSONResponse with sanitized error message
    """
    settings = get_security_settings()

    # Log full error details
    if settings.log_error_details:
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
            exc_info=True,
            extra={
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else "unknown",
            },
        )

    # Return sanitized error to client
    if settings.show_error_details:
        # Development mode - show details
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "type": type(exc).__name__,
            },
        )
    else:
        # Production mode - hide details
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )


def configure_error_handlers(app):
    """
    Configure error handlers for FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Add generic exception handler
    app.add_exception_handler(Exception, production_error_handler)
