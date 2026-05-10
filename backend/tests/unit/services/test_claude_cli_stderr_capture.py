"""FR-02: characterisation test for ClaudeCodeCLIProvider stderr capture.

Verifies (no modification expected) that on a non-zero exit, the provider:
  - awaits proc.stderr,
  - raises SubprocessNonZeroExitError,
  - exposes returncode + stderr_truncated (clipped to STDERR_TRUNCATE)
    + stderr_full (untruncated).

Spec note: spec/plan refer to a 2048-char truncation, but the live code
constant is STDERR_TRUNCATE = 500 (see claude_cli.py:23). To honour the
"verify, not modify" mandate of FR-02 we assert against the module's actual
constant rather than the spec literal — the discrepancy is logged as a
deviation in the task log.
"""

import asyncio

import pytest

from app.exceptions import SubprocessNonZeroExitError
from app.services.summarizer import claude_cli
from app.services.summarizer.claude_cli import STDERR_TRUNCATE, ClaudeCodeCLIProvider


class _FakeProc:
    """Minimal stand-in for asyncio.subprocess.Process."""

    def __init__(self, *, returncode: int, stderr_bytes: bytes, stdout_bytes: bytes = b""):
        self.returncode = returncode
        self._stderr_bytes = stderr_bytes
        self._stdout_bytes = stdout_bytes

    async def communicate(self, input=None):  # noqa: A002 — match asyncio API
        # Simulate the real proc.communicate() returning (stdout, stderr).
        return (self._stdout_bytes, self._stderr_bytes)

    def kill(self):  # noqa: D401 — interface stub
        pass


def _patch_create_subprocess_exec(monkeypatch, fake_proc: _FakeProc) -> None:
    async def _fake_exec(*args, **kwargs):
        return fake_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    # claude_cli module imports asyncio directly; the attribute lookup goes
    # through the same module reference, so the global monkeypatch suffices.


@pytest.mark.asyncio
async def test_nonzero_exit_captures_stderr_short(monkeypatch):
    stderr_bytes = b"trace data\nrace condition at line 42"
    proc = _FakeProc(returncode=1, stderr_bytes=stderr_bytes)
    _patch_create_subprocess_exec(monkeypatch, proc)

    provider = ClaudeCodeCLIProvider()
    with pytest.raises(SubprocessNonZeroExitError) as ei:
        await provider.generate(prompt="test", json_schema={"type": "object"})

    e = ei.value
    assert e.returncode == 1
    assert e.stderr_truncated == "trace data\nrace condition at line 42"
    assert e.stderr_full == "trace data\nrace condition at line 42"


@pytest.mark.asyncio
async def test_nonzero_exit_truncates_long_stderr(monkeypatch):
    # Build stderr longer than the truncation cap.
    payload = ("x" * (STDERR_TRUNCATE + 1024)).encode()
    proc = _FakeProc(returncode=2, stderr_bytes=payload)
    _patch_create_subprocess_exec(monkeypatch, proc)

    provider = ClaudeCodeCLIProvider()
    with pytest.raises(SubprocessNonZeroExitError) as ei:
        await provider.generate(prompt="test", json_schema={"type": "object"})

    e = ei.value
    assert e.returncode == 2
    assert len(e.stderr_truncated) == STDERR_TRUNCATE
    assert len(e.stderr_full) == STDERR_TRUNCATE + 1024
    # Sanity: truncated is a prefix of full (after .strip() — payload has no whitespace).
    assert e.stderr_full.startswith(e.stderr_truncated)


def test_stderr_truncate_constant_present():
    """Pin the module constant so future renames break this test loudly."""
    assert isinstance(claude_cli.STDERR_TRUNCATE, int)
    assert claude_cli.STDERR_TRUNCATE > 0
