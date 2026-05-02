"""Re-import deletes orphaned AudioFile rows whose section disappeared (FR-26a)."""

from app.db.models import ContentType
from app.db.repositories.audio_file_repo import AudioFileRepository

BASE_KW = dict(
    engine="kokoro",
    duration_seconds=10.0,
    sentence_count=3,
    sentence_offsets=[0.0, 3.0, 6.5],
    source_hash="abc",
    sanitizer_version="1.0",
)


async def test_delete_orphans_skips_surviving_sections(db_session, tmp_path):
    """Repo-level orphan reconciliation — small targeted test instead of a full re-import flow."""
    from app.db.models import Book, BookSection

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
    s1 = BookSection(book_id=b.id, title="S1", order_index=1, content_md="a")
    s2 = BookSection(book_id=b.id, title="S2", order_index=2, content_md="b")
    db_session.add_all([s1, s2])
    await db_session.flush()

    repo = AudioFileRepository(db_session, data_dir=tmp_path)
    af1 = await repo.upsert(
        book_id=b.id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=s1.id,
        voice="af_sarah",
        mp3_bytes=b"X",
        **BASE_KW,
    )
    af2 = await repo.upsert(
        book_id=b.id,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=s2.id,
        voice="af_sarah",
        mp3_bytes=b"Y",
        **BASE_KW,
    )
    af1_path = tmp_path / af1.file_path
    af2_path = tmp_path / af2.file_path
    assert af1_path.exists() and af2_path.exists()

    deleted = await repo.delete_orphans(b.id, surviving_section_ids={s1.id})
    assert deleted == 1
    assert af1_path.exists()
    assert not af2_path.exists()

    survivors = await repo.list_by_book(b.id)
    assert [r.content_id for r in survivors] == [s1.id]
