"""Marks orphaned RUNNING audio jobs as FAILED on server start (FR-21b)."""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProcessingJob, ProcessingJobStatus, ProcessingStep


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


async def recover_orphan_audio_jobs(session: AsyncSession) -> int:
    """Mark RUNNING audio jobs whose pid is dead as FAILED. Returns count."""
    result = await session.execute(
        select(ProcessingJob).where(
            ProcessingJob.status == ProcessingJobStatus.RUNNING,
            ProcessingJob.step == ProcessingStep.AUDIO,
        )
    )
    count = 0
    for job in result.scalars():
        if job.pid is None or not _pid_alive(job.pid):
            job.status = ProcessingJobStatus.FAILED
            job.error_message = "server_restart"
            count += 1
    if count:
        await session.commit()
    return count
