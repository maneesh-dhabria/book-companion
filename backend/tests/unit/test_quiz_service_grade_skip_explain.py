"""Tests for grade_answer / skip / explain / override / discard (T13)."""

import json

import pytest

from app.config import Settings
from app.db.models import QuizQuestion, QuizSession
from app.exceptions import QuizSoftCapError, QuizValidationError
from app.services.quiz.quiz_service import QuizService
from tests.unit.conftest import FakeLLMProvider


async def _seed_question(
    db_session,
    *,
    book,
    session: QuizSession | None = None,
    stem: str = "What is X?",
    **overrides,
) -> QuizQuestion:
    defaults = dict(
        book_id=book.id,
        session_id=session.id if session else None,
        shape="open",
        bloom_level="apply",
        stem=stem,
        concept_label="x",
        citation_json='{"section_id": 1, "section_title": "ch", "snippet": "important snippet"}',
    )
    defaults.update(overrides)
    q = QuizQuestion(**defaults)
    db_session.add(q)
    await db_session.flush()
    return q


async def _seed_session(db_session, *, book) -> QuizSession:
    qs = QuizSession(book_id=book.id, scope_mode="all_summaries", status="in_progress")
    db_session.add(qs)
    await db_session.flush()
    return qs


# ---- grade_answer -----------------------------------------------------------


@pytest.mark.asyncio
async def test_grade_answer_persists_three_field_feedback_and_hides_verdict(
    db_session, book_factory
):
    book = await book_factory()
    qs = await _seed_session(db_session, book=book)
    q = await _seed_question(db_session, book=book, session=qs)
    provider = FakeLLMProvider(
        [
            {
                "feedback": {
                    "correct": "you nailed the asymmetry",
                    "missing": "didn't mention reference points",
                    "actual": "Per Ch 6, loss aversion …",
                },
                "agent_verdict": "partial",
            }
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    result = await svc.grade_answer(question_id=q.id, user_answer="my answer")
    await db_session.refresh(q)
    assert q.user_answer == "my answer"
    feedback = json.loads(q.feedback_json)
    assert feedback["correct"] == "you nailed the asymmetry"
    assert q.agent_verdict == "partial"
    # S9: agent_verdict NOT exposed in returned UI shape
    assert "agent_verdict" not in result["feedback"]
    assert result["feedback"]["correct"] == "you nailed the asymmetry"


@pytest.mark.asyncio
async def test_grade_answer_appends_fatigue_clause_at_turn_10(db_session, book_factory):
    """FR-55: when answering the 10th non-warm-up turn, append fatigue clause."""
    book = await book_factory()
    qs = await _seed_session(db_session, book=book)
    # Seed 9 prior answered non-warm-up questions
    for i in range(9):
        await _seed_question(
            db_session,
            book=book,
            session=qs,
            stem=f"prior {i}",
            user_answer=f"a{i}",
        )
    q = await _seed_question(db_session, book=book, session=qs, stem="turn 10")
    provider = FakeLLMProvider(
        [
            {
                "feedback": {"correct": "", "missing": "", "actual": "x"},
                "agent_verdict": "correct",
            }
        ]
    )
    svc = QuizService(db_session, provider, Settings())
    await svc.grade_answer(question_id=q.id, user_answer="answer")
    sent_prompt = provider.calls[0]["prompt"]
    assert "Want to keep going or wrap up here?" in sent_prompt


# ---- skip_question ---------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_increments_per_stem_not_per_row(db_session, book_factory):
    """G17: each row with the matching stem → skip_count += 1, others untouched."""
    book = await book_factory()
    qs = await _seed_session(db_session, book=book)
    q1 = await _seed_question(db_session, book=book, session=qs, stem="What is X?")
    q2 = await _seed_question(db_session, book=book, session=qs, stem="What is X?")
    q3 = await _seed_question(db_session, book=book, session=qs, stem="Define Y.")
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    result = await svc.skip_question(question_id=q1.id)
    assert result["rows_affected"] == 2
    await db_session.refresh(q1)
    await db_session.refresh(q2)
    await db_session.refresh(q3)
    assert q1.skip_count == 1
    assert q2.skip_count == 1
    assert q3.skip_count == 0


# ---- explain_question ------------------------------------------------------


@pytest.mark.asyncio
async def test_explain_appends_to_history(db_session, book_factory):
    book = await book_factory()
    q = await _seed_question(db_session, book=book)
    provider = FakeLLMProvider([{"explanation": "It clarifies X."}])
    svc = QuizService(db_session, provider, Settings())
    result = await svc.explain_question(question_id=q.id)
    await db_session.refresh(q)
    history = json.loads(q.explain_history_json)
    assert history == ["It clarifies X."]
    assert result["explanation"] == "It clarifies X."


@pytest.mark.asyncio
async def test_explain_soft_cap_blocks_third_attempt(db_session, book_factory):
    """FR-46: after `explain_soft_cap` (default 2), refuse without LLM call."""
    book = await book_factory()
    q = await _seed_question(
        db_session,
        book=book,
        explain_history_json=json.dumps(["first explain", "second explain"]),
    )
    provider = FakeLLMProvider([])  # no scripted response — must NOT be invoked
    svc = QuizService(db_session, provider, Settings())
    with pytest.raises(QuizSoftCapError):
        await svc.explain_question(question_id=q.id)
    assert provider.calls == []


# ---- override_verdict ------------------------------------------------------


@pytest.mark.asyncio
async def test_override_stores_note_no_tally_change(db_session, book_factory):
    book = await book_factory()
    q = await _seed_question(db_session, book=book, self_assessment="missed")  # tally stays missed
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    await svc.override_verdict(question_id=q.id, note="The book actually says X.")
    await db_session.refresh(q)
    assert q.override_note == "The book actually says X."
    assert q.self_assessment == "missed"  # tally unchanged


@pytest.mark.asyncio
async def test_override_rejects_too_long_note(db_session, book_factory):
    book = await book_factory()
    q = await _seed_question(db_session, book=book)
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    with pytest.raises(QuizValidationError):
        await svc.override_verdict(question_id=q.id, note="x" * 501)


# ---- discard_question ------------------------------------------------------


@pytest.mark.asyncio
async def test_discard_returns_discarded_and_next_question(db_session, book_factory):
    book = await book_factory()
    qs = await _seed_session(db_session, book=book)
    q = await _seed_question(db_session, book=book, session=qs, stem="bad stem")
    next_payload = {
        "stem": "fresh stem",
        "concept_label": "y",
        "citation": {"section_id": 1, "section_title": "ch", "snippet": "..."},
        "shape": "open",
        "bloom_level": "apply",
    }
    provider = FakeLLMProvider([next_payload])
    svc = QuizService(db_session, provider, Settings())
    result = await svc.discard_question(question_id=q.id, scope_content="x")
    assert result["discarded_question"]["id"] == q.id
    assert result["discarded_question"]["discarded"] is True
    assert result["next_question"]["id"] != q.id
    await db_session.refresh(q)
    assert q.discarded is True
    # G4: the prompt sent to the next-question generation includes the
    # discarded stem as a negative-example signal
    assert "bad stem" in provider.calls[0]["prompt"]
