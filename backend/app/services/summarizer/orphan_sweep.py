"""Startup sweep that marks dead RUNNING / PENDING jobs FAILED.

When the server is killed mid-job, `processing_jobs` rows stay in ``RUNNING``
indefinitely — leaving the book locked by the v1.4 partial UNIQUE index and
the Summary tab stuck in a perpetual "Generating..." state. Running this
sweep before the FastAPI app accepts requests reconciles those rows: any
job whose ``pid`` is not a live process gets marked ``FAILED`` with a
"Server restarted mid-job" message.

Jobs whose ``pid`` column is NULL (legacy rows predating the column) are
also swept — we have no way to confirm they're alive.
"""

from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.db.models import ProcessingJob, ProcessingJobStatus

logger = structlog.get_logger()


def _pid_is_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


async def orphan_sweep(db: AsyncSession) -> int:
    """Mark dead RUNNING/PENDING jobs FAILED. Returns the count of sweeps."""
    rows = (
        await db.execute(
            sa.select(ProcessingJob).where(
                ProcessingJob.status.in_(
                    [ProcessingJobStatus.RUNNING, ProcessingJobStatus.PENDING]
                )
            )
        )
    ).scalars().all()

    swept = 0
    now = datetime.now(UTC)
    for job in rows:
        if _pid_is_alive(job.pid):
            continue
        job.status = ProcessingJobStatus.FAILED
        job.error_message = "Server restarted mid-job"
        job.completed_at = now
        swept += 1

    if swept:
        with contextlib.suppress(Exception):
            logger.info("orphan_jobs_swept", count=swept)
    await db.commit()
    return swept
