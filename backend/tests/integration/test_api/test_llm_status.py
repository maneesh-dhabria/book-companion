"""Tests for GET /api/v1/llm/status and POST /api/v1/llm/recheck."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.llm_preflight import PreflightResult, get_preflight_service


@pytest.fixture(autouse=True)
def _force_auto_provider(app):
    """Force `provider="auto"` so resolution depends on the patched
    `shutil.which`, not whatever the dev's local settings.yaml says.

    Mutates BOTH `app.state.settings` and the module-level `_settings`
    cache used by `get_settings()` (Depends), since the route reaches
    settings via the latter.
    """
    from app.api import deps as api_deps

    object.__setattr__(app.state.settings.llm, "provider", "auto")
    if api_deps._settings is not None:
        object.__setattr__(api_deps._settings.llm, "provider", "auto")
    get_preflight_service().invalidate_cache()
    yield
    get_preflight_service().invalidate_cache()


def _claude_only(x):
    return "/usr/local/bin/claude" if x == "claude" else None


def _mock_proc(stdout: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate.return_value = (stdout, b"")
    proc.returncode = returncode
    return proc


@pytest.mark.asyncio
async def test_llm_status_when_claude_on_path(client: AsyncClient):
    with (
        patch("app.services.llm_preflight.shutil.which", _claude_only),
        patch("app.services.summarizer.shutil.which", _claude_only),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_mock_proc(b"claude-cli 2.1.123\n"),
        ),
    ):
        r = await client.get("/api/v1/llm/status")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "claude"
    assert body["preflight"]["ok"] is True
    assert body["preflight"]["binary_resolved"] is True
    assert body["preflight"]["version"] == "2.1.123"
    assert body["preflight"]["version_ok"] is True


@pytest.mark.asyncio
async def test_llm_status_when_codex_on_path(client: AsyncClient):
    def which(x):
        return "/usr/local/bin/codex" if x == "codex" else None

    with (
        patch("app.services.llm_preflight.shutil.which", which),
        patch("app.services.summarizer.shutil.which", which),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_mock_proc(b"codex-cli 0.118.0\n"),
        ),
    ):
        r = await client.get("/api/v1/llm/status")
    body = r.json()
    assert body["provider"] == "codex"
    assert body["preflight"]["ok"] is True
    assert body["preflight"]["version"] == "0.118.0"


@pytest.mark.asyncio
async def test_llm_status_when_neither(client: AsyncClient):
    with (
        patch("app.services.llm_preflight.shutil.which", lambda x: None),
        patch("app.services.summarizer.shutil.which", lambda x: None),
    ):
        r = await client.get("/api/v1/llm/status")
    body = r.json()
    assert body["preflight"]["ok"] is False
    assert body["preflight"]["binary_resolved"] is False
    assert body["preflight"]["reason"]


@pytest.mark.asyncio
async def test_llm_status_version_below_floor_non_blocking(client: AsyncClient):
    with (
        patch("app.services.llm_preflight.shutil.which", _claude_only),
        patch("app.services.summarizer.shutil.which", _claude_only),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_mock_proc(b"claude 1.5.0\n"),
        ),
    ):
        r = await client.get("/api/v1/llm/status")
    body = r.json()
    assert body["preflight"]["ok"] is True  # non-blocking warning
    assert body["preflight"]["version"] == "1.5.0"
    assert body["preflight"]["version_ok"] is False
    assert "below the recommended floor" in body["preflight"]["reason"]


@pytest.mark.asyncio
async def test_llm_status_version_unparseable_still_ok(client: AsyncClient):
    with (
        patch("app.services.llm_preflight.shutil.which", _claude_only),
        patch("app.services.summarizer.shutil.which", _claude_only),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_mock_proc(b"garbage banner\n"),
        ),
    ):
        r = await client.get("/api/v1/llm/status")
    body = r.json()
    assert body["preflight"]["ok"] is True
    assert body["preflight"]["binary_resolved"] is True
    assert body["preflight"]["version"] is None


@pytest.mark.asyncio
async def test_llm_status_caches_within_ttl(client: AsyncClient):
    """Two calls hit the version probe only once thanks to the 60s cache."""
    call_count = 0

    def fake_exec(*a, **k):
        nonlocal call_count
        call_count += 1
        return _mock_proc(b"claude 2.1.0\n")

    with (
        patch("app.services.llm_preflight.shutil.which", _claude_only),
        patch("app.services.summarizer.shutil.which", _claude_only),
        patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
    ):
        await client.get("/api/v1/llm/status")
        await client.get("/api/v1/llm/status")
    assert call_count == 1


@pytest.mark.asyncio
async def test_llm_recheck_invalidates_cache(client: AsyncClient):
    call_count = 0

    def fake_exec(*a, **k):
        nonlocal call_count
        call_count += 1
        return _mock_proc(b"claude 2.1.0\n")

    with (
        patch("app.services.llm_preflight.shutil.which", _claude_only),
        patch("app.services.summarizer.shutil.which", _claude_only),
        patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
    ):
        await client.get("/api/v1/llm/status")
        r = await client.post("/api/v1/llm/recheck")
    assert r.status_code == 200
    assert call_count == 2  # status warmed cache, recheck blew it away + reprobed
    body = r.json()
    assert body["preflight"]["ok"] is True


@pytest.mark.asyncio
async def test_llm_status_seeds_cache_so_recheck_changes_response(
    client: AsyncClient,
):
    """First call: claude not present → ok=False. Re-detect after install: ok=True."""
    state = {"installed": False}

    def which(x):
        if x == "claude" and state["installed"]:
            return "/usr/local/bin/claude"
        return None

    def fake_exec(*a, **k):
        return _mock_proc(b"claude 2.1.0\n")

    with (
        patch("app.services.llm_preflight.shutil.which", which),
        patch("app.services.summarizer.shutil.which", which),
        patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
    ):
        r1 = await client.get("/api/v1/llm/status")
        assert r1.json()["preflight"]["ok"] is False

        # Simulate user installing claude, then clicking Re-detect
        state["installed"] = True
        r2 = await client.post("/api/v1/llm/recheck")
        assert r2.json()["preflight"]["ok"] is True
        assert r2.json()["preflight"]["version"] == "2.1.0"
