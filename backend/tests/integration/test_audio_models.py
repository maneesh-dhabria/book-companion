"""ORM round-trip tests for AudioFile + AudioPosition."""

from app.db.models import (
    AudioFile,
    AudioPosition,
    ContentType,
)


async def _seed_book(db_session) -> int:
    from app.db.models import Book

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
    return book.id


async def test_audio_file_persist_round_trip(db_session):
    book_id = await _seed_book(db_session)
    af = AudioFile(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
        engine="kokoro",
        file_path="audio/1/section_summary_42__af_sarah.mp3",
        file_size_bytes=4_410_000,
        duration_seconds=367.4,
        sentence_count=47,
        sentence_offsets_json="[0.0, 4.2]",
        source_hash="ab3c",
        sanitizer_version="1.0",
    )
    db_session.add(af)
    await db_session.commit()
    loaded = await db_session.get(AudioFile, af.id)
    assert loaded.duration_seconds == 367.4
    assert loaded.sentence_count == 47
    assert loaded.engine == "kokoro"


async def test_audio_position_pk_composite(db_session):
    pos = AudioPosition(
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        browser_id="abc-uuid",
        sentence_index=16,
    )
    db_session.add(pos)
    await db_session.commit()
    loaded = await db_session.get(AudioPosition, (ContentType.SECTION_SUMMARY, 42, "abc-uuid"))
    assert loaded.sentence_index == 16
