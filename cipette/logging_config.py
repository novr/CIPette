"""Logging configuration for CIPette application."""

import logging
from pathlib import Path


def setup_logging() -> None:
    """Set up logging configuration for the entire application."""
    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(data_dir / 'cipette.log'),
            logging.StreamHandler()
        ]
    )

    # Set specific loggers to appropriate levels
    logging.getLogger('cipette.collector').setLevel(logging.INFO)
    logging.getLogger('cipette.database').setLevel(logging.INFO)
    logging.getLogger('cipette.app').setLevel(logging.INFO)

    # Reduce noise from third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Logging configuration initialized")
    return logger
