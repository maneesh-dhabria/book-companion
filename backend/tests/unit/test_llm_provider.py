"""Tests for LLM provider interface and Claude CLI implementation."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.summarizer.llm_provider import LLMResponse
from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider


def test_llm_response_model():
    resp = LLMResponse(content="hello", model="sonnet", latency_ms=100)
    assert resp.content == "hello"
    assert resp.input_tokens is None


@pytest.mark.asyncio
async def test_claude_cli_constructs_correct_args():
    provider = ClaudeCodeCLIProvider(
        cli_command="claude", default_model="sonnet", default_timeout=300
    )
    # Mock subprocess
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (
        json.dumps({"result": "test output", "model": "sonnet", "usage": {"input_tokens": 10, "output_tokens": 5}}).encode(),
        b"",
    )
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await provider.generate("Summarize this")
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "claude"
        assert "-p" in call_args
        assert "-" in call_args  # stdin mode
        assert "--output-format" in call_args
        assert "json" in call_args
        assert "--print" in call_args
        # Verify prompt passed via stdin
        mock_proc.communicate.assert_called_once()


@pytest.mark.asyncio
async def test_claude_cli_timeout_raises():
    import asyncio
    provider = ClaudeCodeCLIProvider(
        cli_command="claude", default_model="sonnet", default_timeout=1
    )
    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = asyncio.TimeoutError()
    mock_proc.kill = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(Exception, match="timed out"):
            await provider.generate("Slow prompt")
