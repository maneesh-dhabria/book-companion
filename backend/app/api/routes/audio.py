"""Audio (TTS) HTTP routes — queue jobs, inventory, lookup, serve, delete, sample."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_settings
from app.config import Settings
from app.db.models import (
    AudioFile,
    Book,
    BookSection,
    ContentType,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingStep,
)

router = APIRouter()


SAMPLE_VOICE_TEXT = (
    "This is a quick sample of the selected voice for the Book Companion audiobook feature."
)


# --- Pydantic ----------------------------------------------------------------


class AudioJobRequest(BaseModel):
    scope: Literal["all", "sections", "book"] = "all"
    section_ids: list[int] | None = None
    voice: str
    engine: Literal["kokoro"] = "kokoro"


class AudioSampleRequest(BaseModel):
    voice: str = Field(..., min_length=1)


# --- Helpers -----------------------------------------------------------------


async def _resolve_audio_units(db: AsyncSession, *, book_id: int, body: AudioJobRequest) -> int:
    """Compute the unit count for a request — matches worker's resolver."""
    if body.scope == "book":
        book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
        if book is None or book.default_summary_id is None:
            return 0
        return 1
    rows = await db.execute(select(BookSection.id).where(BookSection.book_id == book_id))
    ids = [r[0] for r in rows.all()]
    if body.section_ids:
        ids = [i for i in ids if i in set(body.section_ids)]
    return len(ids)


def _data_dir(settings: Settings) -> Path:
    return Path(settings.data.directory)


# --- B7: POST queue ----------------------------------------------------------


@router.post("/api/v1/books/{book_id}/audio", status_code=202)
async def queue_audio_job(
    book_id: int,
    body: AudioJobRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    if body.engine == "web-speech":
        raise HTTPException(status_code=400, detail={"error": "web_speech_not_pregeneratable"})
    if shutil.which("ffmpeg") is None:
        raise HTTPException(status_code=503, detail={"error": "ffmpeg_missing"})

    # BEGIN IMMEDIATE — race-safe queue (FR-18)
    await db.execute(text("BEGIN IMMEDIATE"))
    existing = (
        await db.execute(
            select(ProcessingJob).where(
                ProcessingJob.book_id == book_id,
                ProcessingJob.step == ProcessingStep.AUDIO,
                ProcessingJob.status.in_(
                    [ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]
                ),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "error": "audio_job_in_progress",
                "existing_job_id": existing.id,
                "scope": (existing.request_params or {}).get("scope"),
                "started_at": existing.created_at.isoformat() if existing.created_at else None,
            },
        )

    total_units = await _resolve_audio_units(db, book_id=book_id, body=body)
    if total_units == 0:
        await db.commit()
        raise HTTPException(status_code=400, detail={"error": "no_units"})

    job = ProcessingJob(
        book_id=book_id,
        step=ProcessingStep.AUDIO,
        status=ProcessingJobStatus.PENDING,
        request_params=body.model_dump(),
        progress={
            "completed": 0,
            "total": total_units,
            "current_kind": None,
            "current_ref": None,
            "last_event_at": time.time_ns(),
            "already_stale": 0,
        },
    )
    db.add(job)
    await db.commit()

    event_bus = getattr(request.app.state, "event_bus", None)
    if event_bus is not None:
        await event_bus.publish(str(job.id), "job_queued", {"job_id": job.id, "step": "audio"})

    return {"job_id": job.id, "scope": body.scope, "total_units": total_units}


# --- B8: GET inventory -------------------------------------------------------


@router.get("/api/v1/books/{book_id}/audio")
async def get_audio_inventory(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    rows = (
        (
            await db.execute(
                select(AudioFile)
                .where(AudioFile.book_id == book_id)
                .order_by(AudioFile.content_type, AudioFile.content_id)
            )
        )
        .scalars()
        .all()
    )
    files = [
        {
            "id": r.id,
            "content_type": r.content_type.value
            if hasattr(r.content_type, "value")
            else r.content_type,
            "content_id": r.content_id,
            "voice": r.voice,
            "url": f"/api/v1/books/{book_id}/audio/"
            f"{r.content_type.value if hasattr(r.content_type, 'value') else r.content_type}/"
            f"{r.content_id}.mp3",
            "duration_seconds": r.duration_seconds,
            "file_size_bytes": r.file_size_bytes,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "source_hash": r.source_hash,
            "stale": False,  # cheap form; lookup endpoint computes truth
        }
        for r in rows
    ]
    total_sections = (
        (await db.execute(select(BookSection.id).where(BookSection.book_id == book_id)))
        .scalars()
        .all()
    )
    return {
        "book_id": book_id,
        "files": files,
        "coverage": {
            "total": len(total_sections),
            "generated": len(files),
            "stale": 0,
        },
    }


# --- B9: GET lookup ----------------------------------------------------------


@router.get("/api/v1/audio/lookup")
async def audio_lookup(
    book_id: int,
    content_type: str,
    content_id: int,
    voice: str | None = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.db.repositories.audio_file_repo import AudioFileRepository
    from app.db.repositories.section_repo import SectionRepository
    from app.db.repositories.summary_repo import SummaryRepository
    from app.services.audio_gen_service import AudioGenService
    from app.services.tts.markdown_to_speech import EmptySanitizedTextError, sanitize

    try:
        ct = ContentType(content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"unknown content_type {content_type}") from e

    voice = voice or settings.tts.voice or "af_sarah"

    # Fetch source_md based on content_type
    source_md = ""
    if ct == ContentType.SECTION_SUMMARY:
        section_repo = SectionRepository(db)
        section = await section_repo.get_by_id(content_id)
        if section is None:
            raise HTTPException(status_code=404, detail="section not found")
        if section.default_summary_id is not None:
            summary_repo = SummaryRepository(db)
            s = await summary_repo.get_by_id(section.default_summary_id)
            if s is not None:
                source_md = s.summary_md or ""
        if not source_md:
            source_md = section.content_md or ""
    elif ct == ContentType.BOOK_SUMMARY:
        from app.db.repositories.book_repo import BookRepository

        book_repo = BookRepository(db)
        book = await book_repo.get_by_id(book_id)
        if book is None or book.default_summary_id is None:
            raise HTTPException(status_code=404, detail="book summary not found")
        summary_repo = SummaryRepository(db)
        s = await summary_repo.get_by_id(book.default_summary_id)
        source_md = s.summary_md or "" if s else ""
    elif ct == ContentType.SECTION_CONTENT:
        section_repo = SectionRepository(db)
        section = await section_repo.get_by_id(content_id)
        if section is None:
            raise HTTPException(status_code=404, detail="section not found")
        source_md = section.content_md or ""
    elif ct == ContentType.ANNOTATIONS_PLAYLIST:
        # FR-54/55: synthesize from concatenated highlight+note text. Web Speech
        # fallback when no pre-generated MP3 exists.
        from app.db.repositories.annotation_repo import AnnotationRepository

        ann_repo = AnnotationRepository(db)
        anns = await ann_repo.list_by_book(content_id)
        parts: list[str] = []
        for a in anns:
            if a.selected_text:
                parts.append(a.selected_text)
            if a.note:
                parts.append(a.note)
        source_md = "\n\n".join(parts)

    if not source_md.strip():
        # No source — empty result, fronts can render "no content"
        return {
            "pregenerated": False,
            "sanitized_text": "",
            "sentence_offsets_chars": [],
            "stale": False,
        }

    try:
        sanitize(source_md)
    except EmptySanitizedTextError:
        return {
            "pregenerated": False,
            "sanitized_text": "",
            "sentence_offsets_chars": [],
            "stale": False,
        }

    audio_repo = AudioFileRepository(db, _data_dir(settings))
    # No tts_provider needed for lookup-only (no synthesis happens here).
    service = AudioGenService(
        session=db, audio_repo=audio_repo, tts_provider=None, data_dir=_data_dir(settings)
    )
    result = await service.lookup(
        book_id=book_id,
        content_type=ct,
        content_id=content_id,
        voice=voice,
        current_source_md=source_md,
    )
    return {
        "pregenerated": result.pregenerated,
        "sanitized_text": result.sanitized_text,
        "sentence_offsets_chars": result.sanitized_text and result.sentence_offsets_chars,
        "url": result.url,
        "duration_seconds": result.duration_seconds,
        "voice": result.voice,
        "sentence_offsets_seconds": result.sentence_offsets_seconds,
        "source_hash_stored": result.source_hash_stored,
        "source_hash_current": result.source_hash_current,
        "sanitizer_version_stored": result.sanitizer_version_stored,
        "sanitizer_version_current": result.sanitizer_version_current,
        "stale": result.stale,
        "stale_reason": result.stale_reason,
    }


# --- B10: GET serve ----------------------------------------------------------


@router.get("/api/v1/books/{book_id}/audio/{content_type}/{content_id}.mp3")
async def serve_audio(
    book_id: int,
    content_type: str,
    content_id: int,
    voice: str | None = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        ct = ContentType(content_type)
    except ValueError as e:
        raise HTTPException(status_code=404) from e

    q = select(AudioFile).where(
        AudioFile.book_id == book_id,
        AudioFile.content_type == ct,
        AudioFile.content_id == content_id,
    )
    if voice:
        q = q.where(AudioFile.voice == voice)
    row = (await db.execute(q.limit(1))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    abs_path = _data_dir(settings) / row.file_path
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="audio file missing on disk")
    return FileResponse(
        abs_path,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# --- B11: DELETE all ---------------------------------------------------------


@router.delete("/api/v1/books/{book_id}/audio", status_code=204)
async def delete_all_audio(
    book_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.db.repositories.audio_file_repo import AudioFileRepository

    # Cancel any in-flight audio job
    job = (
        await db.execute(
            select(ProcessingJob).where(
                ProcessingJob.book_id == book_id,
                ProcessingJob.step == ProcessingStep.AUDIO,
                ProcessingJob.status.in_(
                    [ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING]
                ),
            )
        )
    ).scalar_one_or_none()
    if job is not None:
        job.cancel_requested = True
        if job.status == ProcessingJobStatus.PENDING:
            job.status = ProcessingJobStatus.FAILED
            job.error_message = "cancelled"
        await db.commit()

    repo = AudioFileRepository(db, _data_dir(settings))
    await repo.delete_all_for_book(book_id)
    await db.commit()
    return None


# --- B12: DELETE per-row -----------------------------------------------------


@router.delete("/api/v1/books/{book_id}/audio/{content_type}/{content_id}", status_code=204)
async def delete_one_audio(
    book_id: int,
    content_type: str,
    content_id: int,
    voice: str | None = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        ct = ContentType(content_type)
    except ValueError as e:
        raise HTTPException(status_code=404) from e

    # 409 if a RUNNING job is currently writing this unit
    running = (
        await db.execute(
            select(ProcessingJob).where(
                ProcessingJob.book_id == book_id,
                ProcessingJob.step == ProcessingStep.AUDIO,
                ProcessingJob.status == ProcessingJobStatus.RUNNING,
            )
        )
    ).scalar_one_or_none()
    if running is not None:
        progress = running.progress or {}
        if progress.get("current_kind") == ct.value and progress.get("current_ref") == content_id:
            raise HTTPException(
                status_code=409,
                detail="Wait or cancel job before deleting an in-flight unit",
            )

    from app.db.repositories.audio_file_repo import AudioFileRepository

    repo = AudioFileRepository(db, _data_dir(settings))
    n = await repo.delete_one(book_id=book_id, content_type=ct, content_id=content_id, voice=voice)
    await db.commit()
    if n == 0:
        raise HTTPException(status_code=404, detail="audio file not found")
    return None


# --- B13: POST sample (rate-limited at 5/min/IP) -----------------------------

_SAMPLE_RATE_BUCKET: dict[str, list[float]] = {}
_SAMPLE_LIMIT = 5
_SAMPLE_WINDOW_SECONDS = 60.0


def _rate_limit_check(client_ip: str) -> bool:
    now = time.monotonic()
    bucket = _SAMPLE_RATE_BUCKET.setdefault(client_ip, [])
    bucket[:] = [t for t in bucket if now - t < _SAMPLE_WINDOW_SECONDS]
    if len(bucket) >= _SAMPLE_LIMIT:
        return False
    bucket.append(now)
    return True


@router.post("/api/v1/audio/sample")
async def audio_sample(
    body: AudioSampleRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
):
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limit_check(client_ip):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    from app.services.tts import create_tts_provider

    provider = create_tts_provider("kokoro", settings)
    if provider is None:
        raise HTTPException(status_code=503, detail="kokoro_unavailable")
    try:
        result = provider.synthesize(SAMPLE_VOICE_TEXT, voice=body.voice, speed=1.0)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return _mp3_response(result.audio_bytes)


def _mp3_response(audio_bytes: bytes):
    from fastapi.responses import Response

    return Response(content=audio_bytes, media_type="audio/mpeg")
