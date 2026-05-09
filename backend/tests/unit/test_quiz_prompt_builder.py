"""Unit tests for QuizPromptBuilder."""

import pytest

from app.config import Settings
from app.services.quiz.prompt_builder import QuizPromptBuilder
from app.services.quiz.token_counter import count_tokens


@pytest.fixture
def builder() -> QuizPromptBuilder:
    return QuizPromptBuilder(Settings())


def test_build_generation_prompt_includes_scope_content(builder):
    p = builder.build_generation_prompt(
        scope_content="The chapter introduces loss aversion.",
        recent_stems=[],
        themed_summary=None,
        theme=None,
        shape_histogram={"mcq": 0, "open": 0, "spot_error": 0},
        skipped_concepts=[],
    )
    assert "loss aversion" in p
    assert "mcq: 0.4" in p  # target distribution mentioned


def test_build_generation_prompt_includes_recent_stems_block(builder):
    p = builder.build_generation_prompt(
        scope_content="The chapter introduces loss aversion.",
        recent_stems=["What is X?", "Define Y."],
        themed_summary=None,
        theme=None,
        shape_histogram={"mcq": 0, "open": 0, "spot_error": 0},
        skipped_concepts=[],
    )
    assert "What is X?" in p and "Define Y." in p
    assert "Already-Asked Stems" in p


def test_build_generation_prompt_skipped_concepts_augmentation(builder):
    p = builder.build_generation_prompt(
        scope_content="Some content.",
        recent_stems=[],
        themed_summary=None,
        theme=None,
        shape_histogram={"mcq": 0, "open": 0, "spot_error": 0},
        skipped_concepts=["loss aversion", "anchoring"],
    )
    assert "repeatedly skipped" in p
    assert "loss aversion, anchoring" in p


def test_build_generation_prompt_themed_summary_and_theme(builder):
    p = builder.build_generation_prompt(
        scope_content="x",
        recent_stems=[],
        themed_summary="Several questions covered framing effects.",
        theme="risk under uncertainty",
        shape_histogram={"mcq": 1, "open": 2, "spot_error": 0},
        skipped_concepts=[],
    )
    assert "framing effects" in p
    assert "risk under uncertainty" in p
    assert "User-Requested Theme" in p
    assert "Themes Already Covered" in p


def test_build_grading_prompt_appends_fatigue_clause_when_flagged(builder):
    p = builder.build_grading_prompt(
        stem="?",
        citation="...",
        user_answer="...",
        append_fatigue_prompt=True,
    )
    assert "Want to keep going or wrap up here?" in p


def test_build_grading_prompt_omits_fatigue_clause_by_default(builder):
    p = builder.build_grading_prompt(
        stem="?",
        citation="...",
        user_answer="...",
    )
    assert "Want to keep going or wrap up here?" not in p


def test_build_explain_prompt_includes_prior_explains(builder):
    p = builder.build_explain_prompt(
        stem="What is loss aversion?",
        citation="passage",
        prior_explains=["First explanation.", "Second explanation."],
    )
    assert "First explanation." in p
    assert "Second explanation." in p
    assert "different angle" in p


def test_build_rollup_prompt_lists_stems(builder):
    p = builder.build_rollup_prompt(stems=["q1", "q2"], max_chars=200)
    assert "- q1" in p and "- q2" in p
    assert "200" in p


def test_build_generation_prompt_token_budget_enforcement_truncates_scope(builder):
    huge = "word " * 100_000
    p = builder.build_generation_prompt(
        scope_content=huge,
        recent_stems=[],
        themed_summary=None,
        theme=None,
        shape_histogram={"mcq": 0, "open": 0, "spot_error": 0},
        skipped_concepts=[],
        max_prompt_tokens=8_000,
    )
    assert count_tokens(p) <= 8_000
    # And the prompt should still contain the structured-context headers
    assert "Question Shape — Target Distribution" in p
