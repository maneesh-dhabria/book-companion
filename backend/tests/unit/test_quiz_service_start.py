"""Unit tests for QuizService.start_session (FR-19/20/21/22/23)."""

import pytest

from app.config import Settings
from app.db.models import QuizQuestion
from app.exceptions import QuizBudgetError, QuizValidationError
from app.services.quiz.quiz_service import QuizService
from tests.unit.conftest import FakeLLMProvider


def _valid_question_payload(section_id: int = 1) -> dict:
    return {
        "stem": "What is X?",
        "concept_label": "framing",
        "citation": {
            "section_id": section_id,
            "section_title": "ch",
            "snippet": "framing is...",
        },
        "shape": "open",
        "bloom_level": "apply",
    }


@pytest.mark.asyncio
async def test_start_session_invalid_scope_raises(db_session, book_factory):
    book = await book_factory()
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    with pytest.raises(QuizValidationError):
        await svc.start_session(book_id=book.id, scope={"mode": "bogus"}, theme=None)


@pytest.mark.asyncio
async def test_start_session_specific_chapters_requires_section_ids(db_session, book_factory):
    book = await book_factory()
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    with pytest.raises(QuizValidationError):
        await svc.start_session(
            book_id=book.id,
            scope={"mode": "specific_chapters", "section_ids": []},
            theme=None,
        )


@pytest.mark.asyncio
async def test_start_session_specific_chapters_rejects_alien_section(
    db_session, book_factory, section_factory
):
    book_a = await book_factory()
    book_b = await book_factory()
    foreign_section = await section_factory(book=book_b)
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    with pytest.raises(QuizValidationError):
        await svc.start_session(
            book_id=book_a.id,
            scope={"mode": "specific_chapters", "section_ids": [foreign_section.id]},
            theme=None,
        )


@pytest.mark.asyncio
async def test_start_session_specific_chapters_budget_exceeded(
    db_session, book_factory, section_factory
):
    book = await book_factory()
    huge = "loss aversion " * 30_000  # ~30k * 2 ≈ 60k+ tokens
    section = await section_factory(book=book, content_md=huge)
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    with pytest.raises(QuizBudgetError):
        await svc.start_session(
            book_id=book.id,
            scope={"mode": "specific_chapters", "section_ids": [section.id]},
            theme=None,
        )


@pytest.mark.asyncio
async def test_start_session_cold_start_without_pregen(db_session, book_factory, section_factory):
    book = await book_factory()
    section = await section_factory(book=book)
    provider = FakeLLMProvider([_valid_question_payload(section.id)])
    svc = QuizService(db_session, provider, Settings())
    result = await svc.start_session(
        book_id=book.id,
        scope={"mode": "all_summaries"},
        theme=None,
    )
    assert result["queue_hit"] is False
    assert result["warm_up_count"] == 0
    assert result["session_id"] is not None
    assert result["question_id"] is not None
    qq = await db_session.get(QuizQuestion, result["question_id"])
    assert qq.session_id == result["session_id"]
    assert qq.warm_up is False


@pytest.mark.asyncio
async def test_start_session_consumes_pregen_when_all_conditions_met(db_session, book_factory):
    book = await book_factory()
    pregen = QuizQuestion(
        book_id=book.id,
        session_id=None,
        shape="open",
        bloom_level="apply",
        stem="pregen stem?",
        concept_label="loss aversion",
        citation_json='{"section_id": 1, "section_title": "ch", "snippet": "..."}',
        is_pregen=True,
    )
    db_session.add(pregen)
    await db_session.flush()
    book.pre_drafted_q1_id = pregen.id
    await db_session.flush()

    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    result = await svc.start_session(book_id=book.id, scope={"mode": "all_summaries"}, theme=None)
    assert result["queue_hit"] is True
    assert result["question_id"] == pregen.id
    await db_session.refresh(book)
    assert book.pre_drafted_q1_id is None
    await db_session.refresh(pregen)
    assert pregen.is_pregen is False
    assert pregen.session_id == result["session_id"]


@pytest.mark.asyncio
async def test_start_session_does_not_consume_pregen_when_theme_present(
    db_session, book_factory, section_factory
):
    book = await book_factory()
    section = await section_factory(book=book)
    pregen = QuizQuestion(
        book_id=book.id,
        shape="open",
        bloom_level="apply",
        stem="pregen?",
        concept_label="x",
        citation_json='{"section_id": 1, "section_title": "ch", "snippet": "..."}',
        is_pregen=True,
    )
    db_session.add(pregen)
    await db_session.flush()
    book.pre_drafted_q1_id = pregen.id
    await db_session.flush()

    provider = FakeLLMProvider([_valid_question_payload(section.id)])
    svc = QuizService(db_session, provider, Settings())
    result = await svc.start_session(
        book_id=book.id,
        scope={"mode": "all_summaries"},
        theme="prospect theory",
    )
    assert result["queue_hit"] is False
    await db_session.refresh(book)
    assert book.pre_drafted_q1_id == pregen.id  # NOT consumed (E14/E19)


@pytest.mark.asyncio
async def test_start_session_does_not_consume_pregen_for_specific_chapters(
    db_session, book_factory, section_factory
):
    book = await book_factory()
    section = await section_factory(book=book, content_md="short content")
    pregen = QuizQuestion(
        book_id=book.id,
        shape="open",
        bloom_level="apply",
        stem="pregen?",
        concept_label="x",
        citation_json='{"section_id": 1, "section_title": "ch", "snippet": "..."}',
        is_pregen=True,
    )
    db_session.add(pregen)
    await db_session.flush()
    book.pre_drafted_q1_id = pregen.id
    await db_session.flush()

    provider = FakeLLMProvider([_valid_question_payload(section.id)])
    svc = QuizService(db_session, provider, Settings())
    result = await svc.start_session(
        book_id=book.id,
        scope={"mode": "specific_chapters", "section_ids": [section.id]},
        theme=None,
    )
    assert result["queue_hit"] is False
    await db_session.refresh(book)
    assert book.pre_drafted_q1_id == pregen.id  # E19


@pytest.mark.asyncio
async def test_start_session_warm_up_takes_precedence_over_pregen(
    db_session, book_factory, section_factory
):
    """E14 / FR-22(c): warm-up has ≥1 candidate → pregen slot NOT consumed."""
    from app.db.models import QuizSession

    book = await book_factory()
    section = await section_factory(book=book)
    # Seed a prior completed session that produces a warm-up candidate
    prior = QuizSession(book_id=book.id, scope_mode="all_summaries", status="completed")
    db_session.add(prior)
    await db_session.flush()
    db_session.add(
        QuizQuestion(
            book_id=book.id,
            session_id=prior.id,
            shape="open",
            bloom_level="apply",
            stem="?",
            concept_label="loss aversion",
            citation_json='{"section_id": 1, "section_title": "ch", "snippet": "..."}',
            self_assessment="missed",
        )
    )
    # Stage a pregen slot
    pregen = QuizQuestion(
        book_id=book.id,
        shape="open",
        bloom_level="apply",
        stem="pregen?",
        concept_label="x",
        citation_json='{"section_id": 1, "section_title": "ch", "snippet": "..."}',
        is_pregen=True,
    )
    db_session.add(pregen)
    await db_session.flush()
    book.pre_drafted_q1_id = pregen.id
    await db_session.flush()

    # Warm-up + cold-start Q1 both go through generate_question; script 2 valid
    # responses (1 warm-up + 1 cold-start). Only one warm-up candidate seeded.
    payload = _valid_question_payload(section.id)
    provider = FakeLLMProvider([payload, payload])
    svc = QuizService(db_session, provider, Settings())
    result = await svc.start_session(book_id=book.id, scope={"mode": "all_summaries"}, theme=None)
    assert result["warm_up_count"] == 1
    assert result["queue_hit"] is False  # FR-22(c) — slot NOT consumed
    await db_session.refresh(book)
    assert book.pre_drafted_q1_id == pregen.id  # E14: persists


@pytest.mark.asyncio
async def test_start_session_does_not_consume_stale_pregen(
    db_session, book_factory, section_factory
):
    book = await book_factory()
    section = await section_factory(book=book)
    stale = QuizQuestion(
        book_id=book.id,
        shape="open",
        bloom_level="apply",
        stem="stale pregen?",
        concept_label="x",
        citation_json='{"section_id": 1, "section_title": "ch", "snippet": "..."}',
        is_pregen=True,
        is_stale=True,
    )
    db_session.add(stale)
    await db_session.flush()
    book.pre_drafted_q1_id = stale.id
    await db_session.flush()

    provider = FakeLLMProvider([_valid_question_payload(section.id)])
    svc = QuizService(db_session, provider, Settings())
    result = await svc.start_session(book_id=book.id, scope={"mode": "all_summaries"}, theme=None)
    assert result["queue_hit"] is False
    # Slot itself is left untouched (FR-22 — only consume sets it to NULL)
    await db_session.refresh(book)
    assert book.pre_drafted_q1_id == stale.id
