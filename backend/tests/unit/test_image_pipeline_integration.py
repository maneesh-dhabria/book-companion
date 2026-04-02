"""Regression tests for image pipeline integration."""

import hashlib
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.config import Settings
from app.db.models import Image, ImageRelevance
from app.services.parser.base import ParsedImage
from app.services.parser.epub_parser import EPUBParser
from app.services.summarizer.image_captioner import (
    ImageCaptioner,
    compute_content_hash,
    should_skip_image,
)
from app.services.summarizer.llm_provider import LLMResponse


class TestPreFilter:
    def test_skips_sub_5kb_images(self):
        assert should_skip_image(
            data=b"x" * 4000, width=200, height=200, filename="fig.png"
        ) is True

    def test_passes_5kb_plus_images(self):
        assert should_skip_image(
            data=b"x" * 6000, width=200, height=200, filename="fig.png"
        ) is False

    def test_skips_cover_variants(self):
        for name in ["cover.jpg", "book-cover.png", "front_cover.jpeg"]:
            assert should_skip_image(
                data=b"x" * 10000, width=600, height=900, filename=name
            ) is True

    def test_no_dimensions_not_skipped(self):
        assert should_skip_image(
            data=b"x" * 10000, width=None, height=None, filename="fig.png"
        ) is False


class TestContentHash:
    def test_returns_sha256_hex(self):
        data = b"test image data"
        expected = hashlib.sha256(data).hexdigest()
        assert compute_content_hash(data) == expected
        assert len(compute_content_hash(data)) == 64


class TestImageModel:
    def test_new_fields_accepted(self):
        img = Image(
            section_id=1,
            data=b"fake",
            mime_type="image/png",
            relevance="key",
            alt_text="A diagram",
            content_hash="abc123",
        )
        assert img.relevance == "key"
        assert img.alt_text == "A diagram"
        assert img.content_hash == "abc123"

    def test_relevance_enum_string_values(self):
        assert ImageRelevance.KEY == "key"
        assert ImageRelevance.SUPPLEMENTARY == "supplementary"
        assert ImageRelevance.DECORATIVE == "decorative"


class TestParsedImageAltText:
    def test_alt_text_defaults_none(self):
        img = ParsedImage(data=b"x", mime_type="image/png")
        assert img.alt_text is None

    def test_alt_text_accepted(self):
        img = ParsedImage(
            data=b"x", mime_type="image/png", alt_text="Five Forces"
        )
        assert img.alt_text == "Five Forces"


class TestEPUBAltText:
    def test_alt_before_src(self):
        parser = EPUBParser.__new__(EPUBParser)
        html = '<img alt="Diagram" src="fig.png"/>'
        result = parser._extract_alt_text(html)
        assert result.get("fig.png") == "Diagram"

    def test_filters_generic_alt(self):
        parser = EPUBParser.__new__(EPUBParser)
        html = '<img src="a.png" alt="image"/>'
        result = parser._extract_alt_text(html)
        assert "a.png" not in result


@pytest.mark.asyncio
class TestCaptionerReturnType:
    async def test_returns_dict_on_success(self):
        mock_llm = AsyncMock()
        mock_llm.generate_with_image.return_value = LLMResponse(
            content=json.dumps({"caption": "A chart.", "relevance": "key"}),
            model="sonnet",
            latency_ms=100,
        )
        captioner = ImageCaptioner(llm_provider=mock_llm)
        result = await captioner.caption_image(
            image_data=b"x" * 100, mime_type="image/png"
        )
        assert isinstance(result, dict)
        assert "caption" in result
        assert "relevance" in result

    async def test_json_decode_error_returns_supplementary(self):
        mock_llm = AsyncMock()
        mock_llm.generate_with_image.return_value = LLMResponse(
            content="Not valid JSON but a good description",
            model="sonnet",
            latency_ms=100,
        )
        captioner = ImageCaptioner(llm_provider=mock_llm)
        result = await captioner.caption_image(
            image_data=b"x" * 100, mime_type="image/png"
        )
        assert result["relevance"] == "supplementary"
        assert "Not valid JSON" in result["caption"]

    async def test_failure_returns_decorative(self):
        mock_llm = AsyncMock()
        mock_llm.generate_with_image.side_effect = Exception("fail")
        captioner = ImageCaptioner(llm_provider=mock_llm)
        result = await captioner.caption_image(
            image_data=b"x", mime_type="image/png"
        )
        assert result["caption"] == ""
        assert result["relevance"] == "decorative"


class TestSummarizerConstructor:
    def test_accepts_captioner(self):
        from app.services.summarizer.summarizer_service import SummarizerService

        mock_captioner = MagicMock()
        svc = SummarizerService(
            db=MagicMock(), llm=MagicMock(), config=MagicMock(),
            captioner=mock_captioner,
        )
        assert svc.captioner is mock_captioner

    def test_captioner_defaults_none(self):
        from app.services.summarizer.summarizer_service import SummarizerService

        svc = SummarizerService(
            db=MagicMock(), llm=MagicMock(), config=MagicMock(),
        )
        assert svc.captioner is None


class TestConfigToggle:
    def test_images_config_exists(self):
        settings = Settings()
        assert hasattr(settings, "images")
        assert settings.images.captioning_enabled is True


@pytest.mark.asyncio
class TestCaptionSectionImages:
    async def test_skips_prefiltered_and_captions_rest(self):
        mock_llm = AsyncMock()
        mock_llm.generate_with_image.return_value = LLMResponse(
            content=json.dumps({"caption": "A diagram.", "relevance": "key"}),
            model="sonnet",
            latency_ms=50,
        )
        captioner = ImageCaptioner(llm_provider=mock_llm)

        images = [
            {
                "id": 1,
                "data": b"x" * 3000,  # Too small, should be skipped
                "mime_type": "image/png",
                "width": 200,
                "height": 200,
                "filename": "tiny.png",
                "alt_text": None,
                "content_hash": "hash1",
                "existing_caption": None,
                "existing_relevance": None,
            },
            {
                "id": 2,
                "data": b"x" * 10000,  # Big enough
                "mime_type": "image/png",
                "width": 400,
                "height": 300,
                "filename": "chart.png",
                "alt_text": None,
                "content_hash": "hash2",
                "existing_caption": None,
                "existing_relevance": None,
            },
        ]

        results = await captioner.caption_section_images(
            images=images, section_context="Chapter 1"
        )

        assert 1 not in results  # Pre-filtered
        assert 2 in results
        assert results[2]["caption"] == "A diagram."
        mock_llm.generate_with_image.assert_called_once()

    async def test_dedup_reuses_existing_caption(self):
        mock_llm = AsyncMock()
        captioner = ImageCaptioner(llm_provider=mock_llm)

        images = [
            {
                "id": 1,
                "data": b"x" * 10000,
                "mime_type": "image/png",
                "width": 200,
                "height": 200,
                "filename": "fig.png",
                "alt_text": None,
                "content_hash": "shared_hash",
                "existing_caption": "Already captioned.",
                "existing_relevance": "key",
            },
            {
                "id": 2,
                "data": b"x" * 10000,
                "mime_type": "image/png",
                "width": 200,
                "height": 200,
                "filename": "fig_copy.png",
                "alt_text": None,
                "content_hash": "shared_hash",
                "existing_caption": None,
                "existing_relevance": None,
            },
        ]

        results = await captioner.caption_section_images(
            images=images, section_context="Chapter 1"
        )

        assert results[1]["caption"] == "Already captioned."
        assert results[2]["caption"] == "Already captioned."
        mock_llm.generate_with_image.assert_not_called()
