"""APScheduler setup for scheduled backups."""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.backup_service import BackupService

log = structlog.get_logger()


def create_backup_scheduler(
    interval_hours: int, backup_service: BackupService
) -> AsyncIOScheduler:
    """Create an AsyncIOScheduler for periodic backups.

    Returns a scheduler (not yet started). Call scheduler.start() to begin.
    If interval_hours <= 0, the scheduler has no jobs (effectively disabled).
    """
    scheduler = AsyncIOScheduler()

    if interval_hours > 0:

        async def _run_backup():
            try:
                path = await backup_service.create_backup()
                log.info("scheduled_backup_created", path=str(path))
            except Exception:
                log.exception("scheduled_backup_failed")

        scheduler.add_job(
            _run_backup,
            "interval",
            hours=interval_hours,
            id="scheduled_backup",
            replace_existing=True,
        )

    return scheduler
