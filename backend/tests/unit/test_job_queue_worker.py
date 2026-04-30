"""JobQueueWorker scaffold + atomic-promotion tests (T11a, T11b)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.models import (
    Base,
    Book,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
)
from app.services.job_queue_worker import JobQueueWorker


@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "queue_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def book(session_factory):
    async with session_factory() as session:
        b = Book(
            title="t",
            file_data=b"",
            file_hash="h-queue",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.PARSED,
        )
        session.add(b)
        await session.commit()
        return b.id


@pytest.fixture
def event_bus():
    bus = AsyncMock()
    bus.publish = AsyncMock()
    bus.close = AsyncMock()
    return bus


@pytest.fixture
def settings():
    return Settings()


async def _seed_pending(session_factory, book_id: int, count: int = 1) -> list[int]:
    """Seed N PENDING jobs spaced by 1 microsecond so ordering is stable."""
    import datetime as dt

    ids = []
    async with session_factory() as session:
        base = dt.datetime.utcnow()
        for i in range(count):
            session.add(
                ProcessingJob(
                    book_id=book_id,
                    step=ProcessingStep.SUMMARIZE,
                    status=ProcessingJobStatus.PENDING,
                    created_at=base + dt.timedelta(microseconds=i),
                    request_params={"preset_name": "practitioner_bullets"},
                )
            )
        await session.commit()
        rows = (
            await session.execute(
                select(ProcessingJob.id).order_by(ProcessingJob.created_at)
            )
        ).scalars().all()
        ids.extend(rows)
    return ids


@pytest.mark.asyncio
async def test_worker_starts_and_stops_cleanly(session_factory, event_bus, settings):
    worker = JobQueueWorker(session_factory, event_bus, settings, poll_interval=0.05)
    await worker.start()
    assert worker._task is not None and not worker._task.done()
    await worker.stop()
    assert worker._task.done()


@pytest.mark.asyncio
async def test_worker_stop_is_idempotent(session_factory, event_bus, settings):
    worker = JobQueueWorker(session_factory, event_bus, settings, poll_interval=0.05)
    await worker.start()
    await worker.stop()
    await worker.stop()  # second stop must not error


@pytest.mark.asyncio
async def test_atomic_promote_picks_oldest(session_factory, event_bus, settings):
    """Two PENDING jobs across two different books — promotion must pick the
    one with the older created_at."""
    import datetime as dt

    async with session_factory() as session:
        b1 = Book(title="b1", file_data=b"", file_hash="h1", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        b2 = Book(title="b2", file_data=b"", file_hash="h2", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        session.add_all([b1, b2])
        await session.commit()
        b1_id, b2_id = b1.id, b2.id
        base = dt.datetime.utcnow()
        older = ProcessingJob(
            book_id=b1_id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.PENDING,
            created_at=base,
            request_params={},
        )
        newer = ProcessingJob(
            book_id=b2_id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.PENDING,
            created_at=base + dt.timedelta(seconds=1),
            request_params={},
        )
        session.add_all([older, newer])
        await session.commit()
        older_id = older.id

    worker = JobQueueWorker(session_factory, event_bus, settings)
    promoted = await worker._atomic_promote()
    assert promoted == older_id
    async with session_factory() as session:
        promoted_job = (
            await session.execute(
                select(ProcessingJob).where(ProcessingJob.id == older_id)
            )
        ).scalar_one()
        assert promoted_job.status == ProcessingJobStatus.RUNNING
        assert promoted_job.started_at is not None


@pytest.mark.asyncio
async def test_atomic_promote_skips_when_running_exists(
    session_factory, event_bus, settings, book
):
    # Insert one RUNNING + one PENDING (different books to avoid unique idx)
    async with session_factory() as session:
        b2 = Book(
            title="t2",
            file_data=b"",
            file_hash="h-queue-2",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.PARSED,
        )
        session.add(b2)
        await session.commit()
        b2_id = b2.id

        session.add(
            ProcessingJob(
                book_id=book,
                step=ProcessingStep.SUMMARIZE,
                status=ProcessingJobStatus.RUNNING,
            )
        )
        session.add(
            ProcessingJob(
                book_id=b2_id,
                step=ProcessingStep.SUMMARIZE,
                status=ProcessingJobStatus.PENDING,
                request_params={},
            )
        )
        await session.commit()

    worker = JobQueueWorker(session_factory, event_bus, settings)
    promoted = await worker._atomic_promote()
    assert promoted is None  # RUNNING blocks promotion
    async with session_factory() as session:
        pending_count = (
            await session.execute(
                select(ProcessingJob).where(
                    ProcessingJob.status == ProcessingJobStatus.PENDING
                )
            )
        ).all()
        assert len(pending_count) == 1


@pytest.mark.asyncio
async def test_atomic_promote_skips_cancelled_pending(
    session_factory, event_bus, settings, book
):
    """Cancel-PENDING flips cancel_requested=True; the worker must not promote
    those rows (FR-B14)."""
    async with session_factory() as session:
        session.add(
            ProcessingJob(
                book_id=book,
                step=ProcessingStep.SUMMARIZE,
                status=ProcessingJobStatus.PENDING,
                cancel_requested=True,
                request_params={},
            )
        )
        await session.commit()
    worker = JobQueueWorker(session_factory, event_bus, settings)
    promoted = await worker._atomic_promote()
    assert promoted is None


@pytest.mark.asyncio
async def test_no_double_promotion_under_concurrent_ticks(
    session_factory, event_bus, settings, book
):
    """Two _atomic_promote calls in parallel must promote at most one row."""
    await _seed_pending(session_factory, book, count=1)
    worker_a = JobQueueWorker(session_factory, event_bus, settings)
    worker_b = JobQueueWorker(session_factory, event_bus, settings)
    results = await asyncio.gather(
        worker_a._atomic_promote(),
        worker_b._atomic_promote(),
    )
    promoted = [r for r in results if r is not None]
    assert len(promoted) == 1
    async with session_factory() as session:
        running = (
            await session.execute(
                select(ProcessingJob).where(
                    ProcessingJob.status == ProcessingJobStatus.RUNNING
                )
            )
        ).scalars().all()
        assert len(running) == 1


@pytest.mark.asyncio
async def test_tick_returns_false_when_no_pending(
    session_factory, event_bus, settings
):
    worker = JobQueueWorker(session_factory, event_bus, settings)
    promoted = await worker.tick()
    assert promoted is False
    event_bus.publish.assert_not_called()
