"""Codex CLI provider — invokes CLI as subprocess.

Uses ``codex exec --skip-git-repo-check`` (D3, P15). Schema is consumed
natively via ``--output-schema <FILE>``; the agent's final message is
written to ``--output-last-message <FILE>`` and parsed as JSON. Both
temp files are cleaned up after the call.
"""

import asyncio
import contextlib
import json
import os
import tempfile
import time
from pathlib import Path

from app.exceptions import (
    SubprocessNonZeroExitError,
    SubprocessNotFoundError,
    SubprocessTimeoutError,
    SummarizationError,
)
from app.services.summarizer.claude_cli import (
    STDERR_TRUNCATE,
    _build_env,
    _maybe_force_test_failure,
    _maybe_log,
)
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse


def _make_temp(suffix: str, prefix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return path


def _cleanup_paths(*paths: str) -> None:
    for p in paths:
        with contextlib.suppress(FileNotFoundError, OSError):
            os.unlink(p)


class CodexCLIProvider(LLMProvider):
    BINARY = "codex"

    def __init__(
        self,
        default_model: str = "gpt-5",
        default_timeout: int = 300,
        max_budget_usd: float | None = None,
        config_dir: Path | None = None,
    ):
        self.default_model = default_model
        self.default_timeout = default_timeout
        self.max_budget_usd = max_budget_usd
        self.config_dir = config_dir

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        json_schema: dict | None = None,
        timeout: int | None = None,
        context: dict | None = None,
    ) -> LLMResponse:
        _maybe_force_test_failure(self.BINARY, context)
        section_id = (context or {}).get("section_id")
        book_id = (context or {}).get("book_id")

        model = model or self.default_model
        timeout = timeout or self.default_timeout

        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"

        schema_path: str | None = None
        out_path = _make_temp(suffix=".txt", prefix="codex_out_")
        try:
            cmd = [
                self.BINARY,
                "exec",
                "--skip-git-repo-check",
                "--model",
                model,
                "--output-last-message",
                out_path,
            ]
            if json_schema:
                schema_path = _make_temp(suffix=".json", prefix="codex_schema_")
                Path(schema_path).write_text(json.dumps(json_schema))
                cmd.extend(["--output-schema", schema_path])
            cmd.append("-")  # read prompt from stdin

            env = _build_env(self.config_dir, "CODEX_HOME")

            start_time = time.monotonic()
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            except FileNotFoundError as e:
                _maybe_log(
                    binary=self.BINARY,
                    failure_type="cli_not_found",
                    section_id=section_id,
                    book_id=book_id,
                    stderr_full=str(e),
                )
                raise SubprocessNotFoundError(binary=self.BINARY) from e

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode("utf-8")),
                    timeout=timeout,
                )
            except TimeoutError as e:
                proc.kill()
                _maybe_log(
                    binary=self.BINARY,
                    failure_type="cli_timeout",
                    section_id=section_id,
                    book_id=book_id,
                    stderr_full=f"Timeout after {timeout}s",
                )
                raise SubprocessTimeoutError(timeout) from e

            if proc.returncode != 0:
                stderr_text = stderr.decode(errors="replace") if stderr else ""
                truncated = stderr_text.strip()[:STDERR_TRUNCATE]
                _maybe_log(
                    binary=self.BINARY,
                    failure_type="cli_nonzero_exit",
                    section_id=section_id,
                    book_id=book_id,
                    stderr_full=stderr_text,
                )
                raise SubprocessNonZeroExitError(
                    returncode=proc.returncode or 0,
                    stderr_truncated=truncated,
                    stderr_full=stderr_text,
                )

            # Final message is written to out_path; fall back to stdout if empty.
            try:
                raw_output = Path(out_path).read_text().strip()
            except OSError:
                raw_output = ""
            if not raw_output:
                raw_output = stdout.decode().strip()
            latency_ms = int((time.monotonic() - start_time) * 1000)

            return LLMResponse(
                content=raw_output,
                model=model,
                input_tokens=None,
                output_tokens=None,
                latency_ms=latency_ms,
            )
        finally:
            _cleanup_paths(out_path, *([schema_path] if schema_path else []))

    async def generate_with_image(
        self,
        prompt: str,
        image_path: Path,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        # Codex CLI image support — pass image path in prompt
        full_prompt = f"[Image: {image_path}]\n\n{prompt}"
        try:
            return await self.generate(full_prompt, system_prompt=system_prompt, model=model)
        except SummarizationError:
            raise
