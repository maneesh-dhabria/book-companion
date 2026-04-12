import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from app.api.static_files import CachingStaticFiles


@pytest.fixture
def static_tree(tmp_path):
    (tmp_path / "index.html").write_text("<html>hi</html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app-abc123.js").write_text("console.log('x')")
    (assets / "app-abc123.css").write_text("body{}")
    return tmp_path


def _client(static_tree):
    sf = CachingStaticFiles(directory=str(static_tree), html=True)
    app = Starlette(routes=[Mount("/", sf, name="static")])
    return TestClient(app)


def test_index_html_has_no_cache(static_tree):
    r = _client(static_tree).get("/")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"


def test_index_html_direct_path_has_no_cache(static_tree):
    r = _client(static_tree).get("/index.html")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"


def test_hashed_asset_is_immutable(static_tree):
    r = _client(static_tree).get("/assets/app-abc123.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_hashed_css_is_immutable(static_tree):
    r = _client(static_tree).get("/assets/app-abc123.css")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_spa_fallback_for_unknown_path_has_no_cache(static_tree):
    r = _client(static_tree).get("/library/some-id")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"
