"""ProcessingJob repository — data access layer."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProcessingJob, ProcessingJobStatus, ProcessingStep


class ProcessingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: ProcessingJob) -> ProcessingJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_active_for_book(
        self, book_id: int, step: ProcessingStep | None = None
    ) -> list[ProcessingJob]:
        query = select(ProcessingJob).where(
            ProcessingJob.book_id == book_id,
            ProcessingJob.status.in_([ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]),
        )
        if step:
            query = query.where(ProcessingJob.step == step)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        job_id: int,
        status: ProcessingJobStatus,
        error_message: str | None = None,
        progress: dict | None = None,
    ) -> None:
        result = await self.session.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            if error_message:
                job.error_message = error_message
            if progress:
                job.progress = progress
            if status == ProcessingJobStatus.RUNNING and not job.started_at:
                job.started_at = datetime.now(timezone.utc)
            if status in (ProcessingJobStatus.COMPLETED, ProcessingJobStatus.FAILED):
                job.completed_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def get_orphaned_jobs(self, max_age_hours: int = 24) -> list[ProcessingJob]:
        """Find running jobs that may have been abandoned."""
        cutoff = datetime.now(timezone.utc).replace(
            hour=datetime.now(timezone.utc).hour - max_age_hours
        )
        result = await self.session.execute(
            select(ProcessingJob).where(
                ProcessingJob.status == ProcessingJobStatus.RUNNING,
                ProcessingJob.started_at < cutoff,
            )
        )
        return list(result.scalars().all())
