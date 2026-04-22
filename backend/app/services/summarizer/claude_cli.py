"""Claude Code CLI provider — invokes CLI as subprocess."""

import asyncio
import json
import os
import time
from pathlib import Path

from app.config import Settings
from app.exceptions import (
    SubprocessNonZeroExitError,
    SubprocessNotFoundError,
    SubprocessTimeoutError,
    SummarizationError,
)
from app.services.summarizer.failure_log import log_failure
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse

STDERR_TRUNCATE = 500


def _maybe_log(
    *,
    cli_command: str,
    failure_type: str,
    section_id: int | None,
    book_id: int | None,
    stderr_full: str,
) -> None:
    try:
        settings = Settings()
    except Exception:  # pragma: no cover — defensive
        return
    if not settings.llm.stderr_log_enabled:
        return
    data_dir = settings.data.directory
    if not data_dir:
        return
    log_failure(
        Path(data_dir) / "summarization-failures.log",
        failure_type=failure_type,
        section_id=section_id,
        book_id=book_id,
        message=f"cli={cli_command} | {stderr_full.strip()[:2000]}",
    )


def _maybe_force_test_failure(
    cli_command: str,
    context: dict | None,
) -> None:
    """Raise a forced failure for the regression test suite (PD10).

    Activated only when ``BOOKCOMPANION_LLM__TEST_MODE=fail_section_<id>`` is
    set. Safe in production — default is ``None`` and the fast path is a
    single attribute read.
    """
    try:
        mode = Settings().llm.test_mode
    except Exception:  # pragma: no cover
        return
    if not mode or not mode.startswith("fail_section_"):
        return
    try:
        target_id = int(mode.rsplit("_", 1)[-1])
    except ValueError:
        return
    if context and context.get("section_id") == target_id:
        raise SubprocessNonZeroExitError(
            returncode=1,
            stderr_truncated="TEST MODE: forced failure",
            stderr_full="TEST MODE: forced failure",
        )


class ClaudeCodeCLIProvider(LLMProvider):
    def __init__(
        self,
        cli_command: str = "claude",
        default_model: str = "sonnet",
        default_timeout: int = 300,
        max_budget_usd: float | None = None,
        config_dir: str | None = None,
    ):
        self.cli_command = cli_command
        self.default_model = default_model
        self.default_timeout = default_timeout
        self.max_budget_usd = max_budget_usd
        self.config_dir = config_dir

    def _build_env(self) -> dict[str, str]:
        """Build environment for the subprocess, including CLAUDE_CONFIG_DIR if set."""
        env = os.environ.copy()
        if self.config_dir:
            env["CLAUDE_CONFIG_DIR"] = self.config_dir
        return env

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

        cmd = [
            self.cli_command,
            "-p",
            "-",  # Read prompt from stdin
            "--output-format",
            "json",
            "--model",
            model or self.default_model,
            "--print",
        ]
        if json_schema:
            cmd.extend(["--json-schema", json.dumps(json_schema)])
        if self.max_budget_usd:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
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

        effective_timeout = timeout or self.default_timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),  # Prompt via stdin
                timeout=effective_timeout,
            )
        except TimeoutError as e:
            proc.kill()
            _maybe_log(
                cli_command=self.cli_command,
                failure_type="cli_timeout",
                section_id=section_id,
                book_id=book_id,
                stderr_full=f"Timeout after {effective_timeout}s",
            )
            raise SubprocessTimeoutError(effective_timeout) from e

        latency_ms = int((time.monotonic() - start) * 1000)

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

        return self._parse_response(stdout.decode(), model or self.default_model, latency_ms)

    async def generate_with_image(
        self,
        prompt: str,
        image_path: Path,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        image_dir = str(image_path.parent)
        full_prompt = f"Read the image at {image_path.name} and {prompt}"
        cmd = [
            self.cli_command,
            "-p",
            full_prompt,
            "--add-dir",
            image_dir,
            "--permission-mode",
            "auto",
            "--output-format",
            "json",
            "--model",
            model or self.default_model,
            "--print",
        ]

        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.default_timeout,
            )
        except TimeoutError as e:
            proc.kill()
            raise SummarizationError("Image captioning timed out") from e

        latency_ms = int((time.monotonic() - start) * 1000)
        if proc.returncode != 0:
            raise SummarizationError(f"Image captioning failed: {stderr.decode()}")

        return self._parse_response(stdout.decode(), model or self.default_model, latency_ms)

    def _parse_response(self, raw: str, model: str, latency_ms: int) -> LLMResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # CLI may return raw text in --print mode
            return LLMResponse(content=raw.strip(), model=model, latency_ms=latency_ms)

        # Handle different response formats from CLI
        # When --json-schema is used, structured output is in "structured_output"
        structured = data.get("structured_output")
        if structured is not None:
            content = json.dumps(structured) if not isinstance(structured, str) else structured
        else:
            content = data.get("result", data.get("content", raw))
        usage = data.get("usage", {})
        return LLMResponse(
            content=content if isinstance(content, str) else json.dumps(content),
            model=data.get("model", model),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=latency_ms,
        )
