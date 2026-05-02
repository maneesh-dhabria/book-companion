"""B5: lifespan orphan-recovery for step=AUDIO."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    Base,
    Book,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
)
from app.services.audio_orphan_recovery import recover_orphan_audio_jobs


@pytest_asyncio.fixture
async def session(tmp_path):
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/library.db")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(eng, expire_on_commit=False)
    async with sm() as s:
        book = Book(
            title="B",
            file_data=b"\x00",
            file_hash="h",
            file_format="epub",
            file_size_bytes=1,
            status=BookStatus.COMPLETED,
        )
        s.add(book)
        await s.commit()
        yield s


@pytest.mark.asyncio
async def test_orphan_audio_job_marked_failed(session):
    job = ProcessingJob(
        book_id=1,
        step=ProcessingStep.AUDIO,
        status=ProcessingJobStatus.RUNNING,
        pid=99999,
    )
    session.add(job)
    await session.commit()
    n = await recover_orphan_audio_jobs(session)
    assert n == 1
    await session.refresh(job)
    assert job.status == ProcessingJobStatus.FAILED
    assert job.error_message == "server_restart"


@pytest.mark.asyncio
async def test_live_pid_not_touched(session):
    job = ProcessingJob(
        book_id=1,
        step=ProcessingStep.AUDIO,
        status=ProcessingJobStatus.RUNNING,
        pid=os.getpid(),
    )
    session.add(job)
    await session.commit()
    n = await recover_orphan_audio_jobs(session)
    assert n == 0
    await session.refresh(job)
    assert job.status == ProcessingJobStatus.RUNNING


@pytest.mark.asyncio
async def test_no_audio_jobs_no_op(session):
    n = await recover_orphan_audio_jobs(session)
    assert n == 0
