"""Quiz API endpoints (T15) — wires QuizService onto HTTP per spec §9.

Exception → status mapping:
- QuizValidationError    → 400
- QuizBudgetError        → 422
- QuizNotFoundError      → 404
- QuizSoftCapError       → 409
- QuizGenerationError    → 502
- SubprocessTimeoutError → 504
- SubprocessNotFoundError→ 503
- service is None        → 503 (settings.quiz.enabled=False or no LLM provider)
"""

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_quiz_service
from app.api.schemas import (
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizCitation,
    QuizDiscardResponse,
    QuizExplainResponse,
    QuizLifetimeTally,
    QuizNextQuestionResponse,
    QuizOverrideRequest,
    QuizQuestionResponse,
    QuizScope,
    QuizSelfAssessmentRequest,
    QuizSessionDetailResponse,
    QuizSessionListItem,
    QuizSessionListResponse,
    QuizSessionTally,
    QuizStartRequest,
    QuizStartResponse,
)
from app.db.models import Book, QuizDedupState, QuizQuestion, QuizSession
from app.exceptions import (
    QuizBudgetError,
    QuizGenerationError,
    QuizNotFoundError,
    QuizSoftCapError,
    QuizValidationError,
    SubprocessNotFoundError,
    SubprocessTimeoutError,
)
from app.services.quiz.quiz_service import QuizService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["quiz"])


# ---- helpers ----------------------------------------------------------------


def _classify_outcome(exc: BaseException | None) -> str:
    """NFR-10a outcome taxonomy: success | schema_failed | timeout | llm_unavailable."""
    if exc is None:
        return "success"
    if isinstance(exc, SubprocessTimeoutError):
        return "timeout"
    if isinstance(exc, SubprocessNotFoundError):
        return "llm_unavailable"
    if isinstance(exc, QuizGenerationError):
        return "schema_failed"
    return "error"


def _log_outcome(step: str, *, outcome: str, **kwargs) -> None:
    """Emit `quiz.<step>.outcome` per NFR-10a."""
    logger.info(f"quiz.{step}.outcome", outcome=outcome, **kwargs)


def _require_service(svc: QuizService | None) -> QuizService:
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider detected — install Claude Code or Codex CLI.",
        )
    return svc


def _serialize_question(q: QuizQuestion, *, queue_hit: bool = False) -> QuizQuestionResponse:
    """Build the wire shape from a QuizQuestion ORM row.

    `agent_verdict` is intentionally NOT included (S9: backend-only).
    """
    citation_data = json.loads(q.citation_json or "{}")
    citation = QuizCitation(
        section_id=citation_data.get("section_id"),
        section_title=citation_data.get("section_title"),
        snippet=citation_data.get("snippet"),
    )

    mcq_options: list[str] | None = None
    if q.mcq_options_json:
        mcq_payload = json.loads(q.mcq_options_json)
        mcq_options = mcq_payload.get("options") if isinstance(mcq_payload, dict) else mcq_payload

    feedback: dict[str, Any] | None = None
    if q.feedback_json:
        feedback = json.loads(q.feedback_json)

    return QuizQuestionResponse(
        id=q.id,
        session_id=q.session_id,
        book_id=q.book_id,
        shape=q.shape,
        bloom_level=q.bloom_level,
        stem=q.stem,
        concept_label=q.concept_label,
        citation=citation,
        mcq_options=mcq_options,
        intended_error=q.intended_error,
        error_explanation=q.error_explanation,
        user_answer=q.user_answer,
        feedback=feedback,
        self_assessment=q.self_assessment,
        override_note=q.override_note,
        explain_history=json.loads(q.explain_history_json or "[]"),
        skip_count=q.skip_count,
        discarded=q.discarded,
        warm_up=q.warm_up,
        queue_hit=queue_hit,
        is_pregen=q.is_pregen,
        is_stale=q.is_stale,
        created_at=q.created_at,
        answered_at=q.answered_at,
    )


def _compute_session_tally(questions: list[QuizQuestion]) -> tuple[QuizSessionTally, int]:
    """Tally counts + question_count (excludes stale / pregen-not-yet-served)."""
    tally = QuizSessionTally()
    count = 0
    for q in questions:
        if q.is_stale:
            continue
        count += 1
        if q.discarded:
            tally.discarded += 1
            continue
        if q.skip_count > 0 and q.user_answer is None and q.self_assessment is None:
            tally.skipped += 1
            continue
        if q.self_assessment == "got_it":
            tally.got_it += 1
        elif q.self_assessment == "partial":
            tally.partial += 1
        elif q.self_assessment == "missed":
            tally.missed += 1
    return tally, count


def _serialize_session_list_item(qs: QuizSession) -> QuizSessionListItem:
    tally, count = _compute_session_tally(list(qs.questions or []))
    is_warm = bool(qs.questions) and all(q.warm_up for q in qs.questions if not q.is_stale)
    return QuizSessionListItem(
        id=qs.id,
        book_id=qs.book_id,
        scope=QuizScope(mode=qs.scope_mode, section_ids=qs.scope_section_ids),
        theme=qs.theme,
        status=qs.status,
        created_at=qs.created_at,
        ended_at=qs.ended_at,
        question_count=count,
        tally=tally,
        is_warm_up_session=is_warm,
    )


async def _book_or_404(db: AsyncSession, book_id: int) -> None:
    exists = await db.scalar(select(Book.id).where(Book.id == book_id))
    if exists is None:
        raise HTTPException(status_code=404, detail="Book not found")


async def _session_or_404(db: AsyncSession, session_id: int) -> QuizSession:
    qs = await db.scalar(select(QuizSession).where(QuizSession.id == session_id))
    if qs is None:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    return qs


async def _question_or_404(db: AsyncSession, question_id: int) -> QuizQuestion:
    qq = await db.scalar(select(QuizQuestion).where(QuizQuestion.id == question_id))
    if qq is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return qq


async def _compute_lifetime_tally(db: AsyncSession, book_id: int) -> QuizLifetimeTally:
    sessions = list(
        (await db.execute(select(QuizSession).where(QuizSession.book_id == book_id)))
        .scalars()
        .all()
    )
    questions = list(
        (
            await db.execute(
                select(QuizQuestion).where(
                    QuizQuestion.book_id == book_id,
                    QuizQuestion.is_stale.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    tally = QuizLifetimeTally(session_count=len(sessions))
    for q in questions:
        if q.discarded or q.is_pregen or q.session_id is None:
            continue
        tally.total_questions += 1
        if q.self_assessment == "got_it":
            tally.got_it += 1
        elif q.self_assessment == "partial":
            tally.partial += 1
        elif q.self_assessment == "missed":
            tally.missed += 1
    dedup = await db.scalar(select(QuizDedupState).where(QuizDedupState.book_id == book_id))
    if dedup is not None:
        tally.themes_summary = dedup.themes_summary
    return tally


# ---- routes -----------------------------------------------------------------


@router.get(
    "/api/v1/books/{book_id}/quiz-sessions",
    response_model=QuizSessionListResponse,
)
async def list_sessions(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    await _book_or_404(db, book_id)
    from sqlalchemy.orm import selectinload

    rows = list(
        (
            await db.execute(
                select(QuizSession)
                .where(QuizSession.book_id == book_id)
                .options(selectinload(QuizSession.questions))
                .order_by(QuizSession.created_at.desc(), QuizSession.id.desc())
            )
        )
        .scalars()
        .all()
    )
    items = [_serialize_session_list_item(qs) for qs in rows]
    lifetime = await _compute_lifetime_tally(db, book_id)
    return QuizSessionListResponse(sessions=items, lifetime_tally=lifetime)


@router.post(
    "/api/v1/books/{book_id}/quiz-sessions",
    response_model=QuizStartResponse,
    status_code=201,
)
async def start_session(
    book_id: int,
    body: QuizStartRequest,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    await _book_or_404(db, book_id)
    quiz = _require_service(svc)
    scope_dict = body.scope.model_dump(exclude_none=True)
    try:
        result = await quiz.start_session(book_id=book_id, scope=scope_dict, theme=body.theme)
    except QuizValidationError as e:
        _log_outcome("start_session", outcome="error", book_id=book_id)
        raise HTTPException(400, detail=str(e)) from e
    except QuizBudgetError as e:
        _log_outcome("start_session", outcome="error", book_id=book_id)
        raise HTTPException(422, detail=str(e)) from e
    except SubprocessNotFoundError as e:
        _log_outcome("start_session", outcome="llm_unavailable", book_id=book_id)
        raise HTTPException(503, detail=str(e)) from e
    except SubprocessTimeoutError as e:
        _log_outcome("start_session", outcome="timeout", book_id=book_id)
        raise HTTPException(504, detail=str(e)) from e
    except QuizGenerationError as e:
        _log_outcome("start_session", outcome="schema_failed", book_id=book_id)
        raise HTTPException(502, detail=str(e)) from e
    await db.commit()
    _log_outcome("start_session", outcome="success", book_id=book_id)

    # Re-fetch with relationships eagerly loaded so the response serializer
    # has access to questions and tally inputs.
    from sqlalchemy.orm import selectinload

    qs = await db.scalar(
        select(QuizSession)
        .where(QuizSession.id == result["session_id"])
        .options(selectinload(QuizSession.questions))
    )
    qq = await db.scalar(select(QuizQuestion).where(QuizQuestion.id == result["question_id"]))
    return QuizStartResponse(
        session=_serialize_session_list_item(qs),
        first_question=_serialize_question(qq, queue_hit=result["queue_hit"]),
        warm_up_count=result["warm_up_count"],
    )


@router.get(
    "/api/v1/books/{book_id}/quiz-sessions/lifetime-tally",
    response_model=QuizLifetimeTally,
)
async def lifetime_tally(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    await _book_or_404(db, book_id)
    return await _compute_lifetime_tally(db, book_id)


@router.get(
    "/api/v1/quiz-sessions/{session_id}",
    response_model=QuizSessionDetailResponse,
)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload

    qs = await db.scalar(
        select(QuizSession)
        .where(QuizSession.id == session_id)
        .options(selectinload(QuizSession.questions))
    )
    if qs is None:
        raise HTTPException(404, detail="Quiz session not found")
    questions = [_serialize_question(q) for q in qs.questions if not q.is_stale]
    tally, _ = _compute_session_tally(list(qs.questions or []))
    return QuizSessionDetailResponse(
        id=qs.id,
        book_id=qs.book_id,
        scope=QuizScope(mode=qs.scope_mode, section_ids=qs.scope_section_ids),
        theme=qs.theme,
        status=qs.status,
        created_at=qs.created_at,
        ended_at=qs.ended_at,
        questions=questions,
        tally=tally,
    )


@router.post(
    "/api/v1/quiz-sessions/{session_id}/next-question",
    response_model=QuizNextQuestionResponse,
)
async def next_question(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    quiz = _require_service(svc)
    qs = await _session_or_404(db, session_id)
    scope_dict = {"mode": qs.scope_mode, "section_ids": qs.scope_section_ids}
    try:
        qq = await quiz.generate_question(
            book_id=qs.book_id,
            session_id=session_id,
            scope=scope_dict,
            theme=qs.theme,
            warm_up=False,
        )
    except SubprocessNotFoundError as e:
        _log_outcome("next_question", outcome="llm_unavailable", session_id=session_id)
        raise HTTPException(503, detail=str(e)) from e
    except SubprocessTimeoutError as e:
        _log_outcome("next_question", outcome="timeout", session_id=session_id)
        raise HTTPException(504, detail=str(e)) from e
    except QuizGenerationError as e:
        _log_outcome("next_question", outcome="schema_failed", session_id=session_id)
        raise HTTPException(502, detail=str(e)) from e
    await db.commit()
    _log_outcome("next_question", outcome="success", session_id=session_id)
    return QuizNextQuestionResponse(question=_serialize_question(qq))


@router.post(
    "/api/v1/quiz-sessions/{session_id}/questions/{question_id}/answer",
    response_model=QuizAnswerResponse,
)
async def submit_answer(
    session_id: int,
    question_id: int,
    body: QuizAnswerRequest,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    quiz = _require_service(svc)
    await _question_or_404(db, question_id)
    try:
        await quiz.grade_answer(question_id=question_id, user_answer=body.answer)
    except QuizNotFoundError as e:
        raise HTTPException(404, detail=str(e)) from e
    except SubprocessNotFoundError as e:
        _log_outcome("answer", outcome="llm_unavailable", question_id=question_id)
        raise HTTPException(503, detail=str(e)) from e
    except SubprocessTimeoutError as e:
        _log_outcome("answer", outcome="timeout", question_id=question_id)
        raise HTTPException(504, detail=str(e)) from e
    except QuizGenerationError as e:
        _log_outcome("answer", outcome="schema_failed", question_id=question_id)
        raise HTTPException(502, detail=str(e)) from e
    await db.commit()
    qq = await _question_or_404(db, question_id)
    qq.answered_at = datetime.now(UTC)
    await db.commit()
    _log_outcome("answer", outcome="success", question_id=question_id)
    return QuizAnswerResponse(question=_serialize_question(qq))


@router.patch(
    "/api/v1/quiz-sessions/{session_id}/questions/{question_id}",
    response_model=QuizQuestionResponse,
)
async def record_self_assessment(
    session_id: int,
    question_id: int,
    body: QuizSelfAssessmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """FR-53/G9: race-safe conditional UPDATE — 409 when already assessed."""
    result = await db.execute(
        update(QuizQuestion)
        .where(
            QuizQuestion.id == question_id,
            QuizQuestion.self_assessment.is_(None),
        )
        .values(self_assessment=body.self_assessment)
    )
    if result.rowcount == 0:
        # Distinguish 404 from 409.
        exists = await db.scalar(select(QuizQuestion.id).where(QuizQuestion.id == question_id))
        if exists is None:
            raise HTTPException(404, detail="Question not found")
        raise HTTPException(409, detail="self_assessment already recorded")
    await db.commit()
    qq = await _question_or_404(db, question_id)
    return _serialize_question(qq)


@router.post(
    "/api/v1/quiz-sessions/{session_id}/questions/{question_id}/skip",
    response_model=QuizQuestionResponse,
)
async def skip_question(
    session_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    quiz = _require_service(svc)
    await _question_or_404(db, question_id)
    try:
        await quiz.skip_question(question_id=question_id)
    except QuizNotFoundError as e:
        raise HTTPException(404, detail=str(e)) from e
    await db.commit()
    qq = await _question_or_404(db, question_id)
    return _serialize_question(qq)


@router.post(
    "/api/v1/quiz-sessions/{session_id}/questions/{question_id}/explain",
    response_model=QuizExplainResponse,
)
async def explain_question(
    session_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    quiz = _require_service(svc)
    await _question_or_404(db, question_id)
    try:
        result = await quiz.explain_question(question_id=question_id)
    except QuizSoftCapError as e:
        _log_outcome("explain", outcome="error", question_id=question_id)
        raise HTTPException(409, detail=str(e)) from e
    except QuizNotFoundError as e:
        raise HTTPException(404, detail=str(e)) from e
    except SubprocessNotFoundError as e:
        _log_outcome("explain", outcome="llm_unavailable", question_id=question_id)
        raise HTTPException(503, detail=str(e)) from e
    except SubprocessTimeoutError as e:
        _log_outcome("explain", outcome="timeout", question_id=question_id)
        raise HTTPException(504, detail=str(e)) from e
    except QuizGenerationError as e:
        _log_outcome("explain", outcome="schema_failed", question_id=question_id)
        raise HTTPException(502, detail=str(e)) from e
    await db.commit()
    _log_outcome("explain", outcome="success", question_id=question_id)
    qq = await _question_or_404(db, question_id)
    return QuizExplainResponse(
        question=_serialize_question(qq),
        explanation=result["explanation"],
    )


@router.post(
    "/api/v1/quiz-sessions/{session_id}/questions/{question_id}/override",
    response_model=QuizQuestionResponse,
)
async def override_question(
    session_id: int,
    question_id: int,
    body: QuizOverrideRequest,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    quiz = _require_service(svc)
    await _question_or_404(db, question_id)
    try:
        await quiz.override_verdict(question_id=question_id, note=body.note)
    except QuizValidationError as e:
        raise HTTPException(400, detail=str(e)) from e
    except QuizNotFoundError as e:
        raise HTTPException(404, detail=str(e)) from e
    await db.commit()
    qq = await _question_or_404(db, question_id)
    return _serialize_question(qq)


@router.post(
    "/api/v1/quiz-sessions/{session_id}/questions/{question_id}/discard",
    response_model=QuizDiscardResponse,
)
async def discard_question(
    session_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    quiz = _require_service(svc)
    qs = await _session_or_404(db, session_id)
    await _question_or_404(db, question_id)
    # Build scope_content for the replacement question.
    scope_dict = {"mode": qs.scope_mode, "section_ids": qs.scope_section_ids}
    scope_content = await quiz._fetch_scope_content(qs.book_id, scope_dict)
    try:
        await quiz.discard_question(question_id=question_id, scope_content=scope_content)
    except QuizValidationError as e:
        _log_outcome("discard", outcome="error", question_id=question_id)
        raise HTTPException(400, detail=str(e)) from e
    except QuizNotFoundError as e:
        raise HTTPException(404, detail=str(e)) from e
    except SubprocessNotFoundError as e:
        _log_outcome("discard", outcome="llm_unavailable", question_id=question_id)
        raise HTTPException(503, detail=str(e)) from e
    except SubprocessTimeoutError as e:
        _log_outcome("discard", outcome="timeout", question_id=question_id)
        raise HTTPException(504, detail=str(e)) from e
    except QuizGenerationError as e:
        _log_outcome("discard", outcome="schema_failed", question_id=question_id)
        raise HTTPException(502, detail=str(e)) from e
    await db.commit()
    _log_outcome("discard", outcome="success", question_id=question_id)
    discarded = await _question_or_404(db, question_id)
    # Find the just-created next question (newest non-discarded for this session).
    next_q = (
        await db.execute(
            select(QuizQuestion)
            .where(
                QuizQuestion.session_id == session_id,
                QuizQuestion.discarded.is_(False),
            )
            .order_by(QuizQuestion.created_at.desc(), QuizQuestion.id.desc())
            .limit(1)
        )
    ).scalar_one()
    return QuizDiscardResponse(
        discarded_question=_serialize_question(discarded),
        next_question=_serialize_question(next_q),
    )


@router.post(
    "/api/v1/quiz-sessions/{session_id}/stop",
    response_model=QuizSessionListItem,
)
async def stop_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    svc: QuizService | None = Depends(get_quiz_service),
):
    """FR-19/FR-24/G10: atomic stop — completed iff ≥1 answered question,
    abandoned otherwise. Re-stop is idempotent. Side effect: enqueue
    QUIZ_ROLLUP on completed (deduped by partial UNIQUE INDEX)."""
    quiz = _require_service(svc)
    try:
        await quiz.stop_session(session_id=session_id)
    except QuizNotFoundError as e:
        raise HTTPException(404, detail=str(e)) from e
    await db.commit()
    from sqlalchemy.orm import selectinload

    qs = await db.scalar(
        select(QuizSession)
        .where(QuizSession.id == session_id)
        .options(selectinload(QuizSession.questions))
    )
    return _serialize_session_list_item(qs)


@router.get("/api/v1/quiz-sessions/{session_id}/export")
async def export_quiz_session(
    session_id: int,
    fmt: str = "markdown",
    db: AsyncSession = Depends(get_db),
):
    """FR-100..FR-105 / §9.10: Markdown export for a single quiz session.

    Refuses abandoned sessions (E15) → 404 with explanation.
    """
    from fastapi.responses import Response

    from app.services.export_service import ExportError, ExportService, QuizExportError

    if fmt != "markdown":
        raise HTTPException(400, detail=f"Unsupported fmt={fmt!r}; only 'markdown'.")

    svc = ExportService(session=db)
    try:
        body = await svc.export_quiz_session(session_id, fmt="markdown")
    except QuizExportError as e:
        raise HTTPException(404, detail=str(e)) from e
    except ExportError as e:
        # Unknown session OR unknown book → 404.
        raise HTTPException(404, detail=str(e)) from e

    # Look up the book slug for the filename.
    qs = await db.scalar(select(QuizSession).where(QuizSession.id == session_id))
    book = await db.scalar(select(Book).where(Book.id == qs.book_id)) if qs else None
    from app.services.slug import gfm_slug

    slug = gfm_slug(book.title) if (book and book.title) else f"book-{qs.book_id if qs else 0}"
    filename = f"{slug}_quiz_session_{session_id}.md"
    return Response(
        content=body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
