"""POST /api/v1/books/{book_id}/book-summary — queue book-level summary job."""

from __future__ import annotations

import asyncio
import os

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.api.deps import get_db, get_settings
from app.config import Settings  # noqa: TC001
from app.db.models import (
    Book,
    BookSection,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
)

logger = structlog.get_logger()
router = APIRouter(tags=["book-summary"])


class BookSummaryRequest(BaseModel):
    preset_name: str = "practitioner_bullets"
    skip_eval: bool = True
    no_retry: bool = True


class BookSummaryResponse(BaseModel):
    job_id: int


@router.post(
    "/api/v1/books/{book_id}/book-summary",
    response_model=BookSummaryResponse,
    status_code=201,
)
async def start_book_summary(
    book_id: int,
    body: BookSummaryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    # 404 — book doesn't exist.
    book = (
        await db.execute(select(Book).where(Book.id == book_id))
    ).scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    # 400 — no section summaries available to reduce from.
    has_any_summary = (
        await db.execute(
            select(BookSection).where(
                BookSection.book_id == book_id,
                BookSection.default_summary_id.is_not(None),
            )
        )
    ).first()
    if has_any_summary is None:
        raise HTTPException(
            status_code=400,
            detail="Summarize sections first — no section summaries to reduce from",
        )

    # 400 — invalid preset.
    from app.services.preset_service import PresetError, PresetService

    try:
        PresetService().load(body.preset_name)
    except PresetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 409 — a job is already in-flight for this book (shares the same
    # processing_jobs table and partial UNIQUE index as /summarize).
    in_flight = (
        await db.execute(
            select(ProcessingJob).where(
                ProcessingJob.book_id == book_id,
                ProcessingJob.status.in_(
                    [ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]
                ),
            )
        )
    ).scalar_one_or_none()
    if in_flight is not None:
        raise HTTPException(
            status_code=409,
            detail="A summarization job is already running for this book",
        )

    job = ProcessingJob(
        book_id=book_id,
        step=ProcessingStep.SUMMARIZE,
        status=ProcessingJobStatus.PENDING,
        pid=os.getpid(),
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A summarization job is already running for this book",
        ) from e
    await db.refresh(job)
    job_id = job.id

    event_bus = getattr(request.app.state, "event_bus", None)

    async def _run():
        from app.db.session import create_session_factory
        from app.services.summarizer import create_llm_provider, detect_llm_provider
        from app.services.summarizer.summarizer_service import SummarizerService

        session_factory = create_session_factory(settings)
        async with session_factory() as bg_session:
            bg_job = (
                await bg_session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == job_id)
                )
            ).scalar_one()
            bg_job.status = ProcessingJobStatus.RUNNING
            await bg_session.commit()

            book_summary_id: int | None = None
            error_message: str | None = None
            try:
                provider = settings.llm.provider
                if provider == "auto":
                    provider = detect_llm_provider()
                llm = create_llm_provider(
                    provider,
                    cli_command=settings.llm.cli_command,
                    default_model=settings.llm.model,
                    default_timeout=settings.llm.timeout_seconds,
                    max_budget_usd=settings.llm.max_budget_usd,
                    config_dir=settings.llm.config_dir,
                )
                if llm is None:
                    raise RuntimeError(
                        "No LLM provider available. Install Claude CLI or Codex CLI."
                    )
                summarizer = SummarizerService(
                    db=bg_session, llm=llm, config=settings
                )
                summary = await summarizer.summarize_book_level(
                    book_id=book_id,
                    preset_name=body.preset_name,
                    skip_eval=body.skip_eval,
                    no_retry=body.no_retry,
                )
                book_summary_id = summary.id
                bg_job.status = ProcessingJobStatus.COMPLETED
                await bg_session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("book_summary_job_failed", error=str(exc))
                bg_job.status = ProcessingJobStatus.FAILED
                bg_job.error_message = str(exc)
                error_message = str(exc)
                await bg_session.commit()

            if event_bus:
                if error_message is None:
                    # FR-E4.3 — surface freshly-written suggested_tags in
                    # the completion event so the UI can pop the review
                    # chips without an extra fetch.
                    suggested_tags: list[str] = []
                    try:
                        from sqlalchemy.exc import SQLAlchemyError

                        from app.db.models import Book

                        async with session_factory() as post_session:
                            b = await post_session.get(Book, book_id)
                            if b and b.suggested_tags_json:
                                suggested_tags = list(b.suggested_tags_json)
                    except SQLAlchemyError:
                        logger.exception("suggested_tags_fetch_failed", book_id=book_id)
                        suggested_tags = []

                    await event_bus.publish(
                        str(job_id),
                        "processing_completed",
                        {
                            "book_id": book_id,
                            "completed": 1,
                            "failed": 0,
                            "skipped": 0,
                            "book_summary_id": book_summary_id,
                            "suggested_tags": suggested_tags,
                        },
                    )
                else:
                    await event_bus.publish(
                        str(job_id),
                        "processing_failed",
                        {"book_id": book_id, "error": error_message},
                    )
                await event_bus.close(str(job_id))

    asyncio.create_task(_run())

    return BookSummaryResponse(job_id=job_id)
