"""ClaudeCodeCLIProvider env injection + argv shape (T6, FR-B04, FR-B05)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.summarizer.claude_cli import (
    _LOGGED_CONFIG_DIRS,
    ClaudeCodeCLIProvider,
)


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
