"""Processing API: summarization trigger, SSE streaming, status, cancel."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator  # noqa: TC003

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db, get_settings
from app.api.schemas import (
    ProcessingCancelResponse,
    ProcessingStartRequest,
    ProcessingStartResponse,
    ProcessingStatusResponse,
)
from app.config import Settings  # noqa: TC001
from app.db.models import Book, ProcessingJob, ProcessingJobStatus, ProcessingStep

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

    # Create processing job
    job = ProcessingJob(
        book_id=book_id,
        step=ProcessingStep.SUMMARIZE,
        status=ProcessingJobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    job_id = job.id

    # Get event bus from app state
    event_bus = getattr(request.app.state, "event_bus", None)

    # Launch background task
    async def _run_processing():
        from app.db.session import create_session_factory

        session_factory = create_session_factory(settings)
        async with session_factory() as bg_session:
            # Update job to running
            result = await bg_session.execute(
                select(ProcessingJob).where(ProcessingJob.id == job_id)
            )
            bg_job = result.scalar_one()
            bg_job.status = ProcessingJobStatus.RUNNING
            await bg_session.commit()

            try:
                from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider
                from app.services.summarizer.image_captioner import ImageCaptioner
                from app.services.summarizer.summarizer_service import SummarizerService

                llm = ClaudeCodeCLIProvider(
                    cli_command=settings.llm.cli_command,
                    default_model=settings.llm.model,
                    default_timeout=settings.llm.timeout_seconds,
                    max_budget_usd=settings.llm.max_budget_usd,
                )
                captioner = (
                    ImageCaptioner(llm_provider=llm)
                    if settings.images.captioning_enabled
                    else None
                )
                summarizer = SummarizerService(
                    db=bg_session, llm=llm, config=settings, captioner=captioner
                )

                async def on_section_start(section_id, section_title, index, total):
                    if event_bus:
                        await event_bus.publish(
                            str(job_id),
                            "section_started",
                            {
                                "section_id": section_id,
                                "title": section_title,
                                "index": index,
                                "total": total,
                            },
                        )

                async def on_section_complete(section_id, section_title, index, total):
                    if event_bus:
                        await event_bus.publish(
                            str(job_id),
                            "section_completed",
                            {
                                "section_id": section_id,
                                "title": section_title,
                                "index": index,
                                "total": total,
                            },
                        )

                await summarizer.summarize_book(
                    book_id,
                    preset_name=body.preset_name,
                    run_eval=body.run_eval,
                    auto_retry=body.auto_retry,
                    skip_eval=body.skip_eval,
                    on_section_start=on_section_start,
                    on_section_complete=on_section_complete,
                )

                bg_job.status = ProcessingJobStatus.COMPLETED
                await bg_session.commit()

                if event_bus:
                    await event_bus.publish(
                        str(job_id), "processing_completed", {"book_id": book_id}
                    )
                    await event_bus.close(str(job_id))

            except Exception as e:
                bg_job.status = ProcessingJobStatus.FAILED
                bg_job.error_message = str(e)
                await bg_session.commit()

                if event_bus:
                    await event_bus.publish(
                        str(job_id),
                        "processing_failed",
                        {"book_id": book_id, "error": str(e)},
                    )
                    await event_bus.close(str(job_id))

    asyncio.create_task(_run_processing())

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
    db: AsyncSession = Depends(get_db),
):
    """Cancel a processing job."""
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")

    if job.status == ProcessingJobStatus.RUNNING:
        job.status = ProcessingJobStatus.FAILED
        job.error_message = "Cancelled by user"
        await db.commit()
        return ProcessingCancelResponse(
            job_id=job.id, status="cancelled", message="Processing cancelled"
        )

    return ProcessingCancelResponse(
        job_id=job.id,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        message="Job is not running",
    )
