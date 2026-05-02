"""AudioGenService — sanitize → synthesize → tag → atomic-write → UPSERT.

Single orchestrator used by:
- `JobQueueWorker` for `step=AUDIO` (generate per unit, emit SSE)
- `GET /audio/lookup` (compute stale-ness vs current source)
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudioFile, ContentType
from app.db.repositories.audio_file_repo import AudioFileRepository
from app.services.tts.id3_tagger import tag_mp3
from app.services.tts.markdown_to_speech import (
    SANITIZER_VERSION,
    EmptySanitizedTextError,
    sanitize,
)
from app.services.tts.provider import TTSProvider


@dataclass
class LookupResult:
    pregenerated: bool
    sanitized_text: str
    sentence_offsets_chars: list[int]
    url: str | None = None
    duration_seconds: float | None = None
    voice: str | None = None
    sentence_offsets_seconds: list[float] | None = None
    source_hash_stored: str | None = None
    source_hash_current: str | None = None
    sanitizer_version_stored: str | None = None
    sanitizer_version_current: str | None = None
    stale: bool = False
    stale_reason: str | None = None


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_by_offsets(text: str, offsets: list[int]) -> list[str]:
    out: list[str] = []
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < len(offsets) else len(text)
        out.append(text[start:end].strip())
    return [s for s in out if s]


class AudioGenService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        audio_repo: AudioFileRepository,
        tts_provider: TTSProvider,
        data_dir: Path,
        book_title: str = "Book Companion",
        book_artist: str = "Book Companion",
    ) -> None:
        self.session = session
        self.repo = audio_repo
        self.tts = tts_provider
        self.data_dir = Path(data_dir)
        self._title = book_title
        self._artist = book_artist

    async def generate_unit(
        self,
        *,
        book_id: int,
        content_type: ContentType,
        content_id: int,
        voice: str,
        source_md: str,
        job_id: int | None,
        track_n: int = 1,
        track_total: int = 1,
        title: str | None = None,
        album: str | None = None,
        artist: str | None = None,
        cover_jpg: bytes | None = None,
    ) -> AudioFile:
        sanitized = sanitize(source_md)
        sentences = _split_by_offsets(sanitized.text, sanitized.sentence_offsets_chars)
        if not sentences:
            raise EmptySanitizedTextError("no sentences after sanitization")

        result = self.tts.synthesize_segmented(sentences, voice=voice, speed=1.0)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(result.audio_bytes)
            tmp_path = tmp.name
        try:
            tag_mp3(
                tmp_path,
                title=title or f"{content_type.value} {content_id}",
                artist=artist or self._artist,
                album=album or self._title,
                track_n=track_n,
                track_total=track_total,
                cover_jpg=cover_jpg,
            )
            tagged_bytes = Path(tmp_path).read_bytes()
        finally:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass

        return await self.repo.upsert(
            book_id=book_id,
            content_type=content_type,
            content_id=content_id,
            voice=voice,
            engine=self.tts.name,
            mp3_bytes=tagged_bytes,
            duration_seconds=result.duration_seconds,
            sentence_count=len(sentences),
            sentence_offsets=result.sentence_offsets,
            source_hash=_hash_text(sanitized.text),
            sanitizer_version=SANITIZER_VERSION,
            job_id=job_id,
        )

    async def lookup(
        self,
        *,
        book_id: int,
        content_type: ContentType,
        content_id: int,
        voice: str,
        current_source_md: str,
    ) -> LookupResult:
        try:
            sanitized_current = sanitize(current_source_md)
        except EmptySanitizedTextError:
            return LookupResult(
                pregenerated=False,
                sanitized_text="",
                sentence_offsets_chars=[],
            )

        current_hash = _hash_text(sanitized_current.text)
        current_sentences = len(sanitized_current.sentence_offsets_chars)

        af = await self.repo.lookup(
            book_id=book_id,
            content_type=content_type,
            content_id=content_id,
            voice=voice,
        )
        if af is None:
            return LookupResult(
                pregenerated=False,
                sanitized_text=sanitized_current.text,
                sentence_offsets_chars=sanitized_current.sentence_offsets_chars,
                source_hash_current=current_hash,
                sanitizer_version_current=SANITIZER_VERSION,
            )

        # Stale detection (FR-12a precedence): source_changed > sanitizer_upgraded > segmenter_drift
        stale = False
        reason: str | None = None
        if af.source_hash != current_hash:
            stale, reason = True, "source_changed"
        elif af.sanitizer_version != SANITIZER_VERSION:
            stale, reason = True, "sanitizer_upgraded"
        elif af.sentence_count != current_sentences:
            stale, reason = True, "segmenter_drift"

        import json as _json

        offsets_seconds = _json.loads(af.sentence_offsets_json)
        url = f"/api/v1/books/{book_id}/audio/{content_type.value}/{content_id}.mp3"
        return LookupResult(
            pregenerated=True,
            sanitized_text=sanitized_current.text,
            sentence_offsets_chars=sanitized_current.sentence_offsets_chars,
            url=url,
            duration_seconds=af.duration_seconds,
            voice=af.voice,
            sentence_offsets_seconds=offsets_seconds,
            source_hash_stored=af.source_hash,
            source_hash_current=current_hash,
            sanitizer_version_stored=af.sanitizer_version,
            sanitizer_version_current=SANITIZER_VERSION,
            stale=stale,
            stale_reason=reason,
        )
