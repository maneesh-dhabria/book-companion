"""Integration tests for summary CRUD operations."""

import pytest
import pytest_asyncio

from app.db.models import Book, BookSection, BookStatus, Summary, SummaryContentType
from app.db.repositories.section_repo import SectionRepository
from app.db.repositories.summary_repo import SummaryRepository


@pytest_asyncio.fixture
async def book_with_sections(db_session):
    """Create a book with 3 sections."""
    book = Book(
        title="Test Book",
        file_data=b"test",
        file_hash="test_hash_summary_crud",
        file_format="epub",
        file_size_bytes=100,
        status=BookStatus.PARSED,
    )
    db_session.add(book)
    await db_session.flush()

    sections = []
    for i in range(3):
        s = BookSection(
            book_id=book.id,
            title=f"Section {i + 1}",
            order_index=i,
            depth=0,
            content_md=f"Content {i + 1} " * 200,
        )
        db_session.add(s)
        sections.append(s)
    await db_session.flush()
    return book, sections


@pytest.mark.asyncio
async def test_summary_append(db_session, book_with_sections):
    book, sections = book_with_sections
    repo = SummaryRepository(db_session)

    s1 = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=sections[0].id,
        book_id=book.id,
        facets_used={
            "style": "bullet_points",
            "audience": "practitioner",
            "compression": "standard",
            "content_focus": "key_concepts",
        },
        prompt_text_sent="test",
        model_used="sonnet",
        input_char_count=1000,
        summary_char_count=200,
        summary_md="Summary 1",
    )
    await repo.create(s1)

    s2 = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=sections[0].id,
        book_id=book.id,
        facets_used={
            "style": "narrative",
            "audience": "academic",
            "compression": "detailed",
            "content_focus": "full_coverage",
        },
        prompt_text_sent="test2",
        model_used="opus",
        input_char_count=1000,
        summary_char_count=300,
        summary_md="Summary 2",
    )
    await repo.create(s2)

    all_summaries = await repo.list_by_content(SummaryContentType.SECTION, sections[0].id)
    assert len(all_summaries) == 2


@pytest.mark.asyncio
async def test_summary_cascade_delete(db_session, book_with_sections):
    """Deleting book cascades to summaries."""
    book, sections = book_with_sections
    repo = SummaryRepository(db_session)

    await repo.create(
        Summary(
            content_type=SummaryContentType.SECTION,
            content_id=sections[0].id,
            book_id=book.id,
            facets_used={},
            prompt_text_sent="t",
            model_used="s",
            input_char_count=100,
            summary_char_count=20,
            summary_md="S",
        )
    )

    await db_session.delete(book)
    await db_session.flush()

    all_summaries = await repo.list_by_book(book.id)
    assert len(all_summaries) == 0


@pytest.mark.asyncio
async def test_set_default_summary(db_session, book_with_sections):
    book, sections = book_with_sections
    summary_repo = SummaryRepository(db_session)
    section_repo = SectionRepository(db_session)

    s = await summary_repo.create(
        Summary(
            content_type=SummaryContentType.SECTION,
            content_id=sections[0].id,
            book_id=book.id,
            facets_used={},
            prompt_text_sent="t",
            model_used="s",
            input_char_count=100,
            summary_char_count=20,
            summary_md="S",
        )
    )

    await section_repo.update_default_summary(sections[0].id, s.id)
    updated = await section_repo.get_by_id(sections[0].id)
    assert updated.default_summary_id == s.id


@pytest.mark.asyncio
async def test_idempotent_skip(db_session, book_with_sections):
    book, sections = book_with_sections
    repo = SummaryRepository(db_session)

    facets = {
        "style": "bullet_points",
        "audience": "practitioner",
        "compression": "standard",
        "content_focus": "key_concepts",
    }

    await repo.create(
        Summary(
            content_type=SummaryContentType.SECTION,
            content_id=sections[0].id,
            book_id=book.id,
            facets_used=facets,
            preset_name="practitioner_bullets",
            prompt_text_sent="t",
            model_used="s",
            input_char_count=100,
            summary_char_count=20,
            summary_md="S",
        )
    )

    existing = await repo.get_latest_by_content_and_facets(
        SummaryContentType.SECTION, sections[0].id, facets
    )
    assert existing is not None


@pytest.mark.asyncio
async def test_list_book_level_summaries(db_session, book_with_sections):
    book, sections = book_with_sections
    repo = SummaryRepository(db_session)

    await repo.create(
        Summary(
            content_type=SummaryContentType.BOOK,
            content_id=book.id,
            book_id=book.id,
            facets_used={},
            prompt_text_sent="t",
            model_used="s",
            input_char_count=100,
            summary_char_count=20,
            summary_md="Book S",
        )
    )
    await repo.create(
        Summary(
            content_type=SummaryContentType.SECTION,
            content_id=sections[0].id,
            book_id=book.id,
            facets_used={},
            prompt_text_sent="t",
            model_used="s",
            input_char_count=100,
            summary_char_count=20,
            summary_md="Section S",
        )
    )

    book_summaries = await repo.list_book_level(book.id)
    assert len(book_summaries) == 1
    assert book_summaries[0].content_type == SummaryContentType.BOOK
