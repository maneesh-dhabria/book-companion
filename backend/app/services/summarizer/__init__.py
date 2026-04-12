"""LLM provider factory and auto-detection."""

import shutil

from app.services.summarizer.llm_provider import LLMProvider


def detect_llm_provider() -> str | None:
    """Auto-detect available CLI providers on $PATH."""
    if shutil.which("claude"):
        return "claude"
    if shutil.which("codex"):
        return "codex"
    return None


def create_llm_provider(provider: str | None, **kwargs) -> LLMProvider | None:
    """Create the appropriate LLM provider instance."""
    if provider == "claude" or provider == "claude_cli":
        from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider

        return ClaudeCodeCLIProvider(**kwargs)
    elif provider == "codex":
        from app.services.summarizer.codex_cli import CodexCLIProvider

        return CodexCLIProvider(**kwargs)
    return None
