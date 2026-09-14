"""
Centralised logging setup.

Structured-ish, single-line logs (timestamp, level, logger name, message)
so they're greppable in production and easy to ship to any log aggregator.
Verbosity is controlled by LOG_LEVEL so it can be turned up for
troubleshooting without a code change.
"""
import logging
import sys

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    # Quiet down noisy third-party loggers unless we're in DEBUG.
    if settings.log_level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
