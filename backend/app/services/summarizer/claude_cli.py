"""Claude Code CLI provider — invokes CLI as subprocess."""

import asyncio
import json
import time
from pathlib import Path

from app.exceptions import SummarizationError
from app.services.summarizer.llm_provider import LLMProvider, LLMResponse


class ClaudeCodeCLIProvider(LLMProvider):
    def __init__(
        self,
        cli_command: str = "claude",
        default_model: str = "sonnet",
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
    ) -> LLMResponse:
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
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,  # Pass prompt via stdin
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),  # Prompt via stdin
                timeout=timeout or self.default_timeout,
            )
        except TimeoutError:
            proc.kill()
            raise SummarizationError(
                f"Claude CLI timed out after {timeout or self.default_timeout}s"
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        if proc.returncode != 0:
            raise SummarizationError(f"Claude CLI failed (rc={proc.returncode}): {stderr.decode()}")

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
        except TimeoutError:
            proc.kill()
            raise SummarizationError("Image captioning timed out")

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
