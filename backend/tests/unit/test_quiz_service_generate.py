"""Unit tests for QuizService.generate_question (FR-30/32/33/34/35)."""

import json

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.models import QuizQuestion
from app.exceptions import QuizGenerationError
from app.services.quiz.quiz_service import QuizService


@pytest.mark.asyncio
async def test_generate_question_open_persists_with_normalized_label(
    db_session, book_factory, section_factory, fake_llm_factory
):
    book = await book_factory()
    section = await section_factory(book=book, title="Ch 6")
    provider = fake_llm_factory(
        [
            {
                "stem": "Why does the author argue for X?",
                "concept_label": "Loss-Aversion (Kahneman)",
                "citation": {
                    "section_id": section.id,
                    "section_title": "Ch 6",
                    "snippet": "loss aversion is asymmetric",
                },
                "shape": "open",
                "bloom_level": "analyze",
            }
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    q = await svc.generate_question(
        book_id=book.id,
        session_id=None,
        scope_content="Ch 6 introduces loss aversion.",
        theme=None,
        warm_up=False,
    )
    assert q.id is not None
    assert q.concept_label == "loss aversion"  # FR-34 normalization
    assert q.shape == "open"
    assert q.bloom_level == "analyze"
    assert q.warm_up is False
    assert q.is_stale is False
    assert q.skip_count == 0
    citation = json.loads(q.citation_json)
    assert citation["section_id"] == section.id
    assert q.mcq_options_json is None
    assert q.intended_error is None


@pytest.mark.asyncio
async def test_generate_question_mcq_persists_options(db_session, book_factory, fake_llm_factory):
    book = await book_factory()
    provider = fake_llm_factory(
        [
            {
                "stem": "Which option best describes X?",
                "concept_label": "framing",
                "citation": {
                    "section_id": 1,
                    "section_title": "ch1",
                    "snippet": "framing matters",
                },
                "shape": "mcq",
                "bloom_level": "understand",
                "mcq_options": ["a", "b", "c", "d"],
                "mcq_correct_index": 2,
            }
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    q = await svc.generate_question(
        book_id=book.id,
        session_id=None,
        scope_content="x",
        theme=None,
        warm_up=False,
    )
    assert q.shape == "mcq"
    payload = json.loads(q.mcq_options_json)
    assert payload["options"] == ["a", "b", "c", "d"]
    assert payload["correct_index"] == 2


@pytest.mark.asyncio
async def test_generate_question_retries_once_on_schema_failure(
    db_session, book_factory, fake_llm_factory
):
    book = await book_factory()
    provider = fake_llm_factory(
        [
            # first response missing required fields
            {"stem": "?", "shape": "open", "bloom_level": "remember"},
            # second response valid
            {
                "stem": "What is anchoring?",
                "concept_label": "anchoring",
                "citation": {
                    "section_id": 1,
                    "section_title": "ch",
                    "snippet": "anchoring describes...",
                },
                "shape": "open",
                "bloom_level": "remember",
            },
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    q = await svc.generate_question(
        book_id=book.id, session_id=None, scope_content="x", theme=None, warm_up=False
    )
    assert q.concept_label == "anchoring"
    assert len(provider.calls) == 2
    # Retry prompt MUST contain the validator-error block
    retry_prompt = provider.calls[1]["prompt"]
    assert "Prior Attempt Failed Validation" in retry_prompt
    assert "validation" in retry_prompt.lower() or "required" in retry_prompt.lower()


@pytest.mark.asyncio
async def test_generate_question_raises_after_two_failures_and_persists_nothing(
    db_session, book_factory, fake_llm_factory
):
    book = await book_factory()
    provider = fake_llm_factory(
        [
            {"stem": "?", "shape": "open"},  # missing required fields
            {"stem": "?", "shape": "open"},  # still invalid
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    with pytest.raises(QuizGenerationError):
        await svc.generate_question(
            book_id=book.id,
            session_id=None,
            scope_content="x",
            theme=None,
            warm_up=False,
        )
    rows = (await db_session.execute(select(QuizQuestion))).scalars().all()
    assert rows == []  # FR-32: failed attempts NOT persisted


@pytest.mark.asyncio
async def test_spot_error_validator_rejects_correct_restatement(
    db_session, book_factory, fake_llm_factory
):
    """FR-33: stem identical to citation snippet → no deliberate flip → fail."""
    book = await book_factory()
    snippet = "Loss aversion makes losses feel twice as painful as gains."
    provider = fake_llm_factory(
        [
            # first attempt — same lexicon as snippet, no negation/flip
            {
                "stem": "Loss aversion makes losses feel twice as painful as gains.",
                "concept_label": "loss aversion",
                "citation": {"section_id": 1, "section_title": "ch", "snippet": snippet},
                "shape": "spot_error",
                "bloom_level": "analyze",
                "intended_error": "claims losses feel as painful as gains",
                "error_explanation": "the original says twice as painful",
            },
            # retry — adds a deliberate negation ("not")
            {
                "stem": "Loss aversion does NOT make losses feel any worse than gains.",
                "concept_label": "loss aversion",
                "citation": {"section_id": 1, "section_title": "ch", "snippet": snippet},
                "shape": "spot_error",
                "bloom_level": "analyze",
                "intended_error": "claims no asymmetry",
                "error_explanation": "the original says twice as painful",
            },
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    q = await svc.generate_question(
        book_id=book.id,
        session_id=None,
        scope_content="x",
        theme=None,
        warm_up=False,
    )
    assert q.shape == "spot_error"
    assert q.intended_error == "claims no asymmetry"
    assert len(provider.calls) == 2  # one retry consumed


@pytest.mark.asyncio
async def test_spot_error_missing_intended_error_triggers_retry(
    db_session, book_factory, fake_llm_factory
):
    """If intended_error empty/null after schema validate, FR-32 retry kicks in."""
    book = await book_factory()
    # Note: schema requires intended_error & error_explanation, so the schema
    # validator catches the missing-field case. The validator catches the
    # *empty-string* case via _validate_spot_error.
    snippet = "Anchoring biases numerical estimates toward an irrelevant prior."
    provider = fake_llm_factory(
        [
            {
                "stem": "Anchoring biases numerical estimates toward an irrelevant prior.",
                "concept_label": "anchoring",
                "citation": {"section_id": 1, "section_title": "ch", "snippet": snippet},
                "shape": "spot_error",
                "bloom_level": "analyze",
                "intended_error": "",  # empty — _validate_spot_error rejects
                "error_explanation": "irrelevant",
            },
            {
                "stem": "Anchoring NEVER biases numerical estimates.",
                "concept_label": "anchoring",
                "citation": {"section_id": 1, "section_title": "ch", "snippet": snippet},
                "shape": "spot_error",
                "bloom_level": "analyze",
                "intended_error": "claims no anchoring effect",
                "error_explanation": "the source asserts it does",
            },
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    q = await svc.generate_question(
        book_id=book.id, session_id=None, scope_content="x", theme=None, warm_up=False
    )
    assert q.intended_error == "claims no anchoring effect"


@pytest.fixture
def fake_llm_factory():
    from tests.unit.conftest import FakeLLMProvider

    return lambda responses: FakeLLMProvider(responses)
