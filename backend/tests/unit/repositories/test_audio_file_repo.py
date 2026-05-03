"""AudioFileRepository tests."""

from pathlib import Path

import pytest_asyncio

from app.db.models import AudioFile, Book, ContentType
from app.db.repositories.audio_file_repo import AudioFileRepository

BASE_KW = dict(
    engine="kokoro",
    duration_seconds=10.0,
    sentence_count=3,
    sentence_offsets=[0.0, 3.0, 6.5],
    source_hash="abc",
    sanitizer_version="1.0",
)


async def _seed_book(db_session) -> int:
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
    return b.id


@pytest_asyncio.fixture
async def repo(db_session, tmp_path) -> AudioFileRepository:
    return AudioFileRepository(db_session, data_dir=tmp_path)


async def test_upsert_creates_row_and_writes_file(db_session, repo, tmp_path: Path):
    book_id = await _seed_book(db_session)
    af = await repo.upsert(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
        mp3_bytes=b"ID3hello",
        **BASE_KW,
    )
    assert (tmp_path / af.file_path).read_bytes() == b"ID3hello"
    assert af.file_size_bytes == 8
    assert af.sentence_count == 3


async def test_upsert_replaces_existing_row(db_session, repo, tmp_path: Path):
    book_id = await _seed_book(db_session)
    af1 = await repo.upsert(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
        mp3_bytes=b"OLD",
        **BASE_KW,
    )
    af2 = await repo.upsert(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
        mp3_bytes=b"NEW",
        **BASE_KW,
    )
    assert af2.id == af1.id
    assert (tmp_path / af2.file_path).read_bytes() == b"NEW"


async def test_list_by_book(db_session, repo):
    book_id = await _seed_book(db_session)
    for cid in (10, 20, 30):
        await repo.upsert(
            book_id=book_id,
            content_type=ContentType.SECTION_SUMMARY,
            content_id=cid,
            voice="af_sarah",
            mp3_bytes=b"X",
            **BASE_KW,
        )
    rows = await repo.list_by_book(book_id)
    assert [r.content_id for r in rows] == [10, 20, 30]


async def test_delete_all_for_book_unlinks_files(db_session, repo, tmp_path: Path):
    book_id = await _seed_book(db_session)
    af = await repo.upsert(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
        mp3_bytes=b"X",
        **BASE_KW,
    )
    path = tmp_path / af.file_path
    assert path.exists()
    deleted = await repo.delete_all_for_book(book_id)
    assert deleted == 1
    assert not path.exists()


async def test_delete_one_unlinks_single(db_session, repo, tmp_path: Path):
    book_id = await _seed_book(db_session)
    af = await repo.upsert(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
        mp3_bytes=b"X",
        **BASE_KW,
    )
    deleted = await repo.delete_one(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
    )
    assert deleted == 1
    assert not (tmp_path / af.file_path).exists()


async def test_lookup_returns_row(db_session, repo):
    book_id = await _seed_book(db_session)
    await repo.upsert(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
        mp3_bytes=b"X",
        **BASE_KW,
    )
    found = await repo.lookup(
        book_id=book_id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=42,
        voice="af_sarah",
    )
    assert found is not None
    assert isinstance(found, AudioFile)
