"""Codex CLI provider — invokes CLI as subprocess."""

import asyncio
import os
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
    _maybe_force_test_failure,
    _maybe_log,
)
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse


class CodexCLIProvider(LLMProvider):
    def __init__(
        self,
        cli_command: str = "codex",
        default_model: str = "o4-mini",
        default_timeout: int = 300,
        max_budget_usd: float | None = None,
    ):
        self.cli_command = cli_command
        self.default_model = default_model
        self.default_timeout = default_timeout
        self.max_budget_usd = max_budget_usd

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        json_schema: dict | None = None,
        timeout: int | None = None,
        context: dict | None = None,
    ) -> LLMResponse:
        _maybe_force_test_failure(self.cli_command, context)
        section_id = (context or {}).get("section_id")
        book_id = (context or {}).get("book_id")

        model = model or self.default_model
        timeout = timeout or self.default_timeout

        if json_schema:
            # Codex CLI doesn't support --json-schema; inject schema into prompt
            import json

            prompt = (
                f"{prompt}\n\nRespond with valid JSON matching this schema:\n"
                f"{json.dumps(json_schema, indent=2)}"
            )

        cmd = [
            self.cli_command,
            "-p",
            prompt,
            "--model",
            model,
        ]

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        start_time = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )
        except FileNotFoundError as e:
            _maybe_log(
                cli_command=self.cli_command,
                failure_type="cli_not_found",
                section_id=section_id,
                book_id=book_id,
                stderr_full=str(e),
            )
            raise SubprocessNotFoundError(self.cli_command) from e

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as e:
            proc.kill()
            _maybe_log(
                cli_command=self.cli_command,
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
                cli_command=self.cli_command,
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

        raw_output = stdout.decode().strip()
        latency_ms = int((time.monotonic() - start_time) * 1000)

        return LLMResponse(
            content=raw_output,
            model=model,
            input_tokens=None,
            output_tokens=None,
            latency_ms=latency_ms,
        )

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
