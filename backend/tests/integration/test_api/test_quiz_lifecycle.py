"""T16 — atomic stop_session + resume-banner support (FR-19, FR-24, G10).

Tests:
- list_sessions includes in_progress (frontend's resume-banner data source)
- stop with ≥1 answered question → status='completed' + QUIZ_ROLLUP job enqueued
- stop with zero answered → status='abandoned' + NO rollup job (FR-24)
- re-stop is idempotent: 200 + no double-enqueue
- stop on unknown session → 404
"""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.models import (
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
    QuizQuestion,
    QuizSession,
)


async def _seed_book(app, *, book_id: int = 1) -> None:
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO books (id, title, file_data, file_hash, file_format, "
                "file_size_bytes, status) "
                "VALUES (:id, 'B', x'00', :h, 'epub', 1, 'COMPLETED')"
            ),
            {"id": book_id, "h": f"h{book_id}"},
        )
        await session.commit()


async def _seed_session(app, *, book_id: int = 1, status: str = "in_progress") -> int:
    factory = app.state.session_factory
    async with factory() as session:
        qs = QuizSession(book_id=book_id, scope_mode="all_summaries", status=status)
        session.add(qs)
        await session.flush()
        sid = qs.id
        await session.commit()
    return sid


async def _seed_question(
    app,
    *,
    book_id: int,
    session_id: int,
    user_answer: str | None = None,
    discarded: bool = False,
) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        q = QuizQuestion(
            book_id=book_id,
            session_id=session_id,
            shape="open",
            bloom_level="apply",
            stem="What is X?",
            concept_label="x",
            citation_json=json.dumps({"section_id": 1, "section_title": "Ch", "snippet": "..."}),
            user_answer=user_answer,
            discarded=discarded,
        )
        session.add(q)
        await session.flush()
        qid = q.id
        await session.commit()
    return qid


async def _count_rollup_jobs(app, *, book_id: int) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(ProcessingJob).where(
                        ProcessingJob.book_id == book_id,
                        ProcessingJob.step == ProcessingStep.QUIZ_ROLLUP,
                    )
                )
            )
            .scalars()
            .all()
        )
        return len(list(rows))


# ---- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_includes_in_progress(app, client: AsyncClient):
    """FR-19 — frontend reads `sessions[*].status == 'in_progress'` from the
    list endpoint to render the resume banner. No new endpoint needed."""
    await _seed_book(app, book_id=1)
    await _seed_session(app, book_id=1, status="in_progress")
    r = await client.get("/api/v1/books/1/quiz-sessions")
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert any(s["status"] == "in_progress" for s in sessions)


@pytest.mark.asyncio
async def test_stop_session_completed_when_answered_enqueues_rollup(app, client: AsyncClient):
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    await _seed_question(app, book_id=1, session_id=sid, user_answer="answered")
    r = await client.post(f"/api/v1/quiz-sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert await _count_rollup_jobs(app, book_id=1) == 1


@pytest.mark.asyncio
async def test_stop_session_abandoned_when_no_answers_no_rollup(app, client: AsyncClient):
    """FR-24: zero answered → abandoned + NO rollup job."""
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    # No questions seeded.
    r = await client.post(f"/api/v1/quiz-sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "abandoned"
    assert await _count_rollup_jobs(app, book_id=1) == 0


@pytest.mark.asyncio
async def test_stop_session_discarded_does_not_count_as_answered(app, client: AsyncClient):
    """A discarded question with user_answer set should NOT trip the
    'completed' branch. FR-24 says "≥1 answered, non-discarded" turn."""
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    await _seed_question(
        app,
        book_id=1,
        session_id=sid,
        user_answer="answered",
        discarded=True,
    )
    r = await client.post(f"/api/v1/quiz-sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "abandoned"
    assert await _count_rollup_jobs(app, book_id=1) == 0


@pytest.mark.asyncio
async def test_stop_session_idempotent(app, client: AsyncClient):
    """G10: re-stop returns 200 with current state; no duplicate rollup."""
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    await _seed_question(app, book_id=1, session_id=sid, user_answer="x")
    r1 = await client.post(f"/api/v1/quiz-sessions/{sid}/stop")
    r2 = await client.post(f"/api/v1/quiz-sessions/{sid}/stop")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["status"] == "completed"
    assert r2.json()["status"] == "completed"
    assert await _count_rollup_jobs(app, book_id=1) == 1


@pytest.mark.asyncio
async def test_stop_session_404_unknown(app, client: AsyncClient):
    r = await client.post("/api/v1/quiz-sessions/9999/stop")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_stop_session_does_not_double_enqueue_when_rollup_pending(app, client: AsyncClient):
    """If a previous PENDING/RUNNING rollup exists, the partial UNIQUE INDEX
    rejects the new INSERT. The service must swallow the IntegrityError and
    still mark the session as completed."""
    await _seed_book(app, book_id=1)
    sid = await _seed_session(app, book_id=1)
    await _seed_question(app, book_id=1, session_id=sid, user_answer="x")
    # Seed an existing PENDING rollup.
    factory = app.state.session_factory
    async with factory() as session:
        session.add(
            ProcessingJob(
                book_id=1,
                step=ProcessingStep.QUIZ_ROLLUP,
                status=ProcessingJobStatus.PENDING,
            )
        )
        await session.commit()
    r = await client.post(f"/api/v1/quiz-sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert await _count_rollup_jobs(app, book_id=1) == 1  # not duplicated
