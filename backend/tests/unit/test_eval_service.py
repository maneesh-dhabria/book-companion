"""Tests for EvalService preset-aware assertion skipping."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.summarizer.evaluator import EvalService


@pytest.fixture
def eval_service():
    db = AsyncMock()
    llm = AsyncMock()
    config = MagicMock()
    config.llm.cross_summary_consistency = False
    return EvalService(db, llm, config)


def test_preset_skip_assertions(eval_service):
    """Assertions in skip list return passed + skipped."""
    skip_data = {"skip_assertions": ["has_key_concepts", "image_refs_preserved"]}
    with (
        patch("builtins.open", create=True),
        patch("yaml.safe_load", return_value=skip_data),
        patch("pathlib.Path.exists", return_value=True),
    ):
        skip_set = eval_service._load_skip_assertions("tweet_thread")
    assert "has_key_concepts" in skip_set
    assert "image_refs_preserved" in skip_set

    result = eval_service._skipped_result("has_key_concepts", "tweet_thread", 1, 1, "run-1")
    assert result["passed"] is True
    assert result["skipped"] is True
    assert "tweet_thread" in result["reasoning"]
    assert result["category"] == "advisory"


def test_preset_no_skip_list(eval_service):
    """Preset without skip_assertions runs all assertions (empty set)."""
    no_skip_data = {"facets": {"style": "narrative"}}
    with (
        patch("builtins.open", create=True),
        patch("yaml.safe_load", return_value=no_skip_data),
        patch("pathlib.Path.exists", return_value=True),
    ):
        skip_set = eval_service._load_skip_assertions("academic_detailed")
    assert skip_set == set()


def test_preset_none_no_skip(eval_service):
    """No preset means no assertions skipped."""
    skip_set = eval_service._load_skip_assertions(None)
    assert skip_set == set()


def test_unknown_assertion_in_skip_list_ignored(eval_service, capsys):
    """Unknown assertion name in skip list is logged but does not crash."""
    skip_data = {"skip_assertions": ["nonexistent_assertion", "has_key_concepts"]}
    with (
        patch("builtins.open", create=True),
        patch("yaml.safe_load", return_value=skip_data),
        patch("pathlib.Path.exists", return_value=True),
    ):
        skip_set = eval_service._load_skip_assertions("test_preset")
    # Unknown assertion filtered out, only known ones in result
    assert "has_key_concepts" in skip_set
    assert "nonexistent_assertion" not in skip_set
    captured = capsys.readouterr()
    assert "unknown_skip_assertions" in captured.out


@pytest.mark.asyncio
async def test_diagnostic_fields_stored(eval_service):
    """LLM returns likely_cause + suggestion, verify stored on trace."""
    mock_response = MagicMock()
    mock_response.content = '{"passed": false, "reasoning": "test", "likely_cause": "content_quality", "suggestion": "fix it"}'
    mock_response.model = "test-model"
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.latency_ms = 1000
    eval_service.llm.generate = AsyncMock(return_value=mock_response)

    result = await eval_service._run_single_assertion(
        "covers_main_argument", "source text", "summary text", 1
    )

    # Check the trace was created with diagnostic fields
    trace_call = eval_service.db.add.call_args[0][0]
    assert trace_call.likely_cause == "content_quality"
    assert trace_call.suggestion == "fix it"


@pytest.mark.asyncio
async def test_diagnostic_fields_null_on_pass(eval_service):
    """Passing assertion has null diagnostic fields."""
    mock_response = MagicMock()
    mock_response.content = (
        '{"passed": true, "reasoning": "good", "likely_cause": null, "suggestion": null}'
    )
    mock_response.model = "test-model"
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.latency_ms = 1000
    eval_service.llm.generate = AsyncMock(return_value=mock_response)

    result = await eval_service._run_single_assertion(
        "covers_main_argument", "source text", "summary text", 1
    )

    trace_call = eval_service.db.add.call_args[0][0]
    assert trace_call.likely_cause is None
    assert trace_call.suggestion is None


@pytest.mark.asyncio
async def test_diagnostic_fields_missing_graceful(eval_service):
    """LLM omits diagnostic fields, no crash."""
    mock_response = MagicMock()
    mock_response.content = '{"passed": false, "reasoning": "test"}'
    mock_response.model = "test-model"
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.latency_ms = 1000
    eval_service.llm.generate = AsyncMock(return_value=mock_response)

    result = await eval_service._run_single_assertion(
        "covers_main_argument", "source text", "summary text", 1
    )

    trace_call = eval_service.db.add.call_args[0][0]
    assert trace_call.likely_cause is None
    assert trace_call.suggestion is None
    assert result["passed"] is False
