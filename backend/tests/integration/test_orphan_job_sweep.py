"""FR-A7.4 — orphan sweep marks dead RUNNING jobs FAILED at startup."""

import os

import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, ProcessingJob, ProcessingJobStatus
from app.services.summarizer.orphan_sweep import orphan_sweep


async def _setup_db(tmp_path):
    db_path = tmp_path / "library.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_orphan_sweep_marks_dead_running_job_failed(tmp_path):
    engine, maker = await _setup_db(tmp_path)
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES (1, 'T', x'00', 'h', 'epub', 1, 'COMPLETED')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (1, 'RUNNING', 'SUMMARIZE', 999999)"
            )
        )
        await session.commit()

    async with maker() as session:
        swept = await orphan_sweep(session)
    assert swept == 1

    async with maker() as session:
        row = (
            await session.execute(
                sa.select(ProcessingJob).where(ProcessingJob.book_id == 1)
            )
        ).scalar_one()
        assert row.status == ProcessingJobStatus.FAILED
        assert "restarted mid-job" in (row.error_message or "").lower()
        assert row.completed_at is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_orphan_sweep_preserves_live_running_job(tmp_path):
    engine, maker = await _setup_db(tmp_path)
    my_pid = os.getpid()
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES (1, 'T', x'00', 'h', 'epub', 1, 'COMPLETED')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (1, 'RUNNING', 'SUMMARIZE', :pid)"
            ),
            {"pid": my_pid},
        )
        await session.commit()

    async with maker() as session:
        swept = await orphan_sweep(session)
    assert swept == 0

    async with maker() as session:
        row = (
            await session.execute(
                sa.select(ProcessingJob).where(ProcessingJob.book_id == 1)
            )
        ).scalar_one()
        assert row.status == ProcessingJobStatus.RUNNING
    await engine.dispose()


@pytest.mark.asyncio
async def test_orphan_sweep_sweeps_stale_job_even_with_live_pid(tmp_path):
    """FR-A7.4 — PID recycling defence. A job whose PID is currently alive
    but whose ``started_at`` is >24h old is still swept, because no real
    summarization takes that long — the live match must be a recycled PID
    from an unrelated process."""
    import os as _os
    from datetime import UTC, datetime, timedelta

    engine, maker = await _setup_db(tmp_path)
    stale_ts = datetime.now(UTC) - timedelta(hours=48)
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES (1, 'T', x'00', 'h', 'epub', 1, 'COMPLETED')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid, started_at) "
                "VALUES (1, 'RUNNING', 'SUMMARIZE', :pid, :ts)"
            ),
            {"pid": _os.getpid(), "ts": stale_ts.replace(tzinfo=None).isoformat()},
        )
        await session.commit()

    async with maker() as session:
        swept = await orphan_sweep(session)
    assert swept == 1, "stale job should be swept despite PID matching this process"

    async with maker() as session:
        row = (
            await session.execute(
                sa.select(ProcessingJob).where(ProcessingJob.book_id == 1)
            )
        ).scalar_one()
        assert row.status == ProcessingJobStatus.FAILED
    await engine.dispose()


@pytest.mark.asyncio
async def test_orphan_sweep_sweeps_rows_with_null_pid(tmp_path):
    engine, maker = await _setup_db(tmp_path)
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) VALUES (1, 'T', x'00', 'h', 'epub', 1, 'COMPLETED')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO processing_jobs (book_id, status, step, pid) "
                "VALUES (1, 'RUNNING', 'SUMMARIZE', NULL)"
            )
        )
        await session.commit()

    async with maker() as session:
        swept = await orphan_sweep(session)
    assert swept == 1
    await engine.dispose()


