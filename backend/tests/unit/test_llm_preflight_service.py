"""Tests for LLMPreflightService (T7 / FR-B08, FR-B08a, NFR-01)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm_preflight import (
    LLMPreflightService,
    PreflightResult,
    get_preflight_service,
)


def _mock_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    return proc


@pytest.mark.asyncio
async def test_preflight_binary_not_found(monkeypatch):
    monkeypatch.setattr("app.services.llm_preflight.shutil.which", lambda b: None)
    svc = LLMPreflightService()
    result = await svc.check("claude")
    assert result.ok is False
    assert result.binary_resolved is False
    assert result.version is None
    assert "PATH" in result.reason


@pytest.mark.asyncio
async def test_preflight_auto_with_no_provider_detected(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_preflight.detect_llm_provider", lambda: None
    )
    svc = LLMPreflightService()
    result = await svc.check("auto")
    assert result.ok is False
    assert result.binary_resolved is False
    assert result.provider is None
    assert "No LLM CLI" in result.reason


@pytest.mark.asyncio
async def test_preflight_auto_resolves_provider(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_preflight.detect_llm_provider", lambda: "claude"
    )
    monkeypatch.setattr(
        "app.services.llm_preflight.shutil.which", lambda b: "/usr/local/bin/claude"
    )
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(stdout=b"claude 2.1.123\n"),
    ):
        svc = LLMPreflightService()
        result = await svc.check("auto")
    assert result.ok is True
    assert result.provider == "claude"
    assert result.binary == "claude"
    assert result.version == "2.1.123"
    assert result.version_ok is True
    assert result.reason is None


@pytest.mark.asyncio
async def test_preflight_old_version_non_blocking(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_preflight.shutil.which", lambda b: "/usr/local/bin/claude"
    )
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(stdout=b"claude 1.5.0\n"),
    ):
        svc = LLMPreflightService()
        result = await svc.check("claude")
    assert result.ok is True  # non-blocking
    assert result.binary_resolved is True
    assert result.version == "1.5.0"
    assert result.version_ok is False
    assert "below the recommended floor" in result.reason


@pytest.mark.asyncio
async def test_preflight_codex_version_floor(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_preflight.shutil.which", lambda b: "/usr/local/bin/codex"
    )
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(stdout=b"codex-cli 0.118.0\n"),
    ):
        svc = LLMPreflightService()
        result = await svc.check("codex")
    assert result.ok is True
    assert result.version_ok is True


@pytest.mark.asyncio
async def test_preflight_version_unparseable(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_preflight.shutil.which", lambda b: "/usr/local/bin/claude"
    )
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(stdout=b"weird output without semver"),
    ):
        svc = LLMPreflightService()
        result = await svc.check("claude")
    assert result.ok is True
    assert result.binary_resolved is True
    assert result.version is None
    assert "Could not determine" in result.reason


@pytest.mark.asyncio
async def test_preflight_version_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_preflight.shutil.which", lambda b: "/usr/local/bin/claude"
    )
    proc = AsyncMock()
    proc.communicate.side_effect = TimeoutError()
    proc.kill = AsyncMock()
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        svc = LLMPreflightService()
        result = await svc.check("claude")
    assert result.ok is True
    assert result.binary_resolved is True
    assert result.version is None


@pytest.mark.asyncio
async def test_preflight_caches_within_ttl(monkeypatch):
    call_count = 0

    def fake_which(b):
        nonlocal call_count
        call_count += 1
        return "/usr/local/bin/claude"

    monkeypatch.setattr("app.services.llm_preflight.shutil.which", fake_which)
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(stdout=b"claude 2.1.0"),
    ):
        svc = LLMPreflightService(ttl_seconds=60.0)
        r1 = await svc.check("claude")
        r2 = await svc.check("claude")
    assert r1 == r2
    assert call_count == 1


@pytest.mark.asyncio
async def test_preflight_invalidate_cache_all(monkeypatch):
    call_count = 0

    def fake_which(b):
        nonlocal call_count
        call_count += 1
        return "/usr/local/bin/claude"

    monkeypatch.setattr("app.services.llm_preflight.shutil.which", fake_which)
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(stdout=b"claude 2.1.0"),
    ):
        svc = LLMPreflightService()
        await svc.check("claude")
        svc.invalidate_cache()
        await svc.check("claude")
    assert call_count == 2


@pytest.mark.asyncio
async def test_preflight_invalidate_cache_specific(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_preflight.shutil.which", lambda b: "/usr/local/bin/claude"
    )
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(stdout=b"claude 2.1.0"),
    ):
        svc = LLMPreflightService()
        result = await svc.check("claude")
    svc._cache["codex"] = (
        9999999999.0,
        PreflightResult(
            ok=True,
            provider="codex",
            binary="codex",
            binary_resolved=True,
            version="0.118.0",
            version_ok=True,
            reason=None,
        ),
    )
    svc.invalidate_cache("claude")
    assert "claude" not in svc._cache
    assert "codex" in svc._cache


def test_get_preflight_service_returns_singleton():
    a = get_preflight_service()
    b = get_preflight_service()
    assert a is b
