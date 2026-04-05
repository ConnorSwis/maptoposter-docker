import logging
import os
import sys
from typing import Optional


# Simple ANSI color codes
_RESET = "\x1b[0m"
_COLORS = {
    "DEBUG": "\x1b[36m",  # Cyan
    "INFO": "\x1b[32m",  # Green
    "WARNING": "\x1b[33m",  # Yellow
    "ERROR": "\x1b[31m",  # Red
    "CRITICAL": "\x1b[41;37m",  # White on red
}


class ColoredFormatter(logging.Formatter):
    """Formatter that adds color to the level name."""

    def __init__(self, fmt: str | None = None, datefmt: Optional[str] = None):
        super().__init__(
            fmt or "%(levelname)s: %(message)s",
            datefmt=datefmt,
        )

    def format(self, record: logging.LogRecord) -> str:
        # # preserve original levelname
        # original_levelname = record.levelname
        # color = _COLORS.get(original_levelname, "")
        # try:
        #     # color only the level name to keep file/func/line readable
        #     record.levelname = f"{color}{original_levelname}{_RESET}"
        #     return super().format(record)
        # finally:
        #     record.levelname = original_levelname
        return super().format(record)


# Module-level singleton logger
_logger: Optional[logging.Logger] = None


def _parse_level(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return getattr(logging, value.upper(), default)


def _log_format() -> str:
    verbose = os.getenv("CITY_MAP_POSTER_LOG_VERBOSE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if verbose:
        return "%(levelname)s %(filename)s:%(funcName)s:%(lineno)d - %(message)s"
    return "%(levelname)s: %(message)s"


def get_logger(
    name: str = "city_map_poster", level: int | None = None
) -> logging.Logger:
    """Return a singleton logger configured with colors and a formatter that
    includes file name, function name, line number, level and message.

    Subsequent calls return the same logger instance.
    """
    global _logger
    resolved_level = _parse_level(os.getenv("CITY_MAP_POSTER_LOG_LEVEL"), logging.INFO)
    if level is not None:
        resolved_level = level
    if _logger is None:
        _logger = logging.getLogger(name)
        _logger.setLevel(resolved_level)
        # Avoid adding multiple handlers if called repeatedly
        if not _logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(resolved_level)
            handler.setFormatter(ColoredFormatter(fmt=_log_format()))
            _logger.addHandler(handler)
            _logger.propagate = False
    else:
        _logger.setLevel(resolved_level)
        for handler in _logger.handlers:
            handler.setLevel(resolved_level)
    return _logger


__all__ = ["get_logger"]
