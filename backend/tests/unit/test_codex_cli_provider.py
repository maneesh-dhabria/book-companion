"""CodexCLIProvider env injection + argv shape (T6, FR-B06, P15)."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.summarizer.claude_cli import _LOGGED_CONFIG_DIRS
from app.services.summarizer.codex_cli import CodexCLIProvider


@pytest.fixture(autouse=True)
def _isolate_failure_log(monkeypatch):
    """Prevent these provider tests from writing to the dev's real data-dir
    failure log. _maybe_log loads Settings() and binds the singleton failure
    logger to the platformdirs path; later integration tests that swap the
    log path via tmp_path then race against the stale handler."""
    monkeypatch.setenv("BOOKCOMPANION_LLM__STDERR_LOG_ENABLED", "false")


def _mock_proc(out_path_capture: list[str] | None = None, write_message: str = "hello world"):
    """Build a mocked subprocess that, on communicate(), writes a final message
    to whatever path was passed via --output-last-message."""
    proc = AsyncMock()

    async def fake_communicate(input=None):  # noqa: A002 - matching real signature
        # The path was captured by the caller via the mock's call_args; write
        # the final message to it so the provider can read it back.
        if out_path_capture and out_path_capture[0]:
            Path(out_path_capture[0]).write_text(write_message)
        return (b"", b"")

    proc.communicate.side_effect = fake_communicate
    proc.returncode = 0
    return proc


@pytest.mark.asyncio
async def test_codex_provider_injects_codex_home_env(tmp_path):
    _LOGGED_CONFIG_DIRS.clear()
    target = tmp_path / "codex_home"
    provider = CodexCLIProvider(config_dir=target)
    captured: list[str] = [""]
    proc = _mock_proc(captured, "hi")

    def fake_exec(*args, **kwargs):
        # Locate --output-last-message argument
        argv = list(args)
        if "--output-last-message" in argv:
            captured[0] = argv[argv.index("--output-last-message") + 1]
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec) as exec_mock:
        await provider.generate("hi")
    env = exec_mock.call_args.kwargs["env"]
    assert env["CODEX_HOME"] == str(target)
    assert target.exists()


@pytest.mark.asyncio
async def test_codex_provider_argv_shape():
    provider = CodexCLIProvider()
    captured: list[str] = [""]
    proc = _mock_proc(captured, "ok")

    def fake_exec(*args, **kwargs):
        argv = list(args)
        if "--output-last-message" in argv:
            captured[0] = argv[argv.index("--output-last-message") + 1]
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec) as exec_mock:
        await provider.generate("prompt", json_schema={"type": "object"})
    argv = list(exec_mock.call_args.args)
    assert argv[0] == "codex"
    assert argv[1] == "exec"
    assert "--skip-git-repo-check" in argv
    assert "--model" in argv
    assert "--output-schema" in argv
    assert "--output-last-message" in argv
    assert argv[-1] == "-"  # stdin marker

    # Schema temp file must have been written with the schema content
    schema_path = argv[argv.index("--output-schema") + 1]
    # File is cleaned up after generate(), so check via a separate run
    assert not os.path.exists(schema_path), "schema temp file should be cleaned up after call"


@pytest.mark.asyncio
async def test_codex_provider_reads_output_last_message_file():
    provider = CodexCLIProvider()
    captured: list[str] = [""]
    proc = _mock_proc(captured, "the agent's final answer")

    def fake_exec(*args, **kwargs):
        argv = list(args)
        if "--output-last-message" in argv:
            captured[0] = argv[argv.index("--output-last-message") + 1]
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await provider.generate("prompt", json_schema={"type": "object"})
    assert result.content == "the agent's final answer"


@pytest.mark.asyncio
async def test_codex_provider_cleans_up_temp_files_on_success():
    provider = CodexCLIProvider()
    paths_seen: dict[str, str] = {}
    proc = AsyncMock()

    async def fake_communicate(input=None):  # noqa: A002
        Path(paths_seen["out"]).write_text("hi")
        return (b"", b"")

    proc.communicate.side_effect = fake_communicate
    proc.returncode = 0

    def fake_exec(*args, **kwargs):
        argv = list(args)
        paths_seen["out"] = argv[argv.index("--output-last-message") + 1]
        paths_seen["schema"] = argv[argv.index("--output-schema") + 1]
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await provider.generate("prompt", json_schema={"type": "object"})
    assert not os.path.exists(paths_seen["out"])
    assert not os.path.exists(paths_seen["schema"])


@pytest.mark.asyncio
async def test_codex_provider_cleans_up_temp_files_on_failure():
    from app.exceptions import SubprocessNonZeroExitError
    provider = CodexCLIProvider()
    paths_seen: dict[str, str] = {}
    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"oops")
    proc.returncode = 2

    def fake_exec(*args, **kwargs):
        argv = list(args)
        paths_seen["out"] = argv[argv.index("--output-last-message") + 1]
        if "--output-schema" in argv:
            paths_seen["schema"] = argv[argv.index("--output-schema") + 1]
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        with pytest.raises(SubprocessNonZeroExitError):
            await provider.generate("prompt", json_schema={"type": "object"})
    assert not os.path.exists(paths_seen["out"])
    if "schema" in paths_seen:
        assert not os.path.exists(paths_seen["schema"])


@pytest.mark.asyncio
async def test_codex_provider_no_config_dir_no_env(monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    provider = CodexCLIProvider(config_dir=None)
    captured: list[str] = [""]
    proc = _mock_proc(captured, "ok")

    def fake_exec(*args, **kwargs):
        argv = list(args)
        if "--output-last-message" in argv:
            captured[0] = argv[argv.index("--output-last-message") + 1]
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec) as exec_mock:
        await provider.generate("hi")
    env = exec_mock.call_args.kwargs["env"]
    assert "CODEX_HOME" not in env


@pytest.mark.asyncio
async def test_codex_provider_no_schema_omits_output_schema_flag():
    provider = CodexCLIProvider()
    captured: list[str] = [""]
    proc = _mock_proc(captured, "ok")

    def fake_exec(*args, **kwargs):
        argv = list(args)
        if "--output-last-message" in argv:
            captured[0] = argv[argv.index("--output-last-message") + 1]
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec) as exec_mock:
        await provider.generate("hi")  # no json_schema
    argv = list(exec_mock.call_args.args)
    assert "--output-schema" not in argv
    assert "--output-last-message" in argv
