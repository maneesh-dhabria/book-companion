"""FR-22 / plan T2: GET /api/v1/audio/annotations/{id}/lookup integration tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db.models import (
    Annotation,
    AnnotationType,
    Base,
    Book,
    BookSection,
    BookStatus,
    ContentType,
)


@pytest_asyncio.fixture
async def app_with_annotations(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")

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
            content_md="x",
            order_index=0,
        )
        session.add(section)
        await session.flush()
        ann_full = Annotation(
            content_type=ContentType.SECTION_SUMMARY,
            content_id=section.id,
            selected_text="Hello world.",
            note=None,
            type=AnnotationType.HIGHLIGHT,
        )
        ann_empty = Annotation(
            content_type=ContentType.SECTION_SUMMARY,
            content_id=section.id,
            selected_text=None,
            note=None,
            type=AnnotationType.FREEFORM,
        )
        session.add_all([ann_full, ann_empty])
        await session.commit()
        ann_full_id = ann_full.id
        ann_empty_id = ann_empty.id
        book_id = book.id
        section_id = section.id

    from fastapi import FastAPI

    from app.api.deps import get_db
    from app.api.routes import audio

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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        yield ac, ann_full_id, ann_empty_id, book_id, section_id


@pytest.mark.asyncio
async def test_annotation_lookup_returns_sanitized(app_with_annotations):
    ac, ann_full_id, _, _, _ = app_with_annotations
    r = await ac.get(f"/api/v1/audio/annotations/{ann_full_id}/lookup")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pregenerated"] is False
    assert body["sanitized_text"]
    assert isinstance(body["sentence_offsets_chars"], list)
    assert body["sanitizer_version_current"]
    assert body["stale"] is None


@pytest.mark.asyncio
async def test_annotation_lookup_404_when_missing(app_with_annotations):
    ac, *_ = app_with_annotations
    r = await ac.get("/api/v1/audio/annotations/999999/lookup")
    assert r.status_code == 404
    assert "annotation not found" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_annotation_lookup_empty_returns_empty_shape(app_with_annotations):
    ac, _, ann_empty_id, _, _ = app_with_annotations
    r = await ac.get(f"/api/v1/audio/annotations/{ann_empty_id}/lookup")
    assert r.status_code == 200
    body = r.json()
    assert body["sanitized_text"] == ""
    assert body["sentence_offsets_chars"] == []


@pytest.mark.asyncio
async def test_old_route_rejects_annotation_with_hint(app_with_annotations):
    ac, _, _, book_id, section_id = app_with_annotations
    r = await ac.get(
        "/api/v1/audio/lookup",
        params={
            "book_id": book_id,
            "content_type": "annotation",
            "content_id": section_id,
        },
    )
    assert r.status_code == 400
    assert "/audio/annotations/" in r.json()["detail"]
