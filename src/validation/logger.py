"""
Logging configuration for validation suite.

Configures structured logging with rotation for validation operations.
"""

import logging
import logging.handlers
from pathlib import Path

from src.validation.constants import (
    LOG_BACKUP_COUNT,
    LOG_FILE_PATH,
    LOG_LEVEL,
    LOG_MAX_BYTES,
)


def setup_validation_logger(name: str = "validation") -> logging.Logger:
    """
    Configure validation suite logger.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create logs directory if needed
    log_path = Path(LOG_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Default logger instance
logger = setup_validation_logger()
