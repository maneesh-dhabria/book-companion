"""ClaudeCodeCLIProvider env injection + argv shape (T6, FR-B04, FR-B05)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.summarizer.claude_cli import (
    _LOGGED_CONFIG_DIRS,
    ClaudeCodeCLIProvider,
)


@pytest.fixture(autouse=True)
def _isolate_failure_log(monkeypatch):
    """Prevent these provider tests from writing to the dev's real data-dir
    failure log; otherwise the singleton failure logger gets bound to the
    platformdirs path and later integration tests using tmp_path race against
    the stale handler."""
    monkeypatch.setenv("BOOKCOMPANION_LLM__STDERR_LOG_ENABLED", "false")


def _mock_proc(stdout_text: str = "{}"):
    proc = AsyncMock()
    proc.communicate.return_value = (stdout_text.encode(), b"")
    proc.returncode = 0
    return proc


@pytest.mark.asyncio
async def test_claude_provider_injects_config_dir_env(tmp_path):
    _LOGGED_CONFIG_DIRS.clear()
    target = tmp_path / "config"
    provider = ClaudeCodeCLIProvider(config_dir=target)
    with patch("asyncio.create_subprocess_exec", return_value=_mock_proc(json.dumps({"result": "ok"}))) as exec_mock:
        await provider.generate("hello")
    env = exec_mock.call_args.kwargs["env"]
    assert env["CLAUDE_CONFIG_DIR"] == str(target)
    assert target.exists()


@pytest.mark.asyncio
async def test_claude_provider_no_config_dir_does_not_inject_env(monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    provider = ClaudeCodeCLIProvider(config_dir=None)
    with patch("asyncio.create_subprocess_exec", return_value=_mock_proc(json.dumps({"result": "ok"}))) as exec_mock:
        await provider.generate("hello")
    env = exec_mock.call_args.kwargs["env"]
    assert "CLAUDE_CONFIG_DIR" not in env


@pytest.mark.asyncio
async def test_claude_provider_creates_missing_config_dir(tmp_path):
    _LOGGED_CONFIG_DIRS.clear()
    target = tmp_path / "newdir" / "deep"
    assert not target.exists()
    provider = ClaudeCodeCLIProvider(config_dir=target)
    with patch("asyncio.create_subprocess_exec", return_value=_mock_proc(json.dumps({"result": "ok"}))):
        await provider.generate("hello")
    assert target.is_dir()


@pytest.mark.asyncio
async def test_claude_provider_argv_uses_class_binary():
    provider = ClaudeCodeCLIProvider()
    with patch("asyncio.create_subprocess_exec", return_value=_mock_proc(json.dumps({"result": "ok"}))) as exec_mock:
        await provider.generate("hi")
    argv = exec_mock.call_args.args
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "--print" in argv


@pytest.mark.asyncio
async def test_claude_provider_terminate_calls_process_terminate():
    """Regression for verify-finding #1: cancel-RUNNING must SIGTERM the
    in-flight subprocess. Provider tracks the active proc; terminate()
    forwards SIGTERM via proc.terminate()."""
    provider = ClaudeCodeCLIProvider()
    fake_proc = AsyncMock()
    fake_proc.returncode = None
    fake_proc.terminate = lambda: setattr(fake_proc, "_terminated", True)
    provider._track_active(fake_proc)
    await provider.terminate()
    assert getattr(fake_proc, "_terminated", False) is True


@pytest.mark.asyncio
async def test_claude_provider_terminate_noop_when_idle():
    provider = ClaudeCodeCLIProvider()
    # No active proc — must not raise.
    await provider.terminate()


@pytest.mark.asyncio
async def test_claude_provider_terminate_noop_when_proc_already_exited():
    provider = ClaudeCodeCLIProvider()
    fake_proc = AsyncMock()
    fake_proc.returncode = 0  # already exited
    called = {"terminate": False}
    fake_proc.terminate = lambda: called.__setitem__("terminate", True)
    provider._track_active(fake_proc)
    await provider.terminate()
    assert called["terminate"] is False


@pytest.mark.asyncio
async def test_claude_provider_clears_active_proc_after_call():
    provider = ClaudeCodeCLIProvider()
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_mock_proc(json.dumps({"result": "ok"})),
    ):
        await provider.generate("hi")
    assert provider._active_proc is None
