"""Global single-RUNNING queue worker for summarization jobs.

Replaces the per-request ``asyncio.create_task(_run_processing())`` pattern
with a process-wide worker that polls every ~2 s, atomically promotes the
oldest PENDING job to RUNNING when no RUNNING job exists, and runs it.

Key invariants (D7, D8, FR-B11..FR-B13, FR-B23):
* At most one RUNNING summarization job globally — enforced atomically by
  the promotion UPDATE statement (single-row UPDATE with NOT EXISTS guard).
* Per-job ``LLMProvider`` re-instantiation: the worker reads ``Settings()``
  fresh at promotion time and constructs a new provider, so a settings
  change between submission and promotion takes effect.
* Cancel: ``cancel_requested=True`` is observed (a) when picking the next
  job — PENDING-cancel handled by the route via DELETE WHERE PENDING — and
  (b) between sections during a RUNNING job. RUNNING cancel additionally
  SIGTERMs the active subprocess via ``provider.terminate()`` (see T12).

Lifespan: started in ``app/api/main.py:lifespan`` and stored on
``app.state.job_queue_worker``. ``stop()`` cancels the polling task and
awaits its CancelledError so shutdown is clean.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import ProcessingJob, ProcessingJobStatus, ProcessingStep

log = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = 2.0


class JobQueueWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus,
        settings: Settings,
        poll_interval: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._settings = settings
        self._poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        # Track the currently-RUNNING provider so cancel can SIGTERM it (T12).
        self._active_provider = None
        self._active_job_id: int | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_loop(), name="JobQueueWorker")
        log.info("queue_worker_started", poll_interval=self._poll_interval)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("queue_worker_stopped")

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.tick()
            except Exception:  # noqa: BLE001 — keep the loop alive on any error
                log.exception("queue_worker_tick_failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._poll_interval
                )
            except TimeoutError:
                pass

    async def tick(self) -> bool:
        """Promote the oldest PENDING job (if any) to RUNNING and run it.

        Returns True if a job was promoted, False otherwise. Tests call this
        directly to drive the worker deterministically.
        """
        promoted_id = await self._atomic_promote()
        if promoted_id is None:
            return False
        async with self._session_factory() as session:
            job_row = (
                await session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == promoted_id)
                )
            ).scalar_one_or_none()
            if job_row is None:
                return False
            await self._on_promoted(session, job_row)
        return True

    async def _atomic_promote(self) -> int | None:
        """Atomically pick the oldest PENDING job and flip it to RUNNING.

        ``UPDATE ... WHERE id = (SELECT ... ORDER BY created_at LIMIT 1) AND
        NOT EXISTS (RUNNING) RETURNING id`` is a single-statement update that
        SQLite executes serializably under WAL — no two callers can flip
        the same row, and no flip happens while a RUNNING row exists. The
        ``RETURNING`` clause gives us the promoted row id directly, avoiding
        a fragile second SELECT keyed on ``last_event_at`` (which would
        match multiple rows if two ticks happened to share a microsecond,
        e.g., on a worker restart that preserved a stale RUNNING row).
        """
        async with self._session_factory() as session:
            now = datetime.utcnow()
            result = await session.execute(
                text(
                    """
                    UPDATE processing_jobs
                       SET status = 'RUNNING',
                           started_at = :now,
                           last_event_at = :now
                     WHERE id = (
                         SELECT id FROM processing_jobs
                          WHERE status = 'PENDING'
                            AND cancel_requested = 0
                            AND NOT EXISTS (
                                SELECT 1 FROM processing_jobs WHERE status = 'RUNNING'
                            )
                          ORDER BY created_at ASC
                          LIMIT 1
                     )
                    RETURNING id
                    """
                ),
                {"now": now},
            )
            row = result.fetchone()
            await session.commit()
            return int(row[0]) if row is not None else None

    async def _on_promoted(self, session: AsyncSession, job: ProcessingJob) -> None:
        """Emit job_promoted SSE then run the actual processing inline.

        Runs in the worker's polling coroutine, so SSE FIFO is preserved
        between job_promoted and the first section_started event (FR-B23,
        §6.4 invariant ordering).
        """
        log.info("queue_worker_promoted_job", job_id=job.id, book_id=job.book_id)
        if self._event_bus is not None:
            await self._event_bus.publish(
                str(job.id),
                "job_promoted",
                {
                    "job_id": job.id,
                    "book_id": job.book_id,
                    "last_event_at": (
                        job.last_event_at.isoformat() if job.last_event_at else None
                    ),
                },
            )
        if job.step == ProcessingStep.AUDIO:
            await self._run_audio_job(job.id, job.book_id, job.request_params or {})
        else:
            await self._run_processing(job.id, job.book_id, job.request_params or {})

    async def _run_audio_job(
        self,
        job_id: int,
        book_id: int,
        request_params: dict[str, Any],
    ) -> None:
        """Execute an AUDIO ProcessingJob.

        Builds AudioGenService inline (per-job re-instantiation, mirroring
        summarize path). Resolves units from ``request_params['scope']`` +
        ``section_ids`` against the live BookSection / Summary tables.
        """
        from app.config import Settings as _Settings
        from app.db.models import ContentType
        from app.db.repositories.audio_file_repo import AudioFileRepository
        from app.db.repositories.section_repo import SectionRepository
        from app.db.repositories.summary_repo import SummaryRepository
        from app.services.audio_gen_service import AudioGenService
        from app.services.tts import create_tts_provider

        settings = _Settings()
        event_bus = self._event_bus
        voice = request_params.get("voice", "af_sarah")
        scope = request_params.get("scope", "all")
        explicit_ids = request_params.get("section_ids") or []

        async with self._session_factory() as bg_session:
            bg_job = (
                await bg_session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == job_id)
                )
            ).scalar_one_or_none()
            if bg_job is None:
                log.warning("audio_worker_run_missing_job", job_id=job_id)
                return

            try:
                provider = create_tts_provider("kokoro", settings)
                if provider is None:
                    raise RuntimeError("Kokoro TTS provider unavailable")
                self._active_provider = provider
                self._active_job_id = job_id

                section_repo = SectionRepository(bg_session)
                summary_repo = SummaryRepository(bg_session)
                audio_repo = AudioFileRepository(
                    bg_session, settings.data.directory / "audio_data"
                    if hasattr(settings.data.directory, "__truediv__")
                    else settings.data.directory
                )
                # Reuse the configured data dir from settings for atomic writes
                from pathlib import Path as _Path

                data_dir = _Path(settings.data.directory)
                audio_repo = AudioFileRepository(bg_session, data_dir)
                service = AudioGenService(
                    session=bg_session,
                    audio_repo=audio_repo,
                    tts_provider=provider,
                    data_dir=data_dir,
                )

                units = await self._resolve_audio_units(
                    bg_session, section_repo, summary_repo,
                    book_id=book_id, scope=scope, explicit_ids=explicit_ids,
                )

                async def emit(name: str, data: dict[str, Any]) -> None:
                    if event_bus is not None:
                        await event_bus.publish(str(job_id), name, data)

                await service.run_job(
                    job=bg_job, units=units, voice=voice, on_event=emit
                )
                if event_bus is not None:
                    await event_bus.close(str(job_id))
            except Exception as e:  # noqa: BLE001
                bg_job.status = ProcessingJobStatus.FAILED
                bg_job.error_message = str(e)[-2048:]
                await bg_session.commit()
                if event_bus is not None:
                    await event_bus.publish(
                        str(job_id),
                        "processing_failed",
                        {"book_id": book_id, "error": str(e), "reason": "error"},
                    )
                    await event_bus.close(str(job_id))
            finally:
                self._active_provider = None
                self._active_job_id = None

    @staticmethod
    async def _resolve_audio_units(
        session,
        section_repo,
        summary_repo,
        *,
        book_id: int,
        scope: str,
        explicit_ids: list[int],
    ) -> list:
        """Translate (scope, section_ids) → list of (ContentType, id, source_md).

        For ``scope='sections'`` and ``scope='all'`` we pull each section's
        default summary (falling back to content_md). For ``scope='book'`` we
        pull the book-level default summary as a single unit.
        """
        from app.db.models import ContentType
        from app.db.repositories.book_repo import BookRepository

        units = []
        if scope == "book":
            book_repo = BookRepository(session)
            book = await book_repo.get_by_id(book_id)
            if book is None or book.default_summary_id is None:
                return []
            summary = await summary_repo.get_by_id(book.default_summary_id)
            if summary is None or not summary.summary_md:
                return []
            units.append((ContentType.BOOK_SUMMARY, book.id, summary.summary_md))
            return units

        sections = await section_repo.get_by_book_id(book_id)
        if explicit_ids:
            id_set = set(explicit_ids)
            sections = [s for s in sections if s.id in id_set]
        for section in sections:
            source_md = None
            if section.default_summary_id is not None:
                summary = await summary_repo.get_by_id(section.default_summary_id)
                if summary is not None and summary.summary_md:
                    source_md = summary.summary_md
            if source_md is None:
                source_md = section.content_md or ""
            if source_md.strip():
                units.append((ContentType.SECTION_SUMMARY, section.id, source_md))
        return units

    async def _run_processing(
        self,
        job_id: int,
        book_id: int,
        request_params: dict[str, Any],
    ) -> None:
        """Execute the summarization for a promoted job.

        Body lifted from the previous ``processing.py:_run_processing``,
        adapted to read params from the persisted ``request_params`` blob
        and re-instantiate the provider from a fresh ``Settings()``.
        """
        from app.api.routes.processing import ProcessingStartRequest
        from app.services.summarizer import (
            create_llm_provider,
            detect_llm_provider,
        )
        from app.services.summarizer.evaluator import EvalService
        from app.services.summarizer.image_captioner import ImageCaptioner
        from app.services.summarizer.summarizer_service import SummarizerService

        body = ProcessingStartRequest(**request_params)
        # Per-job re-instantiation (FR-B12, P8): fresh Settings every time.
        settings = Settings()
        event_bus = self._event_bus

        async with self._session_factory() as bg_session:
            bg_job = (
                await bg_session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == job_id)
                )
            ).scalar_one_or_none()
            if bg_job is None:
                log.warning("queue_worker_run_missing_job", job_id=job_id)
                return

            try:
                provider_name = settings.llm.provider
                if provider_name == "auto":
                    provider_name = detect_llm_provider()
                llm = create_llm_provider(
                    provider_name,
                    config_dir=settings.llm.config_dir,
                    default_model=settings.llm.model,
                    default_timeout=settings.llm.timeout_seconds,
                    max_budget_usd=settings.llm.max_budget_usd,
                )
                if llm is None:
                    raise RuntimeError(
                        "No LLM provider available. Install Claude CLI or Codex CLI."
                    )
                self._active_provider = llm
                self._active_job_id = job_id

                captioner = (
                    ImageCaptioner(llm_provider=llm)
                    if settings.images.captioning_enabled
                    else None
                )
                summarizer = SummarizerService(
                    db=bg_session, llm=llm, config=settings, captioner=captioner
                )
                eval_svc = EvalService(db=bg_session, llm=llm, config=settings)

                callbacks = self._build_section_callbacks(job_id, event_bus)

                skip_eval = body.skip_eval or not body.run_eval
                no_retry = not body.auto_retry

                if event_bus is not None:
                    await event_bus.publish(
                        str(job_id),
                        "processing_started",
                        {
                            "book_id": book_id,
                            "job_id": job_id,
                            "scope": body.scope,
                        },
                    )

                result = await summarizer.summarize_book(
                    book_id,
                    preset_name=body.preset_name,
                    scope=body.scope,
                    section_id=body.section_id,
                    force=body.force,
                    skip_eval=skip_eval,
                    no_retry=no_retry,
                    eval_service=None if skip_eval else eval_svc,
                    **callbacks,
                )

                # Detect cancel-RUNNING: if cancel_requested flipped during
                # processing, treat the job as cancelled, not completed.
                await bg_session.refresh(bg_job)
                if bg_job.cancel_requested:
                    bg_job.status = ProcessingJobStatus.FAILED
                    bg_job.error_message = "cancelled"
                    await bg_session.commit()
                    if event_bus is not None:
                        await event_bus.publish(
                            str(job_id),
                            "processing_failed",
                            {
                                "book_id": book_id,
                                "error": "cancelled",
                                "reason": "cancelled",
                            },
                        )
                        await event_bus.close(str(job_id))
                    return

                failed_count = len(result.get("failed", []))
                completed_count = result.get("completed", 0)
                if failed_count > 0 and completed_count == 0:
                    bg_job.status = ProcessingJobStatus.FAILED
                    bg_job.error_message = (
                        f"All {failed_count} sections failed to summarize. "
                        f"Check logs for details."
                    )
                else:
                    bg_job.status = ProcessingJobStatus.COMPLETED
                    if failed_count > 0:
                        bg_job.error_message = (
                            f"{completed_count} sections succeeded, "
                            f"{failed_count} failed."
                        )
                await bg_session.commit()

                if event_bus is not None:
                    await event_bus.publish(
                        str(job_id),
                        "processing_completed",
                        {
                            "book_id": book_id,
                            "completed": completed_count,
                            "failed": failed_count,
                            "skipped": result.get("skipped", 0),
                            "book_summary_id": None,
                        },
                    )
                    await event_bus.close(str(job_id))

            except Exception as e:  # noqa: BLE001
                bg_job.status = ProcessingJobStatus.FAILED
                bg_job.error_message = str(e)
                await bg_session.commit()
                # Distinguish "binary disappeared mid-job" so the UI can
                # render a specific message; everything else falls under
                # the generic 'error' bucket (FR-B15b / spec §8.6).
                from app.exceptions import SubprocessNotFoundError

                reason = "cli_disappeared" if isinstance(e, SubprocessNotFoundError) else "error"
                if event_bus is not None:
                    await event_bus.publish(
                        str(job_id),
                        "processing_failed",
                        {"book_id": book_id, "error": str(e), "reason": reason},
                    )
                    await event_bus.close(str(job_id))
            finally:
                self._active_provider = None
                self._active_job_id = None

    def _build_section_callbacks(self, job_id: int, event_bus) -> dict[str, Any]:
        """Build the per-section SSE callbacks. Pulled out for readability."""
        if event_bus is None:
            return {}

        def on_start(section_id, index, total, section_title):
            asyncio.create_task(
                event_bus.publish(
                    str(job_id),
                    "section_started",
                    {
                        "section_id": section_id,
                        "title": section_title,
                        "index": index,
                        "total": total,
                    },
                )
            )

        def on_complete(section_id, index, total, section_title, elapsed=None, comp=None):
            asyncio.create_task(
                event_bus.publish(
                    str(job_id),
                    "section_completed",
                    {
                        "section_id": section_id,
                        "title": section_title,
                        "index": index,
                        "total": total,
                        "elapsed_seconds": elapsed,
                    },
                )
            )

        def on_skip(section_id, index, total, section_title, reason):
            asyncio.create_task(
                event_bus.publish(
                    str(job_id),
                    "section_skipped",
                    {
                        "section_id": section_id,
                        "title": section_title,
                        "index": index,
                        "total": total,
                        "reason": reason,
                    },
                )
            )

        def on_fail(section_id, index, total, section_title, error):
            error_type = getattr(error, "failure_type", None) or "unknown"
            message = str(error)
            truncated = message[:500] if message else None
            asyncio.create_task(
                event_bus.publish(
                    str(job_id),
                    "section_failed",
                    {
                        "section_id": section_id,
                        "title": section_title,
                        "index": index,
                        "total": total,
                        "error": message,
                        "error_type": error_type,
                        "error_message_truncated": truncated,
                    },
                )
            )

        def on_retry(section_id, index, total, section_title):
            asyncio.create_task(
                event_bus.publish(
                    str(job_id),
                    "section_retrying",
                    {
                        "section_id": section_id,
                        "title": section_title,
                        "index": index,
                        "total": total,
                    },
                )
            )

        return {
            "on_section_start": on_start,
            "on_section_complete": on_complete,
            "on_section_skip": on_skip,
            "on_section_fail": on_fail,
            "on_section_retry": on_retry,
        }


def serialize_request_params(body) -> dict[str, Any]:
    """Convert ProcessingStartRequest → JSON-safe dict for DB persistence.

    Lives here (not on the model) so the queue worker is the single
    consumer of the shape; the route just calls this helper.
    """
    if hasattr(body, "model_dump"):
        return json.loads(json.dumps(body.model_dump(), default=str))
    return dict(body)
