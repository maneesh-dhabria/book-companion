"""Tests for image captioning via Claude Code CLI."""

import json

import pytest
from unittest.mock import AsyncMock

from app.services.summarizer.image_captioner import ImageCaptioner, should_skip_image
from app.services.summarizer.llm_provider import LLMResponse


# --- Pre-filter tests ---

def test_skip_tiny_image():
    assert should_skip_image(
        data=b"x" * 100, width=20, height=20, filename="img.png"
    ) is True


def test_skip_small_filesize():
    assert should_skip_image(
        data=b"x" * 1000, width=200, height=200, filename="chart.png"
    ) is True


def test_skip_decorative_filename():
    assert should_skip_image(
        data=b"x" * 10000, width=200, height=200, filename="separator.png"
    ) is True
    assert should_skip_image(
        data=b"x" * 10000, width=200, height=200, filename="header-divider.gif"
    ) is True
    assert should_skip_image(
        data=b"x" * 10000, width=200, height=200, filename="bullet_icon.png"
    ) is True


def test_skip_cover_image():
    assert should_skip_image(
        data=b"x" * 50000, width=600, height=900, filename="cover.jpg"
    ) is True
    assert should_skip_image(
        data=b"x" * 50000, width=600, height=900, filename="book-cover.png"
    ) is True


def test_keep_normal_image():
    assert should_skip_image(
        data=b"x" * 10000, width=400, height=300, filename="figure_1.png"
    ) is False


def test_keep_image_with_no_dimensions():
    assert should_skip_image(
        data=b"x" * 10000, width=None, height=None, filename="chart.png"
    ) is False


# --- Caption tests ---

@pytest.mark.asyncio
async def test_caption_image_returns_caption_and_relevance():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.return_value = LLMResponse(
        content=json.dumps({
            "caption": "A diagram showing Porter's Five Forces framework.",
            "relevance": "key",
        }),
        model="sonnet",
        latency_ms=500,
        input_tokens=100,
        output_tokens=50,
    )
    captioner = ImageCaptioner(llm_provider=mock_llm)
    result = await captioner.caption_image(
        image_data=b"fake_image_data",
        mime_type="image/png",
        context="Competitive strategy frameworks.",
    )
    assert result["caption"] == "A diagram showing Porter's Five Forces framework."
    assert result["relevance"] == "key"


@pytest.mark.asyncio
async def test_caption_failure_returns_empty_result():
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.side_effect = Exception("CLI failed")
    captioner = ImageCaptioner(llm_provider=mock_llm)
    result = await captioner.caption_image(
        image_data=b"fake", mime_type="image/png", context="test"
    )
    assert result["caption"] == ""
    assert result["relevance"] == "decorative"


@pytest.mark.asyncio
async def test_caption_section_images_with_prefilter():
    """Pre-filter should skip tiny images, caption the rest."""
    mock_llm = AsyncMock()
    mock_llm.generate_with_image.return_value = LLMResponse(
        content=json.dumps({
            "caption": "A chart showing market share data.",
            "relevance": "key",
        }),
        model="sonnet",
        latency_ms=500,
    )
    captioner = ImageCaptioner(llm_provider=mock_llm)
    images = [
        {
            "id": 1, "data": b"x" * 100, "mime_type": "image/png",
            "width": 10, "height": 10, "filename": "dot.png",
            "alt_text": None, "content_hash": None,
        },
        {
            "id": 2, "data": b"x" * 10000, "mime_type": "image/png",
            "width": 400, "height": 300, "filename": "figure1.png",
            "alt_text": None, "content_hash": None,
        },
    ]
    results = await captioner.caption_section_images(
        images=images, section_context="Market analysis"
    )
    assert 1 not in results
    assert 2 in results
    assert results[2]["relevance"] == "key"
    mock_llm.generate_with_image.assert_called_once()


@pytest.mark.asyncio
async def test_dedup_skips_already_captioned_hash():
    """If two images share the same content_hash and one is already captioned, reuse."""
    mock_llm = AsyncMock()
    captioner = ImageCaptioner(llm_provider=mock_llm)
    images = [
        {"id": 1, "data": b"x" * 10000, "mime_type": "image/png",
         "width": 400, "height": 300, "filename": "fig1.png",
         "alt_text": None, "content_hash": "abc123",
         "existing_caption": "A framework diagram.", "existing_relevance": "key"},
        {"id": 2, "data": b"x" * 10000, "mime_type": "image/png",
         "width": 400, "height": 300, "filename": "fig1_copy.png",
         "alt_text": None, "content_hash": "abc123",
         "existing_caption": None, "existing_relevance": None},
    ]
    results = await captioner.caption_section_images(
        images=images, section_context="Test"
    )
    mock_llm.generate_with_image.assert_not_called()
    assert results[1]["caption"] == "A framework diagram."
    assert results[2]["caption"] == "A framework diagram."
