"""Incremental commit behavior for SummarizerService.summarize_book()."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Book, BookSection, BookStatus, Summary, SummaryContentType
from app.services.summarizer.summarizer_service import SummarizerService

_STANDARD_FACETS = {
    "style": "bullet_points",
    "audience": "practitioner",
    "compression": "standard",
    "content_focus": "key_concepts",
}


@pytest_asyncio.fixture
async def three_section_book(db_session):
    book = Book(
        title="T",
        file_data=b"x",
        file_hash="h1",
        file_format="epub",
        file_size_bytes=1,
        status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()
    for i in range(3):
        db_session.add(
            BookSection(
                book_id=book.id,
                title=f"S{i}",
                order_index=i,
                depth=1,
                content_md=("Section content " * 200),
            )
        )
    await db_session.commit()
    return book


class _Response:
    def __init__(self, content: str):
        self.content = content
        self.input_tokens = 10
        self.output_tokens = 10


class StubLLM:
    def __init__(self):
        self.call_count = 0

    async def generate(self, prompt, model=None, **kw):
        self.call_count += 1
        return _Response("stub summary bullet point. " * 10)


class FailingOnSecondLLM:
    def __init__(self):
        self.call_count = 0

    async def generate(self, prompt, model=None, **kw):
        self.call_count += 1
        if self.call_count == 2:
            raise RuntimeError("simulated mid-run failure")
        return _Response("stub summary bullet point. " * 10)


def _fresh_session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory()


@pytest.mark.asyncio
async def test_summarize_commits_each_section(
    three_section_book, db_session, engine, test_settings
):
    service = SummarizerService(db_session, StubLLM(), test_settings)
    result = await service.summarize_book(
        three_section_book.id, facets=_STANDARD_FACETS, skip_eval=True
    )
    assert result["completed"] == 3

    # Fresh session in a separate transaction proves commits happened
    async with _fresh_session(engine) as fresh:
        rows = (
            (
                await fresh.execute(
                    select(Summary).where(Summary.content_type == SummaryContentType.SECTION)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_summarize_skips_already_summarized_on_rerun(
    three_section_book, db_session, test_settings
):
    llm = StubLLM()
    service = SummarizerService(db_session, llm, test_settings)
    r1 = await service.summarize_book(
        three_section_book.id, facets=_STANDARD_FACETS, skip_eval=True
    )
    assert r1["completed"] == 3
    calls_after_first = llm.call_count

    r2 = await service.summarize_book(
        three_section_book.id, facets=_STANDARD_FACETS, skip_eval=True
    )
    assert r2["skipped"] >= 3
    assert r2["completed"] == 0
    assert llm.call_count == calls_after_first, "no new LLM calls on re-run"


@pytest.mark.asyncio
async def test_summarize_partial_failure_preserves_earlier_sections(
    three_section_book, db_session, engine, test_settings
):
    service = SummarizerService(db_session, FailingOnSecondLLM(), test_settings)
    result = await service.summarize_book(
        three_section_book.id, facets=_STANDARD_FACETS, skip_eval=True
    )

    async with _fresh_session(engine) as fresh:
        rows = (
            (
                await fresh.execute(
                    select(Summary).where(Summary.content_type == SummaryContentType.SECTION)
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) >= 1, "section 1 must be committed despite later failure"
    assert result["failed"], "summarize_book must report the failure"
