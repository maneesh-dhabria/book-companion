"""Startup sweep that marks dead RUNNING / PENDING jobs FAILED.

When the server is killed mid-job, `processing_jobs` rows stay in ``RUNNING``
indefinitely — leaving the book locked by the v1.4 partial UNIQUE index and
the Summary tab stuck in a perpetual "Generating..." state. Running this
sweep before the FastAPI app accepts requests reconciles those rows: any
job whose ``pid`` is not a live process gets marked ``FAILED`` with a
"Server restarted mid-job" message.

Jobs whose ``pid`` column is NULL (legacy rows predating the column) are
also swept — we have no way to confirm they're alive.

**Known limitation — PID recycling.** On long-uptime systems with small PID
spaces the OS may recycle a dead job's PID to an unrelated live process.
``_pid_is_alive`` would then see "alive" and skip the sweep. We mitigate
via a ``max_age`` heuristic: any RUNNING/PENDING job whose ``started_at``
is older than ``max_age`` is treated as dead regardless of PID — a normal
summarize run completes well under this window, so a live match is
vanishingly unlikely in practice.
"""

from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.db.models import ProcessingJob, ProcessingJobStatus

logger = structlog.get_logger()

# Jobs older than this are swept regardless of PID-liveness — defeats PID
# recycling. 24h is an order of magnitude above the longest realistic run.
_STALE_MAX_AGE = timedelta(hours=24)


def _pid_is_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by another user — treat as alive.
        return True
    except OSError:
        return False
    return True


def _job_is_too_old(job: ProcessingJob, now: datetime) -> bool:
    started = job.started_at
    if started is None:
        return False
    # Normalize naive → UTC-aware so the subtraction doesn't error.
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (now - started) > _STALE_MAX_AGE


def is_stale(job, *, now: datetime, max_age: timedelta) -> bool:
    """Return True if the job should be considered abandoned.

    A job is stale when:
      - it has no PID recorded (legacy rows pre-dating the column), or
      - its PID does not refer to a live process (caught via ``os.kill(pid, 0)``
        raising ``ProcessLookupError``), or
      - it has been running longer than ``max_age`` (defeats PID recycling).

    ``PermissionError`` from ``os.kill`` means the PID exists but is owned by
    another user; we treat that as alive (not stale).
    """
    if job.pid is None:
        return True
    try:
        os.kill(job.pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass  # process exists but owned by other user; treat as alive
    except OSError:
        return True

    started = job.started_at
    if started is None:
        return False
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if (now - started) > max_age:
        return True
    return False


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
        if _pid_is_alive(job.pid) and not _job_is_too_old(job, now):
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
