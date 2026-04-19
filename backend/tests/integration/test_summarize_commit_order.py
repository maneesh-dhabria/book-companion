"""Regression (live-verify bug): on_section_complete must fire AFTER db.commit().

Previously the service invoked the completion callback *before* committing the
new Summary row. Because the SSE handler in processing.py immediately publishes
the event downstream, the frontend's refetch of the section via a separate
session saw the pre-commit state (`has_summary=False`), leaving the reader UI
stuck on the "Not yet summarized" empty state even though the backend had just
generated a summary. Surfaced by Playwright end-to-end walkthrough against a
live Claude CLI.
"""

import sqlite3
import uuid

import pytest
import pytest_asyncio

from app.db.models import Book, BookSection, BookStatus
from app.services.summarizer.summarizer_service import SummarizerService

_FACETS = {
    "style": "bullet_points",
    "audience": "practitioner",
    "compression": "standard",
    "content_focus": "key_concepts",
}


class _Response:
    def __init__(self, content: str):
        self.content = content
        self.input_tokens = 10
        self.output_tokens = 10


class StubLLM:
    async def generate(self, prompt, model=None, **kw):
        return _Response("stub summary bullet point. " * 10)


@pytest_asyncio.fixture
async def one_chapter_book(db_session):
    book = Book(
        title="T",
        file_data=b"x",
        file_hash=f"h-{uuid.uuid4()}",
        file_format="epub",
        file_size_bytes=1,
        status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()
    section = BookSection(
        book_id=book.id,
        title="Chapter 1",
        order_index=0,
        depth=1,
        section_type="chapter",
        content_md=("Section content " * 200),
    )
    db_session.add(section)
    await db_session.flush()
    await db_session.commit()
    return book.id, section.id


@pytest.mark.asyncio
async def test_on_section_complete_fires_after_commit(
    one_chapter_book, db_session, test_db_path, test_settings
):
    """At the moment on_section_complete fires, a *separate* database connection
    (simulating the FastAPI request that the frontend makes after receiving the
    SSE event) must already see the committed Summary + default_summary_id.
    """
    book_id, section_id = one_chapter_book

    observations: list[dict] = []

    def on_complete(sid, index, total, title, elapsed=None, comp=None):
        # Open a raw sqlite3 connection — no asyncio, no shared session — and
        # check whether the Summary + default_summary_id are visible.
        conn = sqlite3.connect(str(test_db_path))
        try:
            sum_count = conn.execute(
                "SELECT count(*) FROM summaries "
                "WHERE content_type = 'section' AND content_id = ?",
                (sid,),
            ).fetchone()[0]
            default_id = conn.execute(
                "SELECT default_summary_id FROM book_sections WHERE id = ?",
                (sid,),
            ).fetchone()[0]
        finally:
            conn.close()
        observations.append(
            {"summaries_visible": sum_count, "default_summary_id": default_id}
        )

    service = SummarizerService(db_session, StubLLM(), test_settings)
    await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        on_section_complete=on_complete,
    )

    assert len(observations) == 1, "callback fired exactly once"
    assert observations[0]["summaries_visible"] == 1, (
        "Summary row must be visible to a fresh connection before on_section_complete "
        "fires — otherwise the frontend's SSE-driven refetch races the write."
    )
    assert observations[0]["default_summary_id"] is not None, (
        "default_summary_id must be populated before on_section_complete fires."
    )
