"""Logging configuration for the application.

Sets up a console handler (readable during development) and a rotating
file handler (persistent logs under logs/app.log).
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from app.core.config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    """Configure the root logger. Call once at application startup."""
    settings = get_settings()

    log_dir = os.path.dirname(settings.log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())

    # Avoid duplicate handlers if configure_logging() is called more than once.
    if root_logger.handlers:
        return

    formatter = logging.Formatter(_LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        settings.log_file_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use __name__ from the calling module."""
    return logging.getLogger(name)
