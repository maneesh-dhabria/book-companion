"""book_service.delete_book unlinks audio files + cleans audio_positions (FR-26)."""

import pytest_asyncio

from app.config import Settings
from app.db.models import Book, BookSection, ContentType
from app.db.repositories.audio_file_repo import AudioFileRepository
from app.db.repositories.audio_position_repo import AudioPositionRepository
from app.services.book_service import BookService

BASE_KW = dict(
    engine="kokoro",
    duration_seconds=10.0,
    sentence_count=3,
    sentence_offsets=[0.0, 3.0, 6.5],
    source_hash="abc",
    sanitizer_version="1.0",
)


@pytest_asyncio.fixture
async def book_service(db_session, tmp_path, monkeypatch) -> BookService:
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    settings = Settings()
    return BookService(db_session, settings)


async def test_delete_book_unlinks_audio_and_positions(db_session, book_service, tmp_path):
    book = Book(
        title="T",
        status="completed",
        file_data=b"\x00",
        file_hash="h",
        file_size_bytes=1,
        file_format="epub",
    )
    db_session.add(book)
    await db_session.flush()
    section = BookSection(book_id=book.id, title="S", order_index=1, content_md="hi")
    db_session.add(section)
    await db_session.flush()

    audio_repo = AudioFileRepository(db_session, data_dir=tmp_path)
    pos_repo = AudioPositionRepository(db_session)

    af = await audio_repo.upsert(
        book_id=book.id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section.id,
        voice="af_sarah",
        mp3_bytes=b"X",
        **BASE_KW,
    )
    abs_path = tmp_path / af.file_path
    assert abs_path.exists()

    await pos_repo.upsert(ContentType.SECTION_SUMMARY, section.id, "browser-X", 5)
    await pos_repo.upsert(ContentType.ANNOTATIONS_PLAYLIST, book.id, "browser-X", 3)
    await db_session.commit()

    await book_service.delete_book(book.id)

    assert not abs_path.exists()
    assert (await audio_repo.list_by_book(book.id)) == []
    assert await pos_repo.get(ContentType.SECTION_SUMMARY, section.id, "browser-X") is None
    assert await pos_repo.get(ContentType.ANNOTATIONS_PLAYLIST, book.id, "browser-X") is None
