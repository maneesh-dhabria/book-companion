"""Integration tests for T4 — typed summarization errors + rotating log."""

import contextlib
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import (
    SubprocessNonZeroExitError,
    SubprocessNotFoundError,
    SubprocessTimeoutError,
    SummarizationError,
)
from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider
from app.services.summarizer.failure_log import get_failure_logger, log_failure


@pytest.fixture(autouse=True)
def _reset_logger():
    """Drop handlers between tests so each test picks a fresh path."""
    import logging

    yield
    logger = logging.getLogger("bookcompanion.summarizer_failures")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        with contextlib.suppress(Exception):
            h.close()


@pytest.mark.asyncio
async def test_subprocess_not_found_raises_typed_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    provider = ClaudeCodeCLIProvider()
    with (
        patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("nope")),
        pytest.raises(SubprocessNotFoundError) as exc,
    ):
        await provider.generate("hi", context={"section_id": 1, "book_id": 2})
    assert exc.value.failure_type == "cli_not_found"
    assert isinstance(exc.value, SummarizationError)
    log_path = tmp_path / "summarization-failures.log"
    assert log_path.exists()
    assert "cli_not_found" in log_path.read_text()


@pytest.mark.asyncio
async def test_subprocess_timeout_raises_typed_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    provider = ClaudeCodeCLIProvider(default_timeout=1)
    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = TimeoutError()
    mock_proc.kill = lambda: None
    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(SubprocessTimeoutError) as exc,
    ):
        await provider.generate("hi")
    assert exc.value.failure_type == "cli_timeout"
    assert exc.value.timeout_seconds == 1


@pytest.mark.asyncio
async def test_subprocess_nonzero_exit_raises_typed_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    provider = ClaudeCodeCLIProvider()
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"unauthorized: bad token")
    mock_proc.returncode = 42
    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(SubprocessNonZeroExitError) as exc,
    ):
        await provider.generate("hi", context={"section_id": 7, "book_id": 3})
    assert exc.value.failure_type == "cli_nonzero_exit"
    assert exc.value.returncode == 42
    assert "unauthorized" in exc.value.stderr_truncated
    log_text = (tmp_path / "summarization-failures.log").read_text()
    assert "cli_nonzero_exit" in log_text
    assert "section_id=7" in log_text


def test_log_file_mode_0600(tmp_path):
    log_path = tmp_path / "log.log"
    log_failure(
        log_path,
        failure_type="cli_timeout",
        section_id=1,
        book_id=2,
        message="test",
    )
    assert log_path.exists()
    mode = oct(log_path.stat().st_mode & 0o777)
    assert mode == "0o600", f"expected 0o600, got {mode}"


@pytest.mark.asyncio
async def test_log_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("BOOKCOMPANION_LLM__STDERR_LOG_ENABLED", "false")
    provider = ClaudeCodeCLIProvider()
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"boom")
    mock_proc.returncode = 1
    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(SubprocessNonZeroExitError),
    ):
        await provider.generate("hi")
    assert not (tmp_path / "summarization-failures.log").exists()


@pytest.mark.asyncio
async def test_test_mode_forces_section_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKCOMPANION_DATA__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("BOOKCOMPANION_LLM__TEST_MODE", "fail_section_99")
    provider = ClaudeCodeCLIProvider()
    # Even though we don't actually reach the subprocess, assert the hook fires.
    with pytest.raises(SubprocessNonZeroExitError) as exc:
        await provider.generate(
            "hi", context={"section_id": 99, "book_id": 1}
        )
    assert "TEST MODE" in exc.value.stderr_truncated


def test_get_failure_logger_is_idempotent(tmp_path):
    log = get_failure_logger(tmp_path / "log.log")
    count_before = len(log.handlers)
    log2 = get_failure_logger(tmp_path / "log.log")
    assert log is log2
    assert len(log2.handlers) == count_before
