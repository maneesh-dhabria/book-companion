"""Structured logging configuration via structlog."""

import logging
import sys
from pathlib import Path

import structlog

from app.config import Settings


def setup_logging(settings: Settings) -> None:
    """Configure structlog with JSON output and file rotation."""
    log_dir = Path(settings.logging.log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, settings.logging.level),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.logging.json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
