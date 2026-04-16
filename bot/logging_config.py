"""Rotating file logger for request/response auditing."""

import logging
import os
from logging.handlers import RotatingFileHandler

from bot.config import LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a named logger wired to the shared rotating file handler.

    Args:
        name: Logger namespace, typically ``__name__``.

    Returns:
        Configured ``logging.Logger`` instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(_FORMAT))

    logger.addHandler(file_handler)
    logger.propagate = False

    return logger
