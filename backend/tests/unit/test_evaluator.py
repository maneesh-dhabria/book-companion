"""Tests for the 16-assertion evaluation service."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.summarizer.evaluator import ASSERTION_REGISTRY, EvalService
from app.services.summarizer.llm_provider import LLMResponse


def test_all_16_assertions_registered():
    assert len(ASSERTION_REGISTRY) == 16
    expected = {
        "no_hallucinated_facts",
        "no_contradictions",
        "accurate_quotes",
        "cross_summary_consistency",
        "covers_main_argument",
        "covers_key_concepts",
        "covers_frameworks",
        "covers_examples",
        "standalone_readable",
        "logical_flow",
        "no_dangling_references",
        "not_generic",
        "preserves_author_terminology",
        "has_key_concepts",
        "reasonable_length",
        "image_refs_preserved",
    }
    assert set(ASSERTION_REGISTRY.keys()) == expected


def test_assertion_categories():
    critical = [a for a, meta in ASSERTION_REGISTRY.items() if meta["category"] == "critical"]
    important = [a for a, meta in ASSERTION_REGISTRY.items() if meta["category"] == "important"]
    advisory = [a for a, meta in ASSERTION_REGISTRY.items() if meta["category"] == "advisory"]
    assert len(critical) == 4  # Faithfulness
    assert len(important) == 6  # Completeness + Specificity
    assert len(advisory) == 6  # Coherence + Format


@pytest.mark.asyncio
async def test_eval_result_parsing():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({"passed": True, "reasoning": "All claims supported."}),
        model="sonnet",
        latency_ms=200,
    )
    mock_session = AsyncMock()
    service = EvalService(db=mock_session, llm=mock_llm, config=MagicMock())
    result = await service._run_single_assertion(
        assertion_name="no_hallucinated_facts",
        source_text="Source content here",
        summary_text="Summary content here",
        section_id=1,
    )
    assert result["passed"] is True
    assert result["assertion_name"] == "no_hallucinated_facts"


@pytest.mark.asyncio
async def test_critical_failure_triggers_retry():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content=json.dumps({"passed": False, "reasoning": "Hallucinated fact found."}),
        model="sonnet",
        latency_ms=200,
    )
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.llm.max_retries = 2

    service = EvalService(db=mock_session, llm=mock_llm, config=mock_config)
    result = service._should_auto_retry(
        {"no_hallucinated_facts": {"passed": False}},
        retry_count=0,
        max_retries=2,
    )
    assert result is True  # Should retry on critical failure
