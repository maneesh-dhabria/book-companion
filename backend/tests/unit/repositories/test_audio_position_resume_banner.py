"""Resume-banner-specific tests for AudioPositionRepository (FR-B05, §9.1)."""

import asyncio
from datetime import UTC, datetime

import pytest_asyncio

from app.db.models import AudioFile, AudioPosition, Book, BookSection, ContentType
from app.db.repositories.audio_position_repo import AudioPositionRepository


@pytest_asyncio.fixture
async def repo(db_session) -> AudioPositionRepository:
    return AudioPositionRepository(db_session)


async def _seed_book_with_section(db_session, hash_suffix: str = "") -> tuple[Book, BookSection]:
    b = Book(
        title=f"Book {hash_suffix}",
        status="completed",
        file_data=b"\x00",
        file_hash=f"h-{hash_suffix or datetime.now(UTC).timestamp()}",
        file_size_bytes=1,
        file_format="epub",
    )
    db_session.add(b)
    await db_session.flush()
    s = BookSection(
        book_id=b.id,
        title="Chapter 3: Vision",
        order_index=1,
        content_md="content",
        section_type="chapter",
    )
    db_session.add(s)
    await db_session.flush()
    return b, s


async def test_resume_banner_returns_none_when_no_audio(repo):
    assert await repo.get_latest_resume_banner() is None


async def test_resume_banner_returns_section_summary_with_book_join(repo, db_session):
    book, section = await _seed_book_with_section(db_session, "S")
    db_session.add(
        AudioPosition(
            content_type=ContentType.SECTION_SUMMARY,
            content_id=section.id,
            browser_id="b1",
            sentence_index=12,
        )
    )
    await db_session.commit()

    out = await repo.get_latest_resume_banner()
    assert out is not None
    assert out.content_type == ContentType.SECTION_SUMMARY.value
    assert out.content_id == section.id
    assert out.book_id == book.id
    assert out.book_title == book.title
    assert out.section_title == "Chapter 3: Vision"
    assert out.sentence_index == 12
    assert out.total_sentences is None  # no audio_files row seeded


async def test_resume_banner_excludes_annotations_playlist(repo, db_session):
    book, section = await _seed_book_with_section(db_session, "P")
    # Playlist row is newer; should NOT win.
    db_session.add(
        AudioPosition(
            content_type=ContentType.SECTION_SUMMARY,
            content_id=section.id,
            browser_id="b1",
            sentence_index=5,
        )
    )
    await db_session.commit()
    await asyncio.sleep(1.1)
    db_session.add(
        AudioPosition(
            content_type=ContentType.ANNOTATIONS_PLAYLIST,
            content_id=book.id,
            browser_id="b2",
            sentence_index=3,
        )
    )
    await db_session.commit()

    out = await repo.get_latest_resume_banner()
    assert out is not None
    assert out.content_type == ContentType.SECTION_SUMMARY.value
    assert out.sentence_index == 5


async def test_resume_banner_book_summary_resolves_book_directly(repo, db_session):
    book, _section = await _seed_book_with_section(db_session, "BS")
    db_session.add(
        AudioPosition(
            content_type=ContentType.BOOK_SUMMARY,
            content_id=book.id,
            browser_id="b1",
            sentence_index=2,
        )
    )
    await db_session.commit()

    out = await repo.get_latest_resume_banner()
    assert out is not None
    assert out.content_type == ContentType.BOOK_SUMMARY.value
    assert out.book_id == book.id
    assert out.book_title == book.title
    assert out.section_title is None


async def test_resume_banner_includes_total_sentences_from_audio_files(repo, db_session):
    book, section = await _seed_book_with_section(db_session, "TS")
    db_session.add(
        AudioPosition(
            content_type=ContentType.SECTION_SUMMARY,
            content_id=section.id,
            browser_id="b1",
            sentence_index=4,
        )
    )
    db_session.add(
        AudioFile(
            book_id=book.id,
            content_type=ContentType.SECTION_SUMMARY.value,
            content_id=section.id,
            voice="default",
            engine="kokoro",
            file_path="audio/x.mp3",
            file_size_bytes=1,
            duration_seconds=1.0,
            sentence_count=42,
            sentence_offsets_json="[]",
            source_hash="h",
            sanitizer_version="v1",
        )
    )
    await db_session.commit()

    out = await repo.get_latest_resume_banner()
    assert out is not None
    assert out.total_sentences == 42
