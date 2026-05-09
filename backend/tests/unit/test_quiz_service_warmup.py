"""Unit tests for QuizService.compute_warm_up_candidates (FR-70 a-d)."""

from datetime import datetime, timedelta

import pytest

from app.config import Settings
from app.db.models import QuizQuestion, QuizSession
from app.services.quiz.quiz_service import QuizService
from tests.unit.conftest import FakeLLMProvider


async def _seed_session(
    db_session,
    *,
    book_id: int,
    questions: list[dict],
    status: str = "completed",
    created_at: datetime | None = None,
):
    """Helper: create a QuizSession + questions with the given fields."""
    qs = QuizSession(
        book_id=book_id,
        scope_mode="all_summaries",
        status=status,
    )
    if created_at is not None:
        qs.created_at = created_at
    db_session.add(qs)
    await db_session.flush()
    for q in questions:
        db_session.add(
            QuizQuestion(
                book_id=book_id,
                session_id=qs.id,
                shape="open",
                bloom_level="apply",
                stem=q.get("stem", "?"),
                concept_label=q["concept_label"],
                citation_json=q.get(
                    "citation_json",
                    '{"section_id": 1, "section_title": "ch", "snippet": "..."}',
                ),
                self_assessment=q.get("self_assessment"),
                agent_verdict=q.get("agent_verdict"),
            )
        )
    await db_session.flush()
    return qs


@pytest.mark.asyncio
async def test_warm_up_no_prior_sessions_returns_empty(db_session, book_factory):
    book = await book_factory()
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    out = await svc.compute_warm_up_candidates(book_id=book.id, scope={"mode": "all_summaries"})
    assert out == []


@pytest.mark.asyncio
async def test_warm_up_user_missed_qualifies(db_session, book_factory):
    book = await book_factory()
    await _seed_session(
        db_session,
        book_id=book.id,
        questions=[{"concept_label": "loss aversion", "self_assessment": "missed"}],
    )
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    out = await svc.compute_warm_up_candidates(book_id=book.id, scope={"mode": "all_summaries"})
    assert [c["concept_label"] for c in out] == ["loss aversion"]


@pytest.mark.asyncio
async def test_warm_up_agent_incorrect_qualifies(db_session, book_factory):
    """FR-70(b): agent_verdict='incorrect' alone qualifies the concept."""
    book = await book_factory()
    await _seed_session(
        db_session,
        book_id=book.id,
        questions=[
            {
                "concept_label": "anchoring",
                "self_assessment": "partial",  # user-side also qualifies
                "agent_verdict": "incorrect",  # belt-and-suspenders for FR-70(b)
            },
        ],
    )
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    out = await svc.compute_warm_up_candidates(book_id=book.id, scope={"mode": "all_summaries"})
    assert "anchoring" in [c["concept_label"] for c in out]


@pytest.mark.asyncio
async def test_warm_up_excluded_when_later_session_marks_got_it(db_session, book_factory):
    book = await book_factory()
    t0 = datetime(2026, 5, 1, 10, 0, 0)
    t1 = datetime(2026, 5, 2, 10, 0, 0)
    await _seed_session(
        db_session,
        book_id=book.id,
        questions=[{"concept_label": "loss aversion", "self_assessment": "missed"}],
        created_at=t0,
    )
    await _seed_session(
        db_session,
        book_id=book.id,
        questions=[{"concept_label": "loss aversion", "self_assessment": "got_it"}],
        created_at=t1,
    )
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    out = await svc.compute_warm_up_candidates(book_id=book.id, scope={"mode": "all_summaries"})
    assert "loss aversion" not in [c["concept_label"] for c in out]


@pytest.mark.asyncio
async def test_warm_up_specific_chapters_filters_by_section_id(db_session, book_factory):
    book = await book_factory()
    await _seed_session(
        db_session,
        book_id=book.id,
        questions=[
            {
                "concept_label": "framing",
                "self_assessment": "missed",
                "citation_json": '{"section_id": 1, "section_title": "ch1", "snippet": "..."}',
            },
            {
                "concept_label": "loss aversion",
                "self_assessment": "missed",
                "citation_json": '{"section_id": 2, "section_title": "ch2", "snippet": "..."}',
            },
        ],
    )
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    out = await svc.compute_warm_up_candidates(
        book_id=book.id,
        scope={"mode": "specific_chapters", "section_ids": [1]},
    )
    labels = [c["concept_label"] for c in out]
    assert labels == ["framing"]


@pytest.mark.asyncio
async def test_warm_up_takes_at_most_max_questions(db_session, book_factory):
    book = await book_factory()
    await _seed_session(
        db_session,
        book_id=book.id,
        questions=[
            {"concept_label": f"concept-{i}", "self_assessment": "missed"} for i in range(5)
        ],
    )
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    settings = Settings()
    out = await svc.compute_warm_up_candidates(book_id=book.id, scope={"mode": "all_summaries"})
    assert len(out) <= settings.quiz.warm_up_max_questions


@pytest.mark.asyncio
async def test_warm_up_lookback_only_last_3_sessions(db_session, book_factory):
    book = await book_factory()
    # 5 prior completed sessions; older ones use older timestamps. The 2
    # oldest must be excluded by FR-70(a).
    base = datetime(2026, 4, 1, 10, 0, 0)
    for i in range(5):
        await _seed_session(
            db_session,
            book_id=book.id,
            questions=[{"concept_label": f"old-{i}", "self_assessment": "missed"}],
            created_at=base + timedelta(days=i),
        )
    svc = QuizService(db_session, FakeLLMProvider([]), Settings())
    out = await svc.compute_warm_up_candidates(book_id=book.id, scope={"mode": "all_summaries"})
    labels = {c["concept_label"] for c in out}
    # Most recent 3 sessions seeded concepts old-2, old-3, old-4 — only those
    # are eligible. (warm_up_max_questions caps to 2 but the *eligible* pool
    # excludes old-0 / old-1.)
    assert "old-0" not in labels
    assert "old-1" not in labels
