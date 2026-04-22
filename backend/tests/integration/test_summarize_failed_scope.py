"""FR-A5.0 / FR-A5.2 / FR-A5.3 / FR-A4.5 — scope=failed + atomic preset +
empty-output rejection."""

import uuid

import pytest
import pytest_asyncio
import sqlalchemy as sa

from app.db.models import Book, BookSection, BookStatus
from app.exceptions import EmptySummaryError, SubprocessNonZeroExitError
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


class EmptyLLM:
    async def generate(self, prompt, model=None, **kw):
        return _Response("")


class CrashyLLM:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt, model=None, **kw):
        self.calls += 1
        raise SubprocessNonZeroExitError(returncode=1, stderr_truncated="boom")


class FixedLLM:
    async def generate(self, prompt, model=None, **kw):
        return _Response("stub summary bullet point. " * 10)


async def _mk_book(db, sections, title="T"):
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
    ids = []
    for i, st in enumerate(sections):
        s = BookSection(
            book_id=book.id,
            title=f"C{i}",
            order_index=i,
            depth=1,
            section_type=st,
            content_md="Section content " * 200,
        )
        db.add(s)
        await db.flush()
        ids.append(s.id)
    await db.commit()
    return book.id, ids


@pytest_asyncio.fixture
async def three_chapter_book(db_session):
    return await _mk_book(db_session, ["chapter", "chapter", "chapter"])


@pytest.mark.asyncio
async def test_last_preset_used_persists_before_subprocess(
    db_session, test_settings, three_chapter_book
):
    """Even when the LLM subprocess crashes, last_preset_used and
    attempt_count must already be committed (FR-A5.0)."""
    book_id, section_ids = three_chapter_book
    target = section_ids[0]
    llm = CrashyLLM()
    service = SummarizerService(db_session, llm, test_settings)

    result = await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        scope="section",
        section_id=target,
        preset_name="executive_brief",
    )
    assert target in result["failed"]

    row = (
        await db_session.execute(
            sa.select(BookSection).where(BookSection.id == target)
        )
    ).scalar_one()
    assert row.last_preset_used == "executive_brief"
    assert row.attempt_count == 1
    assert row.last_failure_type == "cli_nonzero_exit"
    assert row.last_failure_message and "boom" in row.last_failure_message.lower()


@pytest.mark.asyncio
async def test_empty_summary_rejected_as_failure(
    db_session, test_settings, three_chapter_book
):
    """Empty LLM output must raise EmptySummaryError, leave no Summary row,
    and stamp last_failure_type='empty_output'."""
    from app.db.models import Summary, SummaryContentType

    book_id, section_ids = three_chapter_book
    target = section_ids[1]
    service = SummarizerService(db_session, EmptyLLM(), test_settings)
    result = await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        scope="section",
        section_id=target,
    )
    assert target in result["failed"]
    summaries = (
        await db_session.execute(
            sa.select(Summary).where(
                Summary.content_type == SummaryContentType.SECTION,
                Summary.content_id == target,
            )
        )
    ).scalars().all()
    assert summaries == []

    row = (
        await db_session.execute(
            sa.select(BookSection).where(BookSection.id == target)
        )
    ).scalar_one()
    assert row.last_failure_type == "empty_output"


@pytest.mark.asyncio
async def test_scope_failed_picks_only_failed_sections(
    db_session, test_settings
):
    """After one section fails, scope=failed retries only that section."""
    book_id, section_ids = await _mk_book(
        db_session, ["chapter", "chapter", "chapter"]
    )

    # Seed last_failure_type on one section to simulate a prior failed run.
    failed_target = section_ids[1]
    await db_session.execute(
        sa.text(
            "UPDATE book_sections SET last_failure_type='cli_timeout', "
            "last_failure_message='previous' WHERE id = :id"
        ),
        {"id": failed_target},
    )
    await db_session.commit()

    llm = FixedLLM()
    service = SummarizerService(db_session, llm, test_settings)
    result = await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        scope="failed",
    )
    assert result["completed"] == 1
    # Only one section was eligible.
    row = (
        await db_session.execute(
            sa.select(BookSection).where(BookSection.id == failed_target)
        )
    ).scalar_one()
    # Service writes a Summary, so default_summary_id is set. T9 will clear
    # last_failure_* on success; this test only asserts scope filtering.
    assert row.default_summary_id is not None


@pytest.mark.asyncio
async def test_emptysummaryerror_is_summarization_error():
    """Typed error invariants."""
    err = EmptySummaryError("x")
    assert err.failure_type == "empty_output"
