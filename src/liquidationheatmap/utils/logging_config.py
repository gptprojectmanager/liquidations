"""Simple logging configuration (KISS approach - no structlog)."""

import logging
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str = "logs/liquidationheatmap.log") -> None:
    """Configure basic logging for the application.
    
    KISS approach: Python standard logging, no external dependencies.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (default: logs/liquidationheatmap.log)
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    # Set specific logger levels
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.INFO)
    
    logging.info(f"Logging configured: level={level}, file={log_file}")
