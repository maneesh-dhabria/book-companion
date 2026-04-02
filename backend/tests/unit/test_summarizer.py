"""Tests for summarizer service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.summarizer.summarizer_service import SummarizerService
from app.services.summarizer.llm_provider import LLMResponse
from app.db.models import BookSection, SummaryStatus


def make_mock_section(section_id=1, title="Chapter 1", content="Test content " * 50):
    section = MagicMock(spec=BookSection)
    section.id = section_id
    section.title = title
    section.content_md = content
    section.content_token_count = len(content.split())
    section.summary_status = SummaryStatus.PENDING
    section.summary_md = None
    section.user_edited = False
    section.images = []
    return section


@pytest.mark.asyncio
async def test_cumulative_context_generation():
    service = SummarizerService.__new__(SummarizerService)
    prior = [
        MagicMock(title="Ch1", summary_md="Chapter 1 covers the basics of strategy."),
        MagicMock(title="Ch2", summary_md="Chapter 2 discusses tactical warfare."),
    ]
    context = service._build_cumulative_context(prior)
    assert "Ch1" in context
    assert "Ch2" in context
    assert len(context) < 3000  # Should be compact


@pytest.mark.asyncio
async def test_compression_ratio_for_detail_levels():
    service = SummarizerService.__new__(SummarizerService)
    assert service._get_compression_target("brief") == 10
    assert service._get_compression_target("standard") == 20
    assert service._get_compression_target("detailed") == 30


@pytest.mark.asyncio
async def test_summarize_section_calls_llm():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({
            "key_concepts": ["concept1", "concept2", "concept3"],
            "detailed_summary": "This section covers strategy.",
            "frameworks": ["Framework A"],
            "key_quotes": ["Quote 1"],
            "concepts": [],
        }),
        model="sonnet",
        latency_ms=1000,
    )
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.summarization.default_detail_level = "standard"
    mock_config.summarization.prompt_version = "v1"

    service = SummarizerService(
        db=mock_session, llm=mock_llm, config=mock_config
    )
    section = make_mock_section()
    result = await service._summarize_single_section(
        section=section, prior_sections=[], detail_level="standard"
    )
    assert "strategy" in result.lower()
    mock_llm.generate.assert_called_once()
