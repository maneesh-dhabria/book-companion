"""AudioFile repository — atomic UPSERT-with-unlink + inventory queries."""

from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudioFile, ContentType


def _path_for(book_id: int, content_type: ContentType, content_id: int, voice: str) -> str:
    return f"audio/{book_id}/{content_type.value}_{content_id}__{voice}.mp3"


class AudioFileRepository:
    def __init__(self, session: AsyncSession, data_dir: Path):
        self.session = session
        self.data_dir = Path(data_dir)

    async def upsert(
        self,
        *,
        book_id: int,
        content_type: ContentType,
        content_id: int,
        voice: str,
        engine: str,
        mp3_bytes: bytes,
        duration_seconds: float,
        sentence_count: int,
        sentence_offsets: list[float],
        source_hash: str,
        sanitizer_version: str,
        job_id: int | None = None,
    ) -> AudioFile:
        rel_path = _path_for(book_id, content_type, content_id, voice)
        abs_path = self.data_dir / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = abs_path.with_suffix(abs_path.suffix + ".tmp")
        with open(tmp_path, "wb") as f:
            f.write(mp3_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, abs_path)

        existing = await self._find(book_id, content_type, content_id, voice)
        old_rel = existing.file_path if existing else None
        if existing is not None:
            existing.engine = engine
            existing.file_path = rel_path
            existing.file_size_bytes = len(mp3_bytes)
            existing.duration_seconds = duration_seconds
            existing.sentence_count = sentence_count
            existing.sentence_offsets_json = json.dumps(sentence_offsets)
            existing.source_hash = source_hash
            existing.sanitizer_version = sanitizer_version
            existing.job_id = job_id
            row = existing
        else:
            row = AudioFile(
                book_id=book_id,
                content_type=content_type,
                content_id=content_id,
                voice=voice,
                engine=engine,
                file_path=rel_path,
                file_size_bytes=len(mp3_bytes),
                duration_seconds=duration_seconds,
                sentence_count=sentence_count,
                sentence_offsets_json=json.dumps(sentence_offsets),
                source_hash=source_hash,
                sanitizer_version=sanitizer_version,
                job_id=job_id,
            )
            self.session.add(row)
        await self.session.flush()

        if old_rel and old_rel != rel_path:
            old_abs = self.data_dir / old_rel
            try:
                old_abs.unlink()
            except FileNotFoundError:
                pass

        return row

    async def _find(
        self,
        book_id: int,
        content_type: ContentType,
        content_id: int,
        voice: str,
    ) -> AudioFile | None:
        result = await self.session.execute(
            select(AudioFile).where(
                AudioFile.book_id == book_id,
                AudioFile.content_type == content_type,
                AudioFile.content_id == content_id,
                AudioFile.voice == voice,
            )
        )
        return result.scalar_one_or_none()

    async def lookup(
        self,
        *,
        book_id: int,
        content_type: ContentType,
        content_id: int,
        voice: str,
    ) -> AudioFile | None:
        return await self._find(book_id, content_type, content_id, voice)

    async def list_by_book(self, book_id: int) -> list[AudioFile]:
        result = await self.session.execute(
            select(AudioFile)
            .where(AudioFile.book_id == book_id)
            .order_by(AudioFile.content_type, AudioFile.content_id)
        )
        return list(result.scalars().all())

    async def delete_one(
        self,
        *,
        book_id: int,
        content_type: ContentType,
        content_id: int,
        voice: str | None = None,
    ) -> int:
        rows = await self.session.execute(
            select(AudioFile).where(
                AudioFile.book_id == book_id,
                AudioFile.content_type == content_type,
                AudioFile.content_id == content_id,
                *((AudioFile.voice == voice,) if voice is not None else ()),
            )
        )
        targets = list(rows.scalars().all())
        for r in targets:
            self._unlink_file(r.file_path)
            await self.session.delete(r)
        await self.session.flush()
        return len(targets)

    async def delete_all_for_book(self, book_id: int) -> int:
        rows = await self.session.execute(
            select(AudioFile).where(AudioFile.book_id == book_id)
        )
        targets = list(rows.scalars().all())
        for r in targets:
            self._unlink_file(r.file_path)
        if targets:
            await self.session.execute(
                delete(AudioFile).where(AudioFile.book_id == book_id)
            )
            await self.session.flush()
        return len(targets)

    async def delete_orphans(self, book_id: int, surviving_section_ids: set[int]) -> int:
        rows = await self.session.execute(
            select(AudioFile).where(
                AudioFile.book_id == book_id,
                AudioFile.content_type == ContentType.SECTION_SUMMARY,
            )
        )
        deleted = 0
        for r in rows.scalars().all():
            if r.content_id not in surviving_section_ids:
                self._unlink_file(r.file_path)
                await self.session.delete(r)
                deleted += 1
        if deleted:
            await self.session.flush()
        return deleted

    def _unlink_file(self, rel_path: str) -> None:
        try:
            (self.data_dir / rel_path).unlink()
        except FileNotFoundError:
            pass
