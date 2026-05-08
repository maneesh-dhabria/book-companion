"""ReadingStateRepository tests — focused on front-matter filtering (FR-B05a)."""

import asyncio

import pytest_asyncio

from app.db.models import Book, BookSection
from app.db.repositories.reading_state_repo import ReadingStateRepository


@pytest_asyncio.fixture
async def repo(db_session) -> ReadingStateRepository:
    return ReadingStateRepository(db_session)


async def _seed_book_with_two_sections(
    db_session, *, fm_type: str = "copyright", chapter_type: str = "chapter"
) -> tuple[int, int, int]:
    """Seed a book with one front-matter section and one chapter section.

    Returns (book_id, fm_section_id, chapter_section_id).
    """
    b = Book(
        title="Sample",
        status="completed",
        file_data=b"\x00",
        file_hash=f"h-{fm_type}-{chapter_type}",
        file_size_bytes=1,
        file_format="epub",
    )
    db_session.add(b)
    await db_session.flush()

    fm = BookSection(
        book_id=b.id,
        title="Copyright",
        order_index=1,
        content_md="(c) 2026",
        section_type=fm_type,
    )
    chapter = BookSection(
        book_id=b.id,
        title="Chapter 1",
        order_index=2,
        content_md="It begins…",
        section_type=chapter_type,
    )
    db_session.add_all([fm, chapter])
    await db_session.flush()
    return b.id, fm.id, chapter.id


async def test_continue_skips_front_matter(repo, db_session):
    """When a more-recent reader_position points at a copyright section,
    /continue should fall back to the next-most-recent non-front-matter row."""
    book_id, fm_id, chapter_id = await _seed_book_with_two_sections(db_session)

    # Older row: chapter (valid).
    await repo.upsert(
        user_agent="ua-A", book_id=book_id, section_id=chapter_id, content_mode="summary"
    )
    await db_session.commit()
    await asyncio.sleep(1.1)  # SQLite CURRENT_TIMESTAMP has 1s resolution.

    # Newer row from a different device: copyright (front-matter; should be skipped).
    await repo.upsert(user_agent="ua-B", book_id=book_id, section_id=fm_id, content_mode="summary")
    await db_session.commit()

    # Querying from a third device: should NOT return the copyright row.
    rs = await repo.get_latest_other_device("ua-C")
    assert rs is not None
    assert rs.section_id == chapter_id
    assert rs.user_agent == "ua-A"


async def test_continue_returns_none_when_only_front_matter(repo, db_session):
    """If every reading_position points at front-matter, return None
    (route serializes to all-null ReadingStateResponse)."""
    book_id, fm_id, _chapter_id = await _seed_book_with_two_sections(db_session)

    await repo.upsert(user_agent="ua-A", book_id=book_id, section_id=fm_id, content_mode="summary")
    await db_session.commit()

    rs = await repo.get_latest_other_device("ua-B")
    assert rs is None


async def test_resume_banner_reading_picks_latest_across_devices(repo, db_session):
    """`get_latest_resume_banner_reading` does NOT exclude any user_agent — it
    returns the single most-recent reading_state across all browsers, skipping
    front-matter rows."""
    book_id, _fm_id, chapter_id = await _seed_book_with_two_sections(db_session)

    await repo.upsert(user_agent="ua-A", book_id=book_id, section_id=chapter_id)
    await db_session.commit()
    await asyncio.sleep(1.1)
    await repo.upsert(user_agent="ua-B", book_id=book_id, section_id=chapter_id)
    await db_session.commit()

    rs = await repo.get_latest_resume_banner_reading()
    assert rs is not None
    assert rs.user_agent == "ua-B"


async def test_resume_banner_reading_skips_front_matter(repo, db_session):
    book_id, fm_id, chapter_id = await _seed_book_with_two_sections(db_session)

    await repo.upsert(user_agent="ua-A", book_id=book_id, section_id=chapter_id)
    await db_session.commit()
    await asyncio.sleep(1.1)
    await repo.upsert(user_agent="ua-B", book_id=book_id, section_id=fm_id)
    await db_session.commit()

    rs = await repo.get_latest_resume_banner_reading()
    assert rs is not None
    assert rs.section_id == chapter_id


async def test_resume_banner_reading_returns_none_when_empty(repo):
    rs = await repo.get_latest_resume_banner_reading()
    assert rs is None


async def test_continue_includes_rows_with_null_section_id(repo, db_session):
    """A reader_position with no section_id (book-level resume) is NOT a front-matter
    row and should still appear in /continue results."""
    b = Book(
        title="No-section book",
        status="completed",
        file_data=b"\x00",
        file_hash="h-null-section",
        file_size_bytes=1,
        file_format="epub",
    )
    db_session.add(b)
    await db_session.flush()

    await repo.upsert(user_agent="ua-A", book_id=b.id, section_id=None, content_mode="summary")
    await db_session.commit()

    rs = await repo.get_latest_other_device("ua-B")
    assert rs is not None
    assert rs.book_id == b.id
    assert rs.section_id is None
