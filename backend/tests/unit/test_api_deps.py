"""Tests for FastAPI app factory, config extensions, and dependency injection."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import NetworkConfig, Settings, WebConfig


def test_network_config_defaults():
    cfg = NetworkConfig()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8000
    assert cfg.allow_lan is False
    assert cfg.access_token is None


def test_web_config_defaults():
    cfg = WebConfig()
    assert cfg.show_cost_estimates is False
    assert cfg.static_dir == "static"


def test_settings_has_network_and_web():
    s = Settings()
    assert isinstance(s.network, NetworkConfig)
    assert isinstance(s.web, WebConfig)


@pytest.mark.asyncio
async def test_app_factory_creates_fastapi():
    from app.api.main import create_app

    app = create_app()
    assert app.title == "Book Companion"


@pytest.mark.asyncio
async def test_health_endpoint():
    from app.api.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
