import pytest
from httpx import ASGITransport, AsyncClient

import app.api.main as api_main


@pytest.fixture
def static_tree(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html><title>Book Companion</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "main-deadbeef.js").write_text("console.log('ok')")
    monkeypatch.setattr(api_main, "_resolve_static_dir", lambda: tmp_path)
    monkeypatch.setattr(api_main, "_assets_present", lambda: True)
    monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)
    return tmp_path


@pytest.mark.asyncio
async def test_root_serves_index_html(static_tree):
    app = api_main.create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
    assert r.status_code == 200
    assert "Book Companion" in r.text
    assert r.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_spa_fallback_for_client_routes(static_tree):
    app = api_main.create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/library/some-book-id")
    assert r.status_code == 200
    assert "Book Companion" in r.text


@pytest.mark.asyncio
async def test_hashed_asset_long_cache(static_tree):
    app = api_main.create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/assets/main-deadbeef.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.asyncio
async def test_api_routes_unaffected_by_mount(static_tree):
    app = api_main.create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/health")
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")
