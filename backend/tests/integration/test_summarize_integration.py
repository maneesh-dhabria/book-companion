"""Integration tests for summarization with real Claude Code CLI.
These tests make actual LLM calls — run with: pytest -m integration_llm"""

import pytest

pytestmark = pytest.mark.integration_llm


@pytest.mark.asyncio
async def test_summarize_single_section(db_session, test_settings):
    """Summarize one section, verify output structure."""
    # Requires a book already added. Use small test content.
    pass  # Implement after Tasks 19+21 are complete


@pytest.mark.asyncio
async def test_quick_summary(db_session, test_settings):
    """Quick summary mode on a small book."""
    pass  # Implement after Task 19


@pytest.mark.asyncio
async def test_image_captioning(db_session, test_settings):
    """Caption a test image via real CLI."""
    pass  # Implement after Task 17
