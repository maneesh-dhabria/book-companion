"""Integration tests for /audio/sections/by-book and /audio/positions/by-book."""

import json

import pytest

from app.db.models import (
    AudioFile,
    AudioPosition,
    Book,
    BookSection,
    ContentType,
)

_seed_counter = 0


async def _seed_book_with_sections(app, n_sections: int = 3) -> tuple[int, list[int]]:
    global _seed_counter
    _seed_counter += 1
    async with app.state.session_factory() as db:
        b = Book(
            title="Test",
            status="completed",
            file_data=b"\x00",
            file_hash=f"h-by-book-{n_sections}-{_seed_counter}",
            file_size_bytes=1,
            file_format="epub",
        )
        db.add(b)
        await db.flush()
        section_ids = []
        for i in range(n_sections):
            s = BookSection(
                book_id=b.id,
                title=f"Section {i + 1}",
                order_index=i + 1,
                content_md=f"text {i}",
                section_type="chapter",
            )
            db.add(s)
            await db.flush()
            section_ids.append(s.id)
        await db.commit()
        return b.id, section_ids


async def _add_audio_file(app, *, book_id: int, content_id: int, engine: str = "kokoro"):
    async with app.state.session_factory() as db:
        db.add(
            AudioFile(
                book_id=book_id,
                content_type=ContentType.SECTION_SUMMARY.value,
                content_id=content_id,
                voice="default",
                engine=engine,
                file_path=f"audio/{book_id}/{content_id}.mp3",
                file_size_bytes=1,
                duration_seconds=1.0,
                sentence_count=10,
                sentence_offsets_json=json.dumps([]),
                source_hash="h",
                sanitizer_version="v1",
            )
        )
        await db.commit()


async def _add_audio_position(
    app,
    *,
    content_type: ContentType,
    content_id: int,
    sentence_index: int = 1,
):
    async with app.state.session_factory() as db:
        db.add(
            AudioPosition(
                content_type=content_type,
                content_id=content_id,
                browser_id="b1",
                sentence_index=sentence_index,
            )
        )
        await db.commit()


# --- /audio/sections/by-book --------------------------------------------------


@pytest.mark.asyncio
async def test_sections_by_book_returns_404_for_unknown_book(client):
    resp = await client.get("/api/v1/audio/sections/by-book/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sections_by_book_marks_only_seeded_sections(client, app):
    book_id, section_ids = await _seed_book_with_sections(app, n_sections=3)
    await _add_audio_file(app, book_id=book_id, content_id=section_ids[1])

    resp = await client.get(f"/api/v1/audio/sections/by-book/{book_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["book_id"] == book_id
    assert len(data["sections"]) == 3
    by_id = {e["section_id"]: e for e in data["sections"]}
    assert by_id[section_ids[0]]["has_mp3"] is False
    assert by_id[section_ids[1]]["has_mp3"] is True
    assert by_id[section_ids[1]]["engine"] == "kokoro"
    assert by_id[section_ids[2]]["has_mp3"] is False


# --- /audio/positions/by-book -------------------------------------------------


@pytest.mark.asyncio
async def test_positions_by_book_returns_404_when_none(client, app):
    book_id, _section_ids = await _seed_book_with_sections(app, n_sections=1)
    resp = await client.get(f"/api/v1/audio/positions/by-book/{book_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_positions_by_book_returns_section_summary(client, app):
    book_id, section_ids = await _seed_book_with_sections(app, n_sections=2)
    await _add_audio_position(
        app,
        content_type=ContentType.SECTION_SUMMARY,
        content_id=section_ids[0],
        sentence_index=7,
    )
    resp = await client.get(f"/api/v1/audio/positions/by-book/{book_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_type"] == ContentType.SECTION_SUMMARY.value
    assert data["content_id"] == section_ids[0]
    assert data["sentence_index"] == 7


@pytest.mark.asyncio
async def test_positions_by_book_excludes_other_books(client, app):
    book_a, sec_a = await _seed_book_with_sections(app, n_sections=1)
    book_b, sec_b = await _seed_book_with_sections(app, n_sections=1)
    await _add_audio_position(app, content_type=ContentType.SECTION_SUMMARY, content_id=sec_b[0])
    resp = await client.get(f"/api/v1/audio/positions/by-book/{book_a}")
    assert resp.status_code == 404
