"""T16 / FR-B18a: GET /api/v1/books/{id}/sections/{sid}/split-preview."""

import pytest

from app.db.models import Book, BookSection, BookStatus


async def _seed_section(app, content: str, title: str = "Test") -> tuple[int, int]:
    factory = app.state.session_factory
    async with factory() as session:
        b = Book(
            title="t",
            file_data=b"",
            file_hash=f"sp-{title}",
            file_format="epub",
            file_size_bytes=0,
            status=BookStatus.PARSED,
        )
        session.add(b)
        await session.commit()
        sec = BookSection(
            book_id=b.id,
            order_index=0,
            title=title,
            content_md=content,
            section_type="chapter",
            content_token_count=10,
        )
        session.add(sec)
        await session.commit()
        return b.id, sec.id


@pytest.mark.asyncio
async def test_split_preview_heading_mode(app, client):
    content = (
        "# Intro\nFirst paragraph.\n\n"
        "## Section A\nBody A.\n\n"
        "## Section B\nBody B."
    )
    book_id, section_id = await _seed_section(app, content, "headings")
    r = await client.get(
        f"/api/v1/books/{book_id}/sections/{section_id}/split-preview",
        params={"mode": "heading"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "heading"
    candidates = body["candidates"]
    assert len(candidates) >= 2
    for c in candidates:
        assert "title" in c and "char_count" in c and "first_line" in c


@pytest.mark.asyncio
async def test_split_preview_paragraph_mode(app, client):
    content = "Para one.\n\nPara two.\n\nPara three."
    book_id, section_id = await _seed_section(app, content, "paragraphs")
    r = await client.get(
        f"/api/v1/books/{book_id}/sections/{section_id}/split-preview",
        params={"mode": "paragraph"},
    )
    body = r.json()
    assert body["mode"] == "paragraph"
    assert len(body["candidates"]) == 3


@pytest.mark.asyncio
async def test_split_preview_char_mode(app, client):
    content = "A" * 100 + "B" * 100
    book_id, section_id = await _seed_section(app, content, "chars")
    r = await client.get(
        f"/api/v1/books/{book_id}/sections/{section_id}/split-preview",
        params={"mode": "char", "position": 100},
    )
    body = r.json()
    assert body["mode"] == "char"
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["char_count"] == 100
    assert body["candidates"][1]["char_count"] == 100


@pytest.mark.asyncio
async def test_split_preview_char_mode_invalid_position(app, client):
    content = "abc"
    book_id, section_id = await _seed_section(app, content, "char-bad")
    r = await client.get(
        f"/api/v1/books/{book_id}/sections/{section_id}/split-preview",
        params={"mode": "char", "position": 100},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_position"


@pytest.mark.asyncio
async def test_split_preview_invalid_mode(app, client):
    content = "abc"
    book_id, section_id = await _seed_section(app, content, "bad-mode")
    r = await client.get(
        f"/api/v1/books/{book_id}/sections/{section_id}/split-preview",
        params={"mode": "blockchain"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_split_preview_section_404(app, client):
    factory = app.state.session_factory
    async with factory() as session:
        b = Book(title="t", file_data=b"", file_hash="sp-404", file_format="epub", file_size_bytes=0, status=BookStatus.PARSED)
        session.add(b)
        await session.commit()
        book_id = b.id
    r = await client.get(
        f"/api/v1/books/{book_id}/sections/999/split-preview",
        params={"mode": "paragraph"},
    )
    assert r.status_code == 404
