"""Codex CLI provider — invokes CLI as subprocess."""

import asyncio
import os
import time
from pathlib import Path

from app.exceptions import SummarizationError
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse


class CodexCLIProvider(LLMProvider):
    def __init__(
        self,
        cli_command: str = "codex",
        default_model: str = "o4-mini",
        default_timeout: int = 300,
        max_budget_usd: float | None = None,
        config_dir: str | None = None,
    ):
        self.cli_command = cli_command
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
    ) -> LLMResponse:
        model = model or self.default_model
        timeout = timeout or self.default_timeout

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
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as e:
            raise SummarizationError(
                f"Codex CLI timed out after {timeout}s"
            ) from e

        if proc.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise SummarizationError(f"Codex CLI failed (exit {proc.returncode}): {error_msg}")

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
        return await self.generate(full_prompt, system_prompt=system_prompt, model=model)
