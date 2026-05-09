"""Strict JSON-schema invariants for quiz LLM round-trips."""

from app.services.quiz.schemas import (
    FEEDBACK_SCHEMA,
    QUESTION_SCHEMA,
    ROLLUP_SCHEMA,
)


def test_question_schema_strict():
    assert QUESTION_SCHEMA["additionalProperties"] is False
    required = set(QUESTION_SCHEMA["required"])
    assert {"stem", "concept_label", "citation", "shape", "bloom_level"}.issubset(required)
    assert QUESTION_SCHEMA["properties"]["shape"]["enum"] == ["mcq", "open", "spot_error"]
    # G21: 'create' Bloom level supported for open-ended
    assert "create" in QUESTION_SCHEMA["properties"]["bloom_level"]["enum"]


def test_question_schema_shape_conditional_required():
    branches = QUESTION_SCHEMA["allOf"]
    mcq_branch = next(b for b in branches if b["if"]["properties"]["shape"]["const"] == "mcq")
    assert "mcq_options" in mcq_branch["then"]["required"]
    spot_branch = next(
        b for b in branches if b["if"]["properties"]["shape"]["const"] == "spot_error"
    )
    assert {"intended_error", "error_explanation"}.issubset(set(spot_branch["then"]["required"]))


def test_feedback_schema_strict():
    assert FEEDBACK_SCHEMA["additionalProperties"] is False
    required = set(FEEDBACK_SCHEMA["required"])
    assert {"feedback", "agent_verdict"}.issubset(required)
    assert FEEDBACK_SCHEMA["properties"]["agent_verdict"]["enum"] == [
        "correct",
        "partial",
        "incorrect",
    ]


def test_rollup_schema_strict():
    assert ROLLUP_SCHEMA["additionalProperties"] is False
    assert ROLLUP_SCHEMA["required"] == ["themes_summary"]
