"""T13 / FR-B14a: GET /api/v1/processing/jobs seed endpoint."""

import datetime as dt

import pytest

from app.db.models import (
    Book,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
)


@pytest.mark.asyncio
async def test_jobs_list_returns_active_with_queue_position(app, client):
    factory = app.state.session_factory
    async with factory() as session:
        # Two books — different so the partial UNIQUE index doesn't fire.
        b1 = Book(title="Book One", file_data=b"", file_hash="b1", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        b2 = Book(title="Book Two", file_data=b"", file_hash="b2", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        b3 = Book(title="Book Three", file_data=b"", file_hash="b3", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        session.add_all([b1, b2, b3])
        await session.commit()

        base = dt.datetime.utcnow()
        running = ProcessingJob(
            book_id=b1.id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.RUNNING,
            created_at=base,
        )
        pending_a = ProcessingJob(
            book_id=b2.id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.PENDING,
            created_at=base + dt.timedelta(seconds=1),
            request_params={},
        )
        pending_b = ProcessingJob(
            book_id=b3.id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.PENDING,
            created_at=base + dt.timedelta(seconds=2),
            request_params={},
        )
        session.add_all([running, pending_a, pending_b])
        await session.commit()

    r = await client.get("/api/v1/processing/jobs?status=PENDING,RUNNING")
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert len(jobs) == 3
    assert jobs[0]["status"] == "running"
    assert jobs[0]["queue_position"] == 0
    assert jobs[0]["book_title"] == "Book One"
    assert jobs[1]["status"] == "pending"
    assert jobs[1]["queue_position"] == 1
    assert jobs[1]["book_title"] == "Book Two"
    assert jobs[2]["status"] == "pending"
    assert jobs[2]["queue_position"] == 2


@pytest.mark.asyncio
async def test_jobs_list_filters_terminal_states_by_default(app, client):
    factory = app.state.session_factory
    async with factory() as session:
        b = Book(title="x", file_data=b"", file_hash="x", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        session.add(b)
        await session.commit()
        session.add_all(
            [
                ProcessingJob(
                    book_id=b.id,
                    step=ProcessingStep.SUMMARIZE,
                    status=ProcessingJobStatus.COMPLETED,
                ),
                ProcessingJob(
                    book_id=b.id,
                    step=ProcessingStep.SUMMARIZE,
                    status=ProcessingJobStatus.FAILED,
                ),
            ]
        )
        await session.commit()

    r = await client.get("/api/v1/processing/jobs")
    assert r.status_code == 200
    assert r.json()["jobs"] == []


@pytest.mark.asyncio
async def test_jobs_list_explicit_completed_filter(app, client):
    factory = app.state.session_factory
    async with factory() as session:
        b = Book(title="x", file_data=b"", file_hash="completed-only", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        session.add(b)
        await session.commit()
        session.add(
            ProcessingJob(
                book_id=b.id,
                step=ProcessingStep.SUMMARIZE,
                status=ProcessingJobStatus.COMPLETED,
            )
        )
        await session.commit()

    r = await client.get("/api/v1/processing/jobs?status=COMPLETED")
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["status"] == "completed"
