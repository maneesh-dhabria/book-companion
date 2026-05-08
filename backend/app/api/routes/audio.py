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


@router.get("/api/v1/audio/stale-books")
async def get_stale_audio_books(db: AsyncSession = Depends(get_db)):
    """Return books whose audio files are stale at the source-hash or sanitizer level.

    Fast cheap version: enumerates AudioFile rows whose source_hash or
    sanitizer_version is missing/changed vs the underlying source. For now,
    this is a best-effort placeholder — the per-row lookup endpoint computes
    the canonical staleness; library banner just needs a count.
    """
    from app.db.models import Book

    audio_files = (await db.execute(select(AudioFile))).scalars().all()
    book_ids: set[int] = set()
    for af in audio_files:
        # Cheap heuristic: AudioFile.sanitizer_version not matching current.
        from app.services.tts.markdown_to_speech import SANITIZER_VERSION

        if (af.sanitizer_version or "") != SANITIZER_VERSION:
            book_ids.add(af.book_id)
    if not book_ids:
        return {"books": []}
    books = (await db.execute(select(Book).where(Book.id.in_(book_ids)))).scalars().all()
    return {"books": [{"id": b.id, "title": b.title} for b in books]}


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

    if content_type == "annotation":
        # FR-22b: annotations have a dedicated route; reject here with a hint.
        raise HTTPException(
            status_code=400,
            detail="use /api/v1/audio/annotations/{id}/lookup for annotations",
        )

    try:
        ct = ContentType(content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"unknown content_type {content_type}") from e
    if ct == ContentType.ANNOTATION:
        # Defense-in-depth: enum value exists but is runtime-only.
        raise HTTPException(
            status_code=400,
            detail="use /api/v1/audio/annotations/{id}/lookup for annotations",
        )

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
    # Frontend AudioLookupResponse expects:
    #   stale: { reason: 'source_changed' | 'sanitizer_upgraded' | 'segmenter_drift' } | null
    #   source_hash: string | null  (the canonical/current hash)
    stale_obj = {"reason": result.stale_reason} if result.stale and result.stale_reason else None
    return {
        "pregenerated": result.pregenerated,
        "sanitized_text": result.sanitized_text,
        "sentence_offsets_chars": result.sanitized_text and result.sentence_offsets_chars,
        "url": result.url,
        "duration_seconds": result.duration_seconds,
        "voice": result.voice,
        "sentence_offsets_seconds": result.sentence_offsets_seconds,
        "source_hash": result.source_hash_current,
        # Internal/diagnostic fields retained for non-UI consumers (CLI, tests):
        "source_hash_stored": result.source_hash_stored,
        "source_hash_current": result.source_hash_current,
        "sanitizer_version_stored": result.sanitizer_version_stored,
        "sanitizer_version_current": result.sanitizer_version_current,
        "stale": stale_obj,
    }


@router.get("/api/v1/audio/annotations/{annotation_id}/lookup")
async def audio_lookup_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """FR-22 / plan T2: per-annotation TTS lookup.

    Annotations are runtime-only (D4 / FR-21): never persisted as audio
    files, never cached. Returns a Web-Speech-only payload with sanitized
    text + sentence offsets.
    """
    import hashlib

    from app.db.repositories.annotation_repo import AnnotationRepository
    from app.services.tts.markdown_to_speech import (
        SANITIZER_VERSION,
        EmptySanitizedTextError,
        sanitize,
    )

    repo = AnnotationRepository(db)
    ann = await repo.get_by_id(annotation_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="annotation not found")

    parts: list[str] = []
    if ann.selected_text:
        parts.append(ann.selected_text)
    if ann.note:
        parts.append(ann.note)
    source_md = "\n\n".join(parts)

    empty_response = {
        "pregenerated": False,
        "sanitized_text": "",
        "sentence_offsets_chars": [],
        "url": None,
        "duration_seconds": None,
        "voice": None,
        "sentence_offsets_seconds": None,
        "source_hash": None,
        "source_hash_stored": None,
        "source_hash_current": None,
        "sanitizer_version_stored": None,
        "sanitizer_version_current": SANITIZER_VERSION,
        "stale": None,
    }

    if not source_md.strip():
        return empty_response

    try:
        sanitized = sanitize(source_md)
    except EmptySanitizedTextError:
        return empty_response

    source_hash = hashlib.sha256(sanitized.text.encode("utf-8")).hexdigest()
    return {
        "pregenerated": False,
        "sanitized_text": sanitized.text,
        "sentence_offsets_chars": sanitized.sentence_offsets_chars,
        "url": None,
        "duration_seconds": None,
        "voice": None,
        "sentence_offsets_seconds": None,
        "source_hash": source_hash,
        "source_hash_stored": None,
        "source_hash_current": source_hash,
        "sanitizer_version_stored": None,
        "sanitizer_version_current": SANITIZER_VERSION,
        "stale": None,
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


# --- Batch lookups for the BookOverviewView (FR-C20, FR-E07a) ------------------


class AudioByBookEntry(BaseModel):
    section_id: int
    has_mp3: bool
    engine: str | None = None


class AudioByBookResponse(BaseModel):
    book_id: int
    sections: list[AudioByBookEntry]


class AudioPositionByBookResponse(BaseModel):
    content_type: str
    content_id: int
    sentence_index: int
    updated_at: str


@router.get("/api/v1/audio/sections/by-book/{book_id}", response_model=AudioByBookResponse)
async def get_audio_sections_by_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Batch audio-availability map for the Sections tab (FR-C20).

    Returns one entry per section, with `has_mp3` and the engine that generated
    the most recent MP3 (or null). Used by `useBookAudioMap` composable.
    """
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")

    sections = (
        (
            await db.execute(
                select(BookSection.id)
                .where(BookSection.book_id == book_id)
                .order_by(BookSection.order_index)
            )
        )
        .scalars()
        .all()
    )

    audio_rows = (
        await db.execute(
            select(AudioFile.content_id, AudioFile.engine).where(
                AudioFile.book_id == book_id,
                AudioFile.content_type.in_(
                    [ContentType.SECTION_SUMMARY.value, ContentType.SECTION_CONTENT.value]
                ),
            )
        )
    ).all()
    audio_by_id: dict[int, str] = {}
    for content_id, engine in audio_rows:
        # Latest write wins; rows are unique on (book, content_type, content_id, voice)
        # but multiple voices/types can collide on content_id. The first hit is fine
        # for the boolean availability check; engine is best-effort.
        audio_by_id.setdefault(content_id, engine)

    entries = [
        AudioByBookEntry(
            section_id=sid,
            has_mp3=sid in audio_by_id,
            engine=audio_by_id.get(sid),
        )
        for sid in sections
    ]
    return AudioByBookResponse(book_id=book_id, sections=entries)


@router.get(
    "/api/v1/audio/positions/by-book/{book_id}",
    response_model=AudioPositionByBookResponse,
)
async def get_audio_position_by_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Most-recent audio_position for any audio belonging to this book (FR-E07a).

    404 when no audio_position exists for any of the book's section-typed audio
    or its `book_summary` audio. `annotations_playlist` rows are excluded.
    """
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")

    from app.db.models import AudioPosition

    # Section-typed audio: join through book_sections.
    section_ids_subq = select(BookSection.id).where(BookSection.book_id == book_id)
    section_row = (
        await db.execute(
            select(AudioPosition)
            .where(
                AudioPosition.content_type.in_(
                    [ContentType.SECTION_SUMMARY.value, ContentType.SECTION_CONTENT.value]
                ),
                AudioPosition.content_id.in_(section_ids_subq),
            )
            .order_by(AudioPosition.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # book_summary audio: keyed directly on book id.
    book_summary_row = (
        await db.execute(
            select(AudioPosition)
            .where(
                AudioPosition.content_type == ContentType.BOOK_SUMMARY.value,
                AudioPosition.content_id == book_id,
            )
            .order_by(AudioPosition.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    candidates = [r for r in (section_row, book_summary_row) if r is not None]
    if not candidates:
        raise HTTPException(status_code=404, detail="no audio position for book")

    candidates.sort(key=lambda r: r.updated_at, reverse=True)
    winner = candidates[0]
    ct = winner.content_type.value if hasattr(winner.content_type, "value") else winner.content_type
    return AudioPositionByBookResponse(
        content_type=ct,
        content_id=winner.content_id,
        sentence_index=winner.sentence_index,
        updated_at=winner.updated_at.isoformat() if winner.updated_at else "",
    )
