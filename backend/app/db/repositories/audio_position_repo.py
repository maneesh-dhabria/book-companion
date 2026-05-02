"""AudioPosition repository — debounced UPSERT + cross-browser hint."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudioPosition, BookSection, ContentType, Summary

DEBOUNCE_SECONDS = 0.5


@dataclass
class PositionWithHint:
    sentence_index: int
    updated_at: datetime
    has_other_browser: bool
    other_browser_updated_at: datetime | None


class AudioPositionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._last_write: dict[tuple[str, int, str], float] = {}

    async def upsert(
        self,
        content_type: ContentType,
        content_id: int,
        browser_id: str,
        sentence_index: int,
    ) -> bool:
        """Returns True if the write landed, False if debounced."""
        ct_value = content_type.value if isinstance(content_type, ContentType) else content_type
        key = (ct_value, content_id, browser_id)
        now = time.monotonic()
        last = self._last_write.get(key)
        if last is not None and (now - last) < DEBOUNCE_SECONDS:
            return False
        self._last_write[key] = now

        existing = await self.session.get(AudioPosition, (content_type, content_id, browser_id))
        if existing is not None:
            existing.sentence_index = sentence_index
            existing.updated_at = datetime.now(UTC)
        else:
            self.session.add(
                AudioPosition(
                    content_type=content_type,
                    content_id=content_id,
                    browser_id=browser_id,
                    sentence_index=sentence_index,
                )
            )
        await self.session.flush()
        return True

    async def get(
        self, content_type: ContentType, content_id: int, browser_id: str
    ) -> AudioPosition | None:
        return await self.session.get(AudioPosition, (content_type, content_id, browser_id))

    async def get_with_hint(
        self, content_type: ContentType, content_id: int, browser_id: str
    ) -> PositionWithHint | None:
        row = await self.get(content_type, content_id, browser_id)
        if row is None:
            return None
        latest_other = await self.session.execute(
            select(func.max(AudioPosition.updated_at)).where(
                AudioPosition.content_type == content_type,
                AudioPosition.content_id == content_id,
                AudioPosition.browser_id != browser_id,
            )
        )
        other_at = latest_other.scalar_one_or_none()
        return PositionWithHint(
            sentence_index=row.sentence_index,
            updated_at=row.updated_at,
            has_other_browser=other_at is not None,
            other_browser_updated_at=other_at,
        )

    async def cleanup_for_book(self, book_id: int) -> int:
        """Delete audio_positions tied to a book (FR-26b)."""
        section_subq = select(BookSection.id).where(BookSection.book_id == book_id)
        summary_subq = select(Summary.id).where(Summary.book_id == book_id)

        sec_summary_q = delete(AudioPosition).where(
            AudioPosition.content_type == ContentType.SECTION_SUMMARY,
            AudioPosition.content_id.in_(section_subq),
        )
        sec_content_q = delete(AudioPosition).where(
            AudioPosition.content_type == ContentType.SECTION_CONTENT,
            AudioPosition.content_id.in_(section_subq),
        )
        book_summary_q = delete(AudioPosition).where(
            AudioPosition.content_type == ContentType.BOOK_SUMMARY,
            AudioPosition.content_id.in_(summary_subq),
        )
        playlist_q = delete(AudioPosition).where(
            AudioPosition.content_type == ContentType.ANNOTATIONS_PLAYLIST,
            AudioPosition.content_id == book_id,
        )

        deleted = 0
        for stmt in (sec_summary_q, sec_content_q, book_summary_q, playlist_q):
            result = await self.session.execute(stmt)
            deleted += result.rowcount or 0
        await self.session.flush()
        return deleted
