"""AudioPositionRepository tests."""

import asyncio

import pytest_asyncio

from app.db.models import Book, BookSection, ContentType
from app.db.repositories.audio_position_repo import AudioPositionRepository


@pytest_asyncio.fixture
async def repo(db_session) -> AudioPositionRepository:
    return AudioPositionRepository(db_session)


async def _seed_book_and_section(db_session) -> tuple[int, int]:
    b = Book(
        title="T",
        status="completed",
        file_data=b"\x00",
        file_hash="h",
        file_size_bytes=1,
        file_format="epub",
    )
    db_session.add(b)
    await db_session.flush()
    s = BookSection(book_id=b.id, title="S", order_index=1, content_md="hello")
    db_session.add(s)
    await db_session.flush()
    return b.id, s.id


async def test_upsert_inserts_then_updates(repo):
    landed1 = await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 5)
    await asyncio.sleep(0.6)
    landed2 = await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 10)
    pos = await repo.get(ContentType.SECTION_SUMMARY, 42, "browser-A")
    assert landed1 is True
    assert landed2 is True
    assert pos.sentence_index == 10


async def test_debounce_drops_writes_within_window(repo):
    landed1 = await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 5)
    landed2 = await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 6)
    await asyncio.sleep(0.6)
    landed3 = await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 7)
    pos = await repo.get(ContentType.SECTION_SUMMARY, 42, "browser-A")
    assert landed1 is True
    assert landed2 is False
    assert landed3 is True
    assert pos.sentence_index == 7


async def test_get_with_hint_flags_other_browser(repo):
    await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 10)
    await asyncio.sleep(0.6)
    await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-B", 25)
    hint = await repo.get_with_hint(ContentType.SECTION_SUMMARY, 42, "browser-A")
    assert hint is not None
    assert hint.sentence_index == 10
    assert hint.has_other_browser is True
    assert hint.other_browser_updated_at is not None


async def test_cleanup_for_book_removes_section_positions(db_session, repo):
    book_id, section_id = await _seed_book_and_section(db_session)
    await repo.upsert(ContentType.SECTION_SUMMARY, section_id, "b", 1)
    await asyncio.sleep(0.6)
    await repo.upsert(ContentType.ANNOTATIONS_PLAYLIST, book_id, "b", 3)
    await db_session.commit()

    deleted = await repo.cleanup_for_book(book_id)
    assert deleted >= 2
    assert await repo.get(ContentType.SECTION_SUMMARY, section_id, "b") is None
    assert await repo.get(ContentType.ANNOTATIONS_PLAYLIST, book_id, "b") is None
