"""T12 / FR-B14, FR-B15: cancel route behavior."""

import pytest
from sqlalchemy import select

from app.db.models import (
    Book,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
)


async def _seed_book(app) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        b = Book(
            title="t",
            file_data=b"",
            file_hash="cancel-test",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.PARSED,
        )
        session.add(b)
        await session.commit()
        return b.id


@pytest.mark.asyncio
async def test_cancel_pending_atomically_deletes_row(app, client):
    book_id = await _seed_book(app)
    factory = app.state.session_factory
    async with factory() as session:
        job = ProcessingJob(
            book_id=book_id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.PENDING,
            request_params={},
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    r = await client.post(f"/api/v1/processing/{job_id}/cancel")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING_REMOVED"
    async with factory() as session:
        present = (
            await session.execute(
                select(ProcessingJob).where(ProcessingJob.id == job_id)
            )
        ).scalar_one_or_none()
        assert present is None


@pytest.mark.asyncio
async def test_cancel_running_sets_flag(app, client):
    book_id = await _seed_book(app)
    factory = app.state.session_factory
    async with factory() as session:
        job = ProcessingJob(
            book_id=book_id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.RUNNING,
            request_params={},
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    r = await client.post(f"/api/v1/processing/{job_id}/cancel")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "CANCEL_REQUESTED"
    async with factory() as session:
        job = (
            await session.execute(
                select(ProcessingJob).where(ProcessingJob.id == job_id)
            )
        ).scalar_one()
        assert job.cancel_requested is True
        assert job.status == ProcessingJobStatus.RUNNING


@pytest.mark.asyncio
async def test_cancel_completed_returns_already_done(app, client):
    book_id = await _seed_book(app)
    factory = app.state.session_factory
    async with factory() as session:
        job = ProcessingJob(
            book_id=book_id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.COMPLETED,
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    r = await client.post(f"/api/v1/processing/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "ALREADY_DONE"


@pytest.mark.asyncio
async def test_cancel_missing_returns_404(client):
    r = await client.post("/api/v1/processing/9999999/cancel")
    assert r.status_code == 404
