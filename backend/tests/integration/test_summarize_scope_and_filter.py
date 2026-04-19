"""FR-25, FR-26, FR-27, FR-27a: summarizer scope filter + type gate."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models import Book, BookSection, BookStatus, Summary, SummaryContentType
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
    def __init__(self):
        self.call_count = 0

    async def generate(self, prompt, model=None, **kw):
        self.call_count += 1
        return _Response("stub summary bullet point. " * 10)


async def _mk_book(
    db, sections: list[tuple[str, str]], *, title: str = "T"
) -> tuple[int, list[int]]:
    import uuid

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
    ids: list[int] = []
    for i, (title, st) in enumerate(sections):
        s = BookSection(
            book_id=book.id,
            title=title,
            order_index=i,
            depth=1,
            section_type=st,
            content_md=("Section content " * 200),
        )
        db.add(s)
        await db.flush()
        ids.append(s.id)
    await db.commit()
    return book.id, ids


@pytest_asyncio.fixture
async def five_chapter_book(db_session):
    return await _mk_book(db_session, [(f"C{i}", "chapter") for i in range(5)])


@pytest_asyncio.fixture
async def mixed_book(db_session):
    # 3 chapters + 2 copyright sections
    sections = [
        ("Copyright A", "copyright"),
        ("Ch1", "chapter"),
        ("Ch2", "chapter"),
        ("Copyright B", "copyright"),
        ("Ch3", "chapter"),
    ]
    return await _mk_book(db_session, sections)


@pytest.mark.asyncio
async def test_scope_pending_skips_already_summarized(
    db_session, test_settings, five_chapter_book
):
    book_id, section_ids = five_chapter_book
    llm = StubLLM()
    service = SummarizerService(db_session, llm, test_settings)

    # First pass: summarize first 2 sections via scope=section
    for sid in section_ids[:2]:
        await service.summarize_book(
            book_id=book_id,
            facets=_FACETS,
            skip_eval=True,
            scope="section",
            section_id=sid,
        )
    assert llm.call_count == 2

    # Now scope=pending should summarize the remaining 3
    llm2 = StubLLM()
    service2 = SummarizerService(db_session, llm2, test_settings)
    result = await service2.summarize_book(
        book_id=book_id, facets=_FACETS, skip_eval=True, scope="pending"
    )
    assert result["completed"] == 3
    assert llm2.call_count == 3


@pytest.mark.asyncio
async def test_scope_section_summarizes_only_that_section(
    db_session, test_settings, five_chapter_book
):
    book_id, section_ids = five_chapter_book
    target = section_ids[2]
    llm = StubLLM()
    service = SummarizerService(db_session, llm, test_settings)
    result = await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        scope="section",
        section_id=target,
    )
    assert result["completed"] == 1
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_scope_section_wrong_book_raises(db_session, test_settings):
    book_a_id, _ = await _mk_book(db_session, [("A", "chapter")])
    _, (foreign_id,) = await _mk_book(db_session, [("Foreign", "chapter")])
    llm = StubLLM()
    service = SummarizerService(db_session, llm, test_settings)
    with pytest.raises(ValueError, match="does not belong"):
        await service.summarize_book(
            book_id=book_a_id,
            facets=_FACETS,
            skip_eval=True,
            scope="section",
            section_id=foreign_id,
        )


@pytest.mark.asyncio
async def test_all_scope_skips_frontmatter(
    db_session, test_settings, mixed_book
):
    book_id, _ = mixed_book
    llm = StubLLM()
    service = SummarizerService(db_session, llm, test_settings)
    result = await service.summarize_book(
        book_id=book_id, facets=_FACETS, skip_eval=True, scope="all"
    )
    assert result["completed"] == 3
    assert llm.call_count == 3


@pytest.mark.asyncio
async def test_section_scope_bypasses_type_gate(
    db_session, test_settings, mixed_book
):
    book_id, section_ids = mixed_book
    # section_ids[0] is the first copyright section
    llm = StubLLM()
    service = SummarizerService(db_session, llm, test_settings)
    result = await service.summarize_book(
        book_id=book_id,
        facets=_FACETS,
        skip_eval=True,
        scope="section",
        section_id=section_ids[0],
    )
    assert result["completed"] == 1
    # Verify summary was actually written for the copyright section
    rows = (
        (
            await db_session.execute(
                select(Summary).where(
                    Summary.content_type == SummaryContentType.SECTION,
                    Summary.content_id == section_ids[0],
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
