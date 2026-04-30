"""Processing API: summarization trigger, SSE streaming, status, cancel."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncGenerator  # noqa: TC003

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db, get_settings
from app.api.schemas import (
    ProcessingCancelResponse,
    ProcessingJobDetailResponse,
    ProcessingStartRequest,
    ProcessingStartResponse,
    ProcessingStatusResponse,
)
from app.config import Settings  # noqa: TC001
from app.db.models import Book, BookSection, ProcessingJob, ProcessingJobStatus, ProcessingStep

router = APIRouter(tags=["processing"])


@router.post("/api/v1/books/{book_id}/summarize")
async def start_processing(
    book_id: int,
    body: ProcessingStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Start summarization processing for a book."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Validate preset_name exists before queuing the job
    if body.preset_name:
        from app.services.preset_service import PresetError, PresetService

        try:
            PresetService().load(body.preset_name)
        except PresetError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # Preflight gate (FR-B10): block job creation when no usable LLM CLI is
    # available. Returns 400 with structured payload so the UI can render a
    # specific message instead of "summarization failed" mid-job.
    from app.services.llm_preflight import get_preflight_service

    preflight = await get_preflight_service().check(settings.llm.provider)
    if not preflight.binary_resolved:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "llm_provider_unavailable",
                "preflight": preflight.model_dump(),
            },
        )

    # Validate scope + section_id combinations (FR-24, FR-27)
    if body.scope == "section":
        if body.section_id is None:
            raise HTTPException(
                status_code=422,
                detail="scope='section' requires section_id",
            )
        section_row = (
            await db.execute(
                select(BookSection).where(
                    BookSection.id == body.section_id,
                    BookSection.book_id == book_id,
                )
            )
        ).scalar_one_or_none()
        if section_row is None:
            raise HTTPException(
                status_code=422,
                detail=f"section_id={body.section_id} does not belong to book {book_id}",
            )
    if body.scope == "pending" and body.force:
        raise HTTPException(
            status_code=400,
            detail="scope='pending' is incompatible with force=true",
        )
    if body.scope == "failed":
        has_failed = (
            await db.execute(
                select(BookSection.id)
                .where(
                    BookSection.book_id == book_id,
                    BookSection.last_failure_type.is_not(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if has_failed is None:
            raise HTTPException(
                status_code=400,
                detail="No failed sections to retry",
            )

    # FR-01/FR-02/FR-03 — on-demand stale-job sweep. Wrap the active-job
    # guard in BEGIN IMMEDIATE so concurrent retries serialize. If we find
    # a PENDING/RUNNING row that is_stale(), mark it FAILED in-place and
    # fall through to INSERT (recovers from server-killed-mid-job state
    # without requiring `bookcompanion init`). If the row is fresh, return
    # an enriched 409 body with the active_job payload so the UI can deep-
    # link the user to /jobs/{id}.
    from datetime import datetime, timedelta, timezone

    from app.services.summarizer.orphan_sweep import is_stale

    await db.execute(text("BEGIN IMMEDIATE"))
    existing = (
        await db.execute(
            select(ProcessingJob).where(
                ProcessingJob.book_id == book_id,
                ProcessingJob.status.in_(
                    [ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]
                ),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        now = datetime.now(timezone.utc)
        max_age = timedelta(seconds=settings.processing.stale_job_age_seconds)
        if is_stale(existing, now=now, max_age=max_age):
            existing.status = ProcessingJobStatus.FAILED
            existing.error_message = "Marked stale by on-demand sweep"
            existing.completed_at = now
            # Fall through to INSERT a fresh job; the same transaction will
            # commit both writes atomically.
        else:
            await db.commit()  # release the BEGIN IMMEDIATE write lock
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "A summarization job is already running for this book",
                    "active_job": {
                        "id": existing.id,
                        "scope": (existing.request_params or {}).get("scope"),
                        "started_at": existing.started_at.isoformat()
                        if existing.started_at
                        else None,
                        "progress": existing.progress or {},
                    },
                },
            )

    # Create processing job
    from app.services.job_queue_worker import serialize_request_params

    job = ProcessingJob(
        book_id=book_id,
        step=ProcessingStep.SUMMARIZE,
        status=ProcessingJobStatus.PENDING,
        pid=os.getpid(),
        request_params=serialize_request_params(body),
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError as e:
        # FR-A7.6 — TOCTOU race: another request won. Return 409.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A summarization job is already running for this book",
        ) from e
    await db.refresh(job)

    job_id = job.id

    # Get event bus from app state
    event_bus = getattr(request.app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.publish(
            str(job_id),
            "job_queued",
            {"job_id": job_id, "book_id": book_id},
        )

    return ProcessingStartResponse(job_id=job_id)



@router.get("/api/v1/processing/{job_id}/stream")
async def stream_processing(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for processing progress."""
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")

    event_bus = getattr(request.app.state, "event_bus", None)
    if not event_bus:
        raise HTTPException(status_code=500, detail="Event bus not available")

    queue = event_bus.subscribe(str(job_id))

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if event["event"] == "close":
                        break
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"]),
                    }
                except TimeoutError:
                    yield {"event": "keepalive", "data": ""}
        finally:
            event_bus.unsubscribe(str(job_id), queue)

    return EventSourceResponse(event_generator())


@router.get("/api/v1/processing/{job_id}/status")
async def get_processing_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get current processing job status."""
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")

    return ProcessingStatusResponse(
        job_id=job.id,
        book_id=job.book_id,
        step=job.step.value if hasattr(job.step, "value") else str(job.step),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        progress=job.progress,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("/api/v1/processing/{job_id}/cancel")
async def cancel_processing(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a processing job (FR-B14, FR-B15).

    PENDING → atomic delete. The partial UNIQUE index `one_active_per_book`
    is freed, so a new submission can take its place immediately.

    RUNNING → set ``cancel_requested=True`` and emit ``job_cancelling``;
    the queue worker observes the flag between sections, SIGTERMs the
    active subprocess, and finalizes the job FAILED with reason='cancelled'.

    Already-terminal states (COMPLETED / FAILED) → return ``ALREADY_DONE``.
    """
    # Atomic PENDING-cancel: DELETE WHERE status='PENDING' guarantees we
    # don't race a worker that just promoted the row.
    deleted = await db.execute(
        text("DELETE FROM processing_jobs WHERE id = :id AND status = 'PENDING'"),
        {"id": job_id},
    )
    await db.commit()
    if deleted.rowcount == 1:
        event_bus = getattr(request.app.state, "event_bus", None)
        if event_bus is not None:
            await event_bus.publish(
                str(job_id),
                "job_cancelling",
                {"job_id": job_id, "phase": "pending_removed"},
            )
            await event_bus.close(str(job_id))
        return ProcessingCancelResponse(
            job_id=job_id,
            status="PENDING_REMOVED",
            message="Pending job removed from queue",
        )

    # Either RUNNING, terminal, or non-existent.
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")

    if job.status == ProcessingJobStatus.RUNNING:
        job.cancel_requested = True
        await db.commit()
        event_bus = getattr(request.app.state, "event_bus", None)
        if event_bus is not None:
            await event_bus.publish(
                str(job_id),
                "job_cancelling",
                {
                    "job_id": job.id,
                    "book_id": job.book_id,
                    "phase": "running_terminating",
                },
            )
        # FR-B15 — SIGTERM the active subprocess via the running worker.
        # Snapshot both _active_job_id and _active_provider into local vars
        # before checking; the worker can clear them between attribute reads
        # when the job finishes mid-cancel.
        worker = getattr(request.app.state, "job_queue_worker", None)
        if worker is not None:
            active_id = worker._active_job_id
            active_provider = worker._active_provider
            if active_id == job_id and active_provider is not None:
                with contextlib.suppress(Exception):
                    await active_provider.terminate()
        return ProcessingCancelResponse(
            job_id=job.id, status="CANCEL_REQUESTED", message="Cancel requested"
        )

    return ProcessingCancelResponse(
        job_id=job.id,
        status="ALREADY_DONE",
        message=job.status.value if hasattr(job.status, "value") else str(job.status),
    )


@router.get("/api/v1/processing/jobs")
async def list_processing_jobs(
    status: str = "PENDING,RUNNING",
    db: AsyncSession = Depends(get_db),
):
    """Active-jobs seed endpoint (T13 / FR-B14a).

    Returns active processing jobs ordered by ``created_at ASC`` with a
    computed ``queue_position`` (0 for RUNNING, 1..N for PENDING). The
    frontend's ``useJobQueueStore`` hits this on mount to hydrate before
    the SSE stream connects.
    """
    statuses = [s.strip().upper() for s in status.split(",") if s.strip()]
    if not statuses:
        statuses = ["PENDING", "RUNNING"]

    rows = (
        await db.execute(
            select(ProcessingJob, Book.title)
            .join(Book, Book.id == ProcessingJob.book_id)
            .where(ProcessingJob.status.in_(statuses))
            .order_by(ProcessingJob.created_at.asc())
        )
    ).all()

    jobs: list[dict] = []
    pending_index = 1
    for job, book_title in rows:
        is_running = job.status == ProcessingJobStatus.RUNNING
        queue_position = 0 if is_running else pending_index
        if not is_running:
            pending_index += 1
        jobs.append(
            {
                "job_id": job.id,
                "book_id": job.book_id,
                "book_title": book_title,
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "queue_position": queue_position,
                "progress": job.progress,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "last_event_at": job.last_event_at.isoformat() if job.last_event_at else None,
                "cancel_requested": bool(job.cancel_requested),
            }
        )
    return {"jobs": jobs}


# Registered last so the literal-prefix routes ("/jobs", "/{id}/stream", etc.)
# match first. FastAPI matches routes in registration order; a leading
# `/{job_id}` would otherwise shadow `/jobs` and cast "jobs" to int (→ 422).
@router.get("/api/v1/processing/{job_id}", response_model=ProcessingJobDetailResponse)
async def get_processing_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Full job state for JobProgressView deep-link (FR-10, FR-11, spec §7.4)."""
    result = await db.execute(
        select(ProcessingJob)
        .options(selectinload(ProcessingJob.book))
        .where(ProcessingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found")

    params = job.request_params or {}
    return ProcessingJobDetailResponse(
        job_id=job.id,
        book_id=job.book_id,
        book_title=job.book.title if job.book else None,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        scope=params.get("scope"),
        section_id=params.get("section_id"),
        progress=job.progress,
        started_at=job.started_at,
        completed_at=job.completed_at,
        last_event_at=job.last_event_at,
        error_message=job.error_message,
        request_params=params or None,
    )
