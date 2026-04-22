"""Rotating file logger for LLM subprocess failures.

Writes one line per failure to ``<data_dir>/summarization-failures.log`` with
the file created at mode ``0o600`` (owner-only) to contain sensitive prompt
content and CLI stderr. Rotates at 5 MB with up to 3 backups.

Gated by ``settings.llm.stderr_log_enabled``; callers that want to disable the
log globally set ``BOOKCOMPANION_LLM__STDERR_LOG_ENABLED=false``.
"""

from __future__ import annotations

import contextlib
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "bookcompanion.summarizer_failures"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s | %(message)s"


def _open_owner_only(path: Path) -> None:
    """Create ``path`` if missing with mode 0600. No-op if it already exists."""
    if path.exists():
        # Ensure mode stays owner-only even if umask allowed wider bits earlier.
        with contextlib.suppress(OSError):
            path.chmod(0o600)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    os.close(fd)


def get_failure_logger(log_path: str | os.PathLike) -> logging.Logger:
    """Return the singleton failure logger targeting ``log_path``.

    Idempotent: repeated calls with the same path reuse the attached handler.
    Calls with a different path replace the handler (test isolation).
    """
    path = Path(log_path)
    _open_owner_only(path)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    # Reconfigure if previously bound to a different file (e.g., across tests).
    existing = next(
        (h for h in logger.handlers if isinstance(h, RotatingFileHandler)), None
    )
    if existing is not None and Path(existing.baseFilename) == path:
        return logger
    for h in list(logger.handlers):
        logger.removeHandler(h)
        with contextlib.suppress(Exception):  # pragma: no cover - best-effort cleanup
            h.close()

    handler = RotatingFileHandler(
        str(path), maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    return logger


def log_failure(
    log_path: str | os.PathLike,
    *,
    failure_type: str,
    section_id: int | None,
    book_id: int | None,
    message: str,
) -> None:
    """Write a single failure line. Shape::

        2026-04-22T10:00:00 | section_id=42 | book_id=1 | type=cli_timeout | <message>
    """
    logger = get_failure_logger(log_path)
    logger.error(
        "section_id=%s | book_id=%s | type=%s | %s",
        section_id if section_id is not None else "-",
        book_id if book_id is not None else "-",
        failure_type,
        message,
    )
