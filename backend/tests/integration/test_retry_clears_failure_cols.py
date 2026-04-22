"""FR-C4.3 — successful summarization clears the section's failure cols."""

import uuid

import pytest
import pytest_asyncio
import sqlalchemy as sa

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


class FixedLLM:
    async def generate(self, prompt, model=None, **kw):
        return _Response("stub summary bullet point. " * 10)


async def _mk_book(db, *, title="T"):
    book = Book(
        title=title,
        file_data=b"x",
        file_hash=f"h-{uuid.uuid4()}",
        file_format="epub",
        file_size_bytes=1,
        status=BookStatus.PARSED,
    )
    db.add(book)
    await db.flush()
    section = BookSection(
        book_id=book.id,
        title="C0",
        order_index=0,
        depth=1,
        section_type="chapter",
        content_md="Section content " * 200,
    )
    db.add(section)
    await db.flush()
    await db.commit()
    return book.id, section.id


@pytest_asyncio.fixture
async def failed_section(db_session):
    book_id, section_id = await _mk_book(db_session)
    # Seed a prior failure.
    await db_session.execute(
        sa.text(
            "UPDATE book_sections "
            "SET last_failure_type='cli_timeout', "
            "    last_failure_message='previous boom', "
            "    attempt_count=2 "
            "WHERE id = :id"
        ),
        {"id": section_id},
    )
    await db_session.commit()
    return book_id, section_id


@pytest.mark.asyncio
async def test_successful_retry_clears_failure_cols(
    db_session, test_settings, failed_section
):
    book_id, section_id = failed_section
    llm = FixedLLM()
    service = SummarizerService(db_session, llm, test_settings)
    result = await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        scope="section",
        section_id=section_id,
    )
    assert result["completed"] == 1

    row = (
        await db_session.execute(
            sa.select(BookSection).where(BookSection.id == section_id)
        )
    ).scalar_one()
    assert row.last_failure_type is None
    assert row.last_failure_message is None
    # attempt_count stays monotonic (was 2, incremented once before this call).
    assert row.attempt_count == 3
    assert row.last_preset_used is not None
