"""Unit tests for backup scheduler."""

from unittest.mock import MagicMock

from app.api.scheduler import create_backup_scheduler


def test_create_scheduler_returns_scheduler():
    mock_service = MagicMock()
    scheduler = create_backup_scheduler(interval_hours=24, backup_service=mock_service)
    assert scheduler is not None


def test_scheduler_disabled_when_interval_zero():
    mock_service = MagicMock()
    scheduler = create_backup_scheduler(interval_hours=0, backup_service=mock_service)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 0


def test_scheduler_has_one_job_when_enabled():
    mock_service = MagicMock()
    scheduler = create_backup_scheduler(interval_hours=24, backup_service=mock_service)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "scheduled_backup"
