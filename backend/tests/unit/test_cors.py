"""Tests for dynamic CORS origin builder."""

from unittest.mock import patch

from app.api.main import build_cors_origins


def test_cors_includes_localhost():
    origins = build_cors_origins(port=8000)
    assert "http://localhost:8000" in origins
    assert "http://127.0.0.1:8000" in origins


def test_cors_includes_vite_dev():
    origins = build_cors_origins(port=8000)
    assert "http://localhost:5173" in origins


def test_cors_includes_lan_ip():
    fake_addr_info = [
        (2, 1, 6, "", ("192.168.1.50", 0)),
    ]
    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        with patch("socket.gethostname", return_value="myhost"):
            origins = build_cors_origins(port=8000)
            assert "http://192.168.1.50:8000" in origins


def test_cors_extra_origins_env(monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_CORS_EXTRA_ORIGINS", "http://myhost:3000,http://other:9000")
    origins = build_cors_origins(port=8000)
    assert "http://myhost:3000" in origins
    assert "http://other:9000" in origins


def test_cors_deduplicates():
    origins = build_cors_origins(port=8000)
    assert len(origins) == len(set(origins))
