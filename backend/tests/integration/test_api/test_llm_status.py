"""Tests for GET /api/v1/llm/status."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


def _claude_only(x):
    return "/usr/local/bin/claude" if x == "claude" else None


@pytest.mark.asyncio
async def test_llm_status_when_claude_on_path(client: AsyncClient):
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"claude-cli 1.2.3\n", b"")
    mock_proc.returncode = 0
    with (
        patch("app.api.routes.llm_status.shutil.which", _claude_only),
        patch("app.services.summarizer.shutil.which", _claude_only),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        r = await client.get("/api/v1/llm/status")
    assert r.status_code == 200
    body = r.json()
    assert body == {"available": True, "provider": "claude", "version": "1.2.3"}


@pytest.mark.asyncio
async def test_llm_status_when_codex_on_path(client: AsyncClient):
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"codex 0.9.0\n", b"")
    mock_proc.returncode = 0

    def which(x):
        return "/usr/local/bin/codex" if x == "codex" else None

    with (
        patch("app.api.routes.llm_status.shutil.which", which),
        patch("app.services.summarizer.shutil.which", which),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        r = await client.get("/api/v1/llm/status")
    body = r.json()
    assert body["provider"] == "codex"
    assert body["available"] is True
    assert body["version"] == "0.9.0"


@pytest.mark.asyncio
async def test_llm_status_when_neither(client: AsyncClient):
    with (
        patch("app.api.routes.llm_status.shutil.which", lambda x: None),
        patch("app.services.summarizer.shutil.which", lambda x: None),
    ):
        r = await client.get("/api/v1/llm/status")
    assert r.json() == {"available": False, "provider": None, "version": None}


@pytest.mark.asyncio
async def test_llm_status_version_parse_failure_still_available(client: AsyncClient):
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"garbage version banner\n", b"")
    mock_proc.returncode = 0

    def which(x):
        return "/usr/local/bin/claude" if x == "claude" else None

    with (
        patch("app.api.routes.llm_status.shutil.which", which),
        patch("app.services.summarizer.shutil.which", which),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        r = await client.get("/api/v1/llm/status")
    body = r.json()
    assert body["available"] is True
    assert body["version"] is None


@pytest.mark.asyncio
async def test_llm_status_prefers_claude_when_both_present(client: AsyncClient):
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"claude-cli 2.0.0\n", b"")
    mock_proc.returncode = 0

    def which(x):
        return f"/usr/local/bin/{x}" if x in ("claude", "codex") else None

    with (
        patch("app.api.routes.llm_status.shutil.which", which),
        patch("app.services.summarizer.shutil.which", which),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        r = await client.get("/api/v1/llm/status")
    assert r.json()["provider"] == "claude"
