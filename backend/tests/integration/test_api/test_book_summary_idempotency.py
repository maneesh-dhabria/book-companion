"""T4: Book-summary 409 idempotency must include active_job_id (FR-02 E11)."""

import pytest
from httpx import AsyncClient

from app.db.models import (
    Book,
    BookSection,
    BookStatus,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
    Summary,
    SummaryContentType,
)


async def _seed_book_with_active_job(app) -> tuple[int, int]:
    """Create a book + section + section summary + a PENDING ProcessingJob.

    Returns (book_id, active_job_id). The pending job mimics state after the
    first POST /books/{id}/book-summary, so the *next* POST hits the 409 branch
    deterministically without having to race the background task.
    """
    factory = app.state.session_factory
    async with factory() as session:
        book = Book(
            title="Idem",
            file_data=b"",
            file_hash="idem-1",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.COMPLETED,
        )
        session.add(book)
        await session.commit()
        sec = BookSection(
            book_id=book.id,
            order_index=0,
            title="S1",
            content_md="body",
            section_type="chapter",
            content_token_count=10,
        )
        session.add(sec)
        await session.flush()
        section_summary = Summary(
            content_type=SummaryContentType.SECTION,
            content_id=sec.id,
            book_id=book.id,
            facets_used={},
            prompt_text_sent="p",
            model_used="sonnet",
            input_char_count=10,
            summary_char_count=5,
            summary_md="s",
        )
        session.add(section_summary)
        await session.flush()
        sec.default_summary_id = section_summary.id
        job = ProcessingJob(
            book_id=book.id,
            step=ProcessingStep.SUMMARIZE,
            status=ProcessingJobStatus.PENDING,
            pid=99999,
        )
        session.add(job)
        await session.commit()
        return book.id, job.id


@pytest.mark.asyncio
async def test_concurrent_book_summary_returns_409_with_active_job_id(client: AsyncClient, app):
    book_id, job_id = await _seed_book_with_active_job(app)
    r = await client.post(
        f"/api/v1/books/{book_id}/book-summary",
        json={"preset_name": "practitioner_bullets"},
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert "active_job_id" in body
    assert body["active_job_id"] == job_id
    assert "in progress" in body.get("detail", "").lower()
