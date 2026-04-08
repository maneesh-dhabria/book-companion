"""Tests for deterministic eval assertions (reasonable_length, has_key_concepts, image_refs_preserved)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.summarizer.evaluator import EvalService


@pytest.fixture
def eval_service():
    db = AsyncMock()
    llm = AsyncMock()
    config = MagicMock()
    config.llm.cross_summary_consistency = False
    return EvalService(db, llm, config)


# --- reasonable_length tests ---


@pytest.mark.asyncio
async def test_reasonable_length_within_range(eval_service):
    source = "x" * 1000
    summary = "y" * 200  # 20% of 1000 — within standard (15-25%)
    result = await eval_service._check_reasonable_length(
        source, summary, {"compression": "standard"}, 1, 1, "run-1"
    )
    assert result["passed"] is True
    assert result["assertion_name"] == "reasonable_length"
    assert result["category"] == "advisory"


@pytest.mark.asyncio
async def test_reasonable_length_too_short(eval_service):
    source = "x" * 1000
    summary = "y" * 20  # 2% — well below standard min (15% * 0.5 = 7.5% = 75 chars)
    result = await eval_service._check_reasonable_length(
        source, summary, {"compression": "standard"}, 1, 1, "run-1"
    )
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_reasonable_length_too_long(eval_service):
    source = "x" * 1000
    summary = "y" * 800  # 80% — well above standard max (25% * 1.5 = 37.5% = 375 chars)
    result = await eval_service._check_reasonable_length(
        source, summary, {"compression": "standard"}, 1, 1, "run-1"
    )
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_reasonable_length_empty_source(eval_service):
    result = await eval_service._check_reasonable_length(
        "", "some summary", {"compression": "standard"}, 1, 1, "run-1"
    )
    assert result["passed"] is True
    assert "nothing to evaluate" in result["reasoning"]


@pytest.mark.asyncio
async def test_reasonable_length_empty_summary(eval_service):
    result = await eval_service._check_reasonable_length(
        "x" * 1000, "", {"compression": "standard"}, 1, 1, "run-1"
    )
    assert result["passed"] is False
    assert "empty" in result["reasoning"].lower()


@pytest.mark.asyncio
async def test_reasonable_length_brief_preset(eval_service):
    source = "x" * 1000
    summary = "y" * 80  # 8% — within brief range (5-15%) with ±50% tolerance
    result = await eval_service._check_reasonable_length(
        source, summary, {"compression": "brief"}, 1, 1, "run-1"
    )
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_reasonable_length_detailed_preset(eval_service):
    source = "x" * 1000
    summary = "y" * 350  # 35% — within detailed range (25-40%) with ±50% tolerance
    result = await eval_service._check_reasonable_length(
        source, summary, {"compression": "detailed"}, 1, 1, "run-1"
    )
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_reasonable_length_tweet_thread(eval_service):
    source = "x" * 1000
    summary = "y" * 50  # 5% — within tweet_thread range (2-8%) with tolerance
    result = await eval_service._check_reasonable_length(
        source, summary, {"style": "tweet_thread"}, 1, 1, "run-1"
    )
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_reasonable_length_no_facets_defaults_standard(eval_service):
    source = "x" * 1000
    summary = "y" * 200  # 20% — within standard defaults
    result = await eval_service._check_reasonable_length(source, summary, None, 1, 1, "run-1")
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_reasonable_length_short_section_floor(eval_service):
    source = "x" * 100
    # For standard: min = max(50, 100 * 15/100 * 0.5) = max(50, 7) = 50
    # max = 100 * 25/100 * 1.5 = 37 ... so max < floor
    # Actually: min_chars = max(50, 7) = 50, max_chars = 37
    # A 55-char summary is >= 50 but > 37, so it fails.
    # Let's test that the 50-char floor is applied for min:
    summary = "y" * 55
    result = await eval_service._check_reasonable_length(
        source, summary, {"compression": "standard"}, 1, 1, "run-1"
    )
    # min_chars=50, max_chars=37 — so 55 > 37 => fail
    # This is correct: very short sources can't really be compressed further
    assert result["passed"] is False

    # A summary exactly at 50 chars also fails (50 > 37)
    summary2 = "y" * 30
    result2 = await eval_service._check_reasonable_length(
        source, summary2, {"compression": "standard"}, 1, 1, "run-1"
    )
    # 30 < 50 (floor) => fail
    assert result2["passed"] is False


@pytest.mark.asyncio
async def test_deterministic_trace_has_null_prompt(eval_service):
    source = "x" * 1000
    summary = "y" * 200
    await eval_service._check_reasonable_length(
        source, summary, {"compression": "standard"}, 1, 1, "run-1"
    )
    # Check that db.add was called with an EvalTrace having deterministic metadata
    call_args = eval_service.db.add.call_args
    trace = call_args[0][0]
    assert trace.prompt_sent is None
    assert trace.model_used == "deterministic"
    assert trace.latency_ms == 0
    assert trace.input_tokens == 0
    assert trace.output_tokens == 0
    assert trace.prompt_version == "deterministic"
    assert trace.llm_response == ""


# --- has_key_concepts tests ---


@pytest.mark.asyncio
async def test_has_key_concepts_heading_found(eval_service):
    summary = "Some intro text.\n\n## Key Concepts\n\nSome concepts here."
    result = await eval_service._check_has_key_concepts(summary, 1, 1, "run-1")
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_has_key_concepts_core_ideas_heading(eval_service):
    summary = "Some intro text.\n\n## Core Ideas\n\nSome ideas here."
    result = await eval_service._check_has_key_concepts(summary, 1, 1, "run-1")
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_has_key_concepts_bold_terms(eval_service):
    summary = (
        "**Alpha**: First concept description.\n"
        "**Beta**: Second concept description.\n"
        "**Gamma**: Third concept description.\n"
    )
    result = await eval_service._check_has_key_concepts(summary, 1, 1, "run-1")
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_has_key_concepts_two_bold_terms(eval_service):
    summary = "**Alpha**: First concept description.\n**Beta**: Second concept description.\n"
    result = await eval_service._check_has_key_concepts(summary, 1, 1, "run-1")
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_has_key_concepts_no_structure(eval_service):
    summary = (
        "This is a plain prose summary without any structured key concepts. "
        "It just describes the chapter content in paragraph form."
    )
    result = await eval_service._check_has_key_concepts(summary, 1, 1, "run-1")
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_has_key_concepts_bullets_with_bold_leads(eval_service):
    summary = (
        "Some intro text.\n\n"
        "- **Concept A**: Description of concept A\n"
        "- **Concept B**: Description of concept B\n"
        "- **Concept C**: Description of concept C\n"
    )
    result = await eval_service._check_has_key_concepts(summary, 1, 1, "run-1")
    assert result["passed"] is True


# --- image_refs tests ---


@pytest.mark.asyncio
async def test_image_refs_no_images(eval_service):
    source = "This is a text-only source with no images."
    summary = "This is a summary."
    result = await eval_service._check_image_refs_preserved(source, summary, 0, 1, 1, "run-1")
    assert result["passed"] is True
    assert "nothing to preserve" in result["reasoning"]


@pytest.mark.asyncio
async def test_image_refs_images_mentioned(eval_service):
    source = "Some text with an image ![my image](figure1.png) and more text."
    summary = "The chapter includes a diagram showing the relationship between concepts."
    result = await eval_service._check_image_refs_preserved(source, summary, 0, 1, 1, "run-1")
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_image_refs_images_not_mentioned(eval_service):
    source = "Some text with an image ![my image](figure1.png) and more text."
    summary = "The chapter discusses various concepts in detail."
    result = await eval_service._check_image_refs_preserved(source, summary, 0, 1, 1, "run-1")
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_image_refs_uses_image_count_param(eval_service):
    source = "This is plain text with no image references at all."
    summary = "The chapter discusses concepts."
    # image_count=3 should trigger the check even though source has no patterns
    result = await eval_service._check_image_refs_preserved(source, summary, 3, 1, 1, "run-1")
    assert result["passed"] is False

    # Now with a visual keyword in summary
    summary_with_visual = "The chapter includes a figure illustrating the concept."
    result2 = await eval_service._check_image_refs_preserved(
        source, summary_with_visual, 3, 1, 1, "run-1"
    )
    assert result2["passed"] is True


@pytest.mark.asyncio
async def test_image_refs_word_boundary_matching(eval_service):
    """Visual keywords should match on word boundaries, including plurals."""
    source = "See ![img](x.png) here"
    # "visuals" should match (plural of "visual")
    result = await eval_service._check_image_refs_preserved(
        source, "The section includes key visuals.", 0, 1, 1, "run-1"
    )
    assert result["passed"] is True

    # "figures" should match
    result2 = await eval_service._check_image_refs_preserved(
        source, "Several figures are discussed.", 0, 1, 1, "run-1"
    )
    assert result2["passed"] is True


@pytest.mark.asyncio
async def test_eval_run_id_generated_when_none(eval_service):
    """evaluate_summary generates eval_run_id when not provided."""
    mock_response = MagicMock()
    mock_response.content = (
        '{"passed": true, "reasoning": "ok", "likely_cause": null, "suggestion": null}'
    )
    mock_response.model = "test-model"
    mock_response.input_tokens = 10
    mock_response.output_tokens = 5
    mock_response.latency_ms = 100
    eval_service.llm.generate = AsyncMock(return_value=mock_response)

    result = await eval_service.evaluate_summary(
        section_id=1,
        source_text="source",
        summary_text="## Key Concepts\n\n**A**: desc\n**B**: desc\n**C**: desc",
        preset_name="practitioner_bullets",
    )
    assert "eval_run_id" in result
    assert result["eval_run_id"] is not None
    assert len(result["eval_run_id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_reference_section_skips_covers_examples(eval_service):
    """Glossary section type should skip covers_examples assertion."""
    mock_response = MagicMock()
    mock_response.content = (
        '{"passed": true, "reasoning": "ok", "likely_cause": null, "suggestion": null}'
    )
    mock_response.model = "test-model"
    mock_response.input_tokens = 10
    mock_response.output_tokens = 5
    mock_response.latency_ms = 100
    eval_service.llm.generate = AsyncMock(return_value=mock_response)

    result = await eval_service.evaluate_summary(
        section_id=1,
        source_text="Glossary content" * 100,
        summary_text="## Key Concepts\n\n**A**: x\n**B**: y\n**C**: z\n" + "summary " * 50,
        section_type="glossary",
    )
    assertions = result["assertions"]
    # covers_examples should be skipped for glossary
    assert assertions["covers_examples"].get("skipped") is True


@pytest.mark.asyncio
async def test_book_level_eval_skips_correct_assertions(eval_service):
    """Book-level eval should skip image_refs_preserved and cross_summary_consistency."""
    mock_response = MagicMock()
    mock_response.content = (
        '{"passed": true, "reasoning": "ok", "likely_cause": null, "suggestion": null}'
    )
    mock_response.model = "test-model"
    mock_response.input_tokens = 10
    mock_response.output_tokens = 5
    mock_response.latency_ms = 100
    eval_service.llm.generate = AsyncMock(return_value=mock_response)

    result = await eval_service.evaluate_summary(
        section_id=0,
        source_text="book content" * 100,
        summary_text="## Key Concepts\n\n**A**: x\n**B**: y\n**C**: z\n" + "summary " * 50,
        eval_scope="book",
        section_count=10,
    )
    assertions = result["assertions"]
    assert assertions["image_refs_preserved"].get("skipped") is True
    assert assertions["cross_summary_consistency"].get("skipped") is True
