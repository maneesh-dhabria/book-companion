"""Tests for image captioning via Claude Code CLI."""

import pytest
from unittest.mock import AsyncMock

from app.services.summarizer.image_captioner import ImageCaptioner
from app.services.summarizer.llm_provider import LLMResponse


@pytest.mark.asyncio
async def test_caption_image():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.return_value = LLMResponse(
        content="A diagram showing the hierarchy of military strategy.",
        model="sonnet",
        latency_ms=500,
    )
    captioner = ImageCaptioner(llm_provider=mock_llm)
    caption = await captioner.caption_image(
        image_data=b"fake_image_data",
        mime_type="image/png",
        context="This section discusses military strategy.",
    )
    assert "strategy" in caption.lower() or "hierarchy" in caption.lower()


@pytest.mark.asyncio
async def test_caption_failure_returns_empty():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.side_effect = Exception("CLI failed")
    captioner = ImageCaptioner(llm_provider=mock_llm)
    caption = await captioner.caption_image(
        image_data=b"fake", mime_type="image/png", context="test"
    )
    assert caption == ""  # Non-blocking: returns empty on failure
