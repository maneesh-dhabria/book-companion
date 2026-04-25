"""Integration tests for export API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_export_library_json(client):
    """Library export returns valid JSON with library key."""
    resp = await client.get("/api/v1/export/library?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert "library" in data
    assert isinstance(data["library"], list)


@pytest.mark.asyncio
async def test_export_library_markdown_returns_410(client):
    """Library Markdown export was removed in v1.6 -- returns 410 Gone."""
    resp = await client.get("/api/v1/export/library?format=markdown")
    assert resp.status_code == 410
    body = resp.json()
    assert "removed in v1.6" in body["detail"]
    assert "format=json" in body["detail"]


@pytest.mark.asyncio
async def test_export_book_not_found(client):
    """Export for nonexistent book returns 404."""
    resp = await client.get("/api/v1/export/book/99999?format=json")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_book_json_when_books_exist(client):
    """If books exist, single-book export returns the correct book."""
    # First get the list of books
    lib_resp = await client.get("/api/v1/export/library?format=json")
    books = lib_resp.json()["library"]
    if not books:
        pytest.skip("No books in test DB — cannot test single-book export")
    book_id = books[0]["id"]

    resp = await client.get(f"/api/v1/export/book/{book_id}?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert "library" in data
    assert len(data["library"]) == 1
    assert data["library"][0]["id"] == book_id


@pytest.mark.asyncio
async def test_export_book_markdown_has_sections(client):
    """Markdown export includes section headings if book has sections."""
    lib_resp = await client.get("/api/v1/export/library?format=json")
    books = lib_resp.json()["library"]
    if not books:
        pytest.skip("No books in test DB")
    book_id = books[0]["id"]

    resp = await client.get(f"/api/v1/export/book/{book_id}?format=markdown")
    assert resp.status_code == 200
    assert "##" in resp.text, "Expected section-level headings in markdown export"


@pytest.mark.asyncio
async def test_export_json_has_content_disposition(client):
    """JSON export includes Content-Disposition header for download."""
    resp = await client.get("/api/v1/export/library?format=json")
    assert resp.status_code == 200
    assert "content-disposition" in resp.headers
    assert "library_export.json" in resp.headers["content-disposition"]
