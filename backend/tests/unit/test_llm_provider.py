"""Tests for LLM provider interface, factory, and auto-detection."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import SubprocessNotFoundError
from app.services.summarizer import create_llm_provider, detect_llm_provider
from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider
from app.services.summarizer.llm_provider import LLMResponse


def test_subprocess_not_found_error_uses_binary_param():
    err = SubprocessNotFoundError(binary="claude")
    assert err.binary == "claude"
    assert "claude" in str(err)
    assert not hasattr(err, "cli_command")


def test_llm_response_model():
    resp = LLMResponse(content="hello", model="sonnet", latency_ms=100)
    assert resp.content == "hello"
    assert resp.input_tokens is None


@pytest.mark.asyncio
async def test_claude_cli_constructs_correct_args():
    provider = ClaudeCodeCLIProvider(default_model="sonnet", default_timeout=300)
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (
        json.dumps(
            {
                "result": "test output",
                "model": "sonnet",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        ).encode(),
        b"",
    )
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await provider.generate("Summarize this")
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "claude"
        assert "-p" in call_args
        assert "-" in call_args
        assert "--output-format" in call_args
        assert "json" in call_args
        assert "--print" in call_args
        mock_proc.communicate.assert_called_once()


@pytest.mark.asyncio
async def test_claude_cli_timeout_raises():
    provider = ClaudeCodeCLIProvider(default_model="sonnet", default_timeout=1)
    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = TimeoutError()
    mock_proc.kill = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(Exception, match="timed out"):
            await provider.generate("Slow prompt")


# --- Factory and detection tests ---


def test_detect_claude_only():
    with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/claude" if cmd == "claude" else None):
        assert detect_llm_provider() == "claude"


def test_detect_codex_only():
    with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/codex" if cmd == "codex" else None):
        assert detect_llm_provider() == "codex"


def test_detect_both_prefers_claude():
    with patch("shutil.which", return_value="/usr/bin/something"):
        assert detect_llm_provider() == "claude"


def test_detect_none():
    with patch("shutil.which", return_value=None):
        assert detect_llm_provider() is None


def test_create_provider_claude():
    provider = create_llm_provider("claude")
    assert isinstance(provider, ClaudeCodeCLIProvider)


def test_create_provider_codex():
    from app.services.summarizer.codex_cli import CodexCLIProvider

    provider = create_llm_provider("codex")
    assert isinstance(provider, CodexCLIProvider)


def test_create_provider_null():
    assert create_llm_provider(None) is None


def test_create_provider_claude_cli_compat():
    """Existing config value 'claude_cli' still works."""
    provider = create_llm_provider("claude_cli")
    assert isinstance(provider, ClaudeCodeCLIProvider)
