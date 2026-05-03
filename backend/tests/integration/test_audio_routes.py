"""Integration tests for B7–B16 audio HTTP routes."""

from __future__ import annotations

import shutil

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db.models import (
    AudioFile,
    Base,
    Book,
    BookSection,
    BookStatus,
    ContentType,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
    Summary,
    SummaryContentType,
)


@pytest_asyncio.fixture
async def app_with_data(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")

    # Reset cached settings + main app
    import app.api.deps as deps_mod

    deps_mod._settings = None

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(eng, expire_on_commit=False)

    async with sm() as session:
        book = Book(
            title="TestBook",
            file_data=b"\x00",
            file_hash="h",
            file_format="epub",
            file_size_bytes=1,
            status=BookStatus.COMPLETED,
        )
        session.add(book)
        await session.flush()
        section = BookSection(
            book_id=book.id,
            title="Ch1",
            content_md="Section content body. Two sentences here.",
            order_index=0,
        )
        session.add(section)
        await session.flush()
        summary = Summary(
            book_id=book.id,
            content_type=SummaryContentType.SECTION,
            content_id=section.id,
            preset_name="x",
            facets_used={},
            prompt_text_sent="p",
            model_used="m",
            input_char_count=10,
            summary_char_count=20,
            summary_md="A summary. Of two sentences.",
        )
        session.add(summary)
        await session.flush()
        section.default_summary_id = summary.id
        await session.commit()
        book_id = book.id
        section_id = section.id

    # Build a FastAPI app whose lifespan is a no-op (skip queue worker etc.)
    from fastapi import FastAPI

    from app.api.deps import get_db
    from app.api.routes import audio, audio_position, settings, spikes

    app = FastAPI()
    app.state.session_factory = sm
    app.state.event_bus = None
    app.state.tts_warm = False
    app.state.settings = Settings()

    async def _get_db():
        async with sm() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    app.include_router(audio.router)
    app.include_router(audio_position.router)
    app.include_router(spikes.router)
    app.include_router(settings.router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        yield ac, sm, book_id, section_id, tmp_path


@pytest.mark.asyncio
async def test_post_audio_400_for_web_speech(app_with_data):
    ac, _, book_id, _, _ = app_with_data
    r = await ac.post(
        f"/api/v1/books/{book_id}/audio",
        json={"scope": "all", "voice": "af_sarah", "engine": "web-speech"},
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_post_audio_503_when_ffmpeg_missing(app_with_data, monkeypatch):
    ac, _, book_id, _, _ = app_with_data
    monkeypatch.setattr(shutil, "which", lambda c: None)
    r = await ac.post(
        f"/api/v1/books/{book_id}/audio",
        json={"scope": "all", "voice": "af_sarah", "engine": "kokoro"},
    )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_post_audio_queues_job(app_with_data, monkeypatch):
    ac, _, book_id, _, _ = app_with_data
    monkeypatch.setattr(shutil, "which", lambda c: "/usr/bin/ffmpeg")
    r = await ac.post(
        f"/api/v1/books/{book_id}/audio",
        json={"scope": "all", "voice": "af_sarah", "engine": "kokoro"},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["scope"] == "all"
    assert body["total_units"] >= 1
    assert "job_id" in body


@pytest.mark.asyncio
async def test_post_audio_409_when_existing(app_with_data, monkeypatch):
    ac, sm, book_id, _, _ = app_with_data
    monkeypatch.setattr(shutil, "which", lambda c: "/usr/bin/ffmpeg")
    async with sm() as s:
        s.add(
            ProcessingJob(
                book_id=book_id,
                step=ProcessingStep.AUDIO,
                status=ProcessingJobStatus.RUNNING,
                request_params={"scope": "all"},
            )
        )
        await s.commit()
    r = await ac.post(
        f"/api/v1/books/{book_id}/audio",
        json={"scope": "all", "voice": "af_sarah", "engine": "kokoro"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "audio_job_in_progress"


@pytest.mark.asyncio
async def test_get_inventory_empty(app_with_data):
    ac, _, book_id, _, _ = app_with_data
    r = await ac.get(f"/api/v1/books/{book_id}/audio")
    assert r.status_code == 200
    body = r.json()
    assert body["book_id"] == book_id
    assert body["files"] == []
    assert body["coverage"]["total"] == 1
    assert body["coverage"]["generated"] == 0


@pytest.mark.asyncio
async def test_lookup_pregen_false_for_unknown(app_with_data):
    ac, _, book_id, section_id, _ = app_with_data
    r = await ac.get(
        "/api/v1/audio/lookup",
        params={
            "book_id": book_id,
            "content_type": "section_summary",
            "content_id": section_id,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pregenerated"] is False
    assert body["sanitized_text"]


@pytest.mark.asyncio
async def test_serve_404_when_missing(app_with_data):
    ac, _, book_id, section_id, _ = app_with_data
    r = await ac.get(f"/api/v1/books/{book_id}/audio/section_summary/{section_id}.mp3")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_serve_returns_mp3_when_present(app_with_data, tmp_path):
    ac, sm, book_id, section_id, data_dir = app_with_data
    mp3_bytes = b"ID3\x04" + b"x" * 256
    audio_subdir = data_dir / "audio" / str(book_id)
    audio_subdir.mkdir(parents=True, exist_ok=True)
    rel = f"audio/{book_id}/section_summary_{section_id}__af_sarah.mp3"
    (data_dir / rel).write_bytes(mp3_bytes)
    async with sm() as s:
        s.add(
            AudioFile(
                book_id=book_id,
                content_type=ContentType.SECTION_SUMMARY,
                content_id=section_id,
                voice="af_sarah",
                engine="kokoro",
                file_path=rel,
                file_size_bytes=len(mp3_bytes),
                duration_seconds=1.0,
                sentence_count=1,
                sentence_offsets_json="[0.0]",
                source_hash="h",
                sanitizer_version="1.0",
            )
        )
        await s.commit()
    r = await ac.get(f"/api/v1/books/{book_id}/audio/section_summary/{section_id}.mp3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.headers["cache-control"] == "public, max-age=86400"
    assert r.content[:3] == b"ID3"


@pytest.mark.asyncio
async def test_delete_all_audio(app_with_data, tmp_path):
    ac, sm, book_id, section_id, data_dir = app_with_data
    audio_subdir = data_dir / "audio" / str(book_id)
    audio_subdir.mkdir(parents=True, exist_ok=True)
    rel = f"audio/{book_id}/section_summary_{section_id}__af_sarah.mp3"
    (data_dir / rel).write_bytes(b"ID3xx")
    async with sm() as s:
        s.add(
            AudioFile(
                book_id=book_id,
                content_type=ContentType.SECTION_SUMMARY,
                content_id=section_id,
                voice="af_sarah",
                engine="kokoro",
                file_path=rel,
                file_size_bytes=5,
                duration_seconds=1.0,
                sentence_count=1,
                sentence_offsets_json="[0.0]",
                source_hash="h",
                sanitizer_version="1.0",
            )
        )
        await s.commit()
    r = await ac.delete(f"/api/v1/books/{book_id}/audio")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_one_404(app_with_data):
    ac, _, book_id, section_id, _ = app_with_data
    r = await ac.delete(f"/api/v1/books/{book_id}/audio/section_summary/{section_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_audio_position_put_then_get(app_with_data):
    ac, _, _, section_id, _ = app_with_data
    r = await ac.put(
        "/api/v1/audio_position",
        json={
            "content_type": "section_summary",
            "content_id": section_id,
            "browser_id": "uuid-A",
            "sentence_index": 7,
        },
    )
    assert r.status_code == 200
    r2 = await ac.get(
        "/api/v1/audio_position",
        params={
            "content_type": "section_summary",
            "content_id": section_id,
            "browser_id": "uuid-A",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["sentence_index"] == 7
    assert r2.json()["has_other_browser"] is False


@pytest.mark.asyncio
async def test_audio_position_404_when_missing(app_with_data):
    ac, _, _, _, _ = app_with_data
    r = await ac.get(
        "/api/v1/audio_position",
        params={
            "content_type": "section_summary",
            "content_id": 99999,
            "browser_id": "X",
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_spike_route_unavailable_default(app_with_data):
    ac, *_ = app_with_data
    r = await ac.get("/api/v1/spikes/tts")
    assert r.status_code == 200
    body = r.json()
    # Repo may or may not have a spike file; both shapes are valid.
    assert "available" in body


@pytest.mark.asyncio
async def test_settings_tts_get_returns_defaults(app_with_data):
    ac, *_ = app_with_data
    r = await ac.get("/api/v1/settings/tts")
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "web-speech"


@pytest.mark.asyncio
async def test_settings_tts_put_unknown_voice_422(app_with_data):
    ac, *_ = app_with_data
    r = await ac.put(
        "/api/v1/settings/tts",
        json={"engine": "kokoro", "voice": "xx_invalid"},
    )
    assert r.status_code == 422
    assert "available" in r.json()["detail"]
