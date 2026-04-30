"""Claude Code CLI provider — invokes CLI as subprocess."""

import asyncio
import json
import os
import time
from pathlib import Path

import structlog

from app.config import Settings
from app.exceptions import (
    SubprocessNonZeroExitError,
    SubprocessNotFoundError,
    SubprocessTimeoutError,
    SummarizationError,
)
from app.services.summarizer.failure_log import log_failure
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse

log = structlog.get_logger(__name__)

STDERR_TRUNCATE = 500

# Module-level guard so each unique config_dir is logged once per process (P12).
_LOGGED_CONFIG_DIRS: set[str] = set()


def _maybe_log(
    *,
    binary: str,
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
        message=f"cli={binary} | {stderr_full.strip()[:2000]}",
    )


def _maybe_force_test_failure(
    binary: str,
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


def _build_env(config_dir: Path | None, env_var: str) -> dict[str, str]:
    env = os.environ.copy()
    if config_dir is not None:
        cfg = Path(config_dir).expanduser()
        cfg.mkdir(parents=True, exist_ok=True)
        cfg_str = str(cfg)
        if cfg_str not in _LOGGED_CONFIG_DIRS:
            log.info("config_dir_initialized", path=cfg_str, env_var=env_var)
            _LOGGED_CONFIG_DIRS.add(cfg_str)
        env[env_var] = cfg_str
    return env


class ClaudeCodeCLIProvider(LLMProvider):
    BINARY = "claude"

    def __init__(
        self,
        default_model: str = "sonnet",
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

        cmd = [
            self.BINARY,
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

        env = _build_env(self.config_dir, "CLAUDE_CONFIG_DIR")

        start = time.monotonic()
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

        # Track this process so the queue worker can SIGTERM it on cancel
        # (FR-B15). Cleared in finally so the provider is idle between calls.
        self._track_active(proc)

        effective_timeout = timeout or self.default_timeout
        try:
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode()),  # Prompt via stdin
                    timeout=effective_timeout,
                )
            except TimeoutError as e:
                proc.kill()
                _maybe_log(
                    binary=self.BINARY,
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

            return self._parse_response(stdout.decode(), model or self.default_model, latency_ms)
        finally:
            self._track_active(None)

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
            self.BINARY,
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

        env = _build_env(self.config_dir, "CLAUDE_CONFIG_DIR")

        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
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
