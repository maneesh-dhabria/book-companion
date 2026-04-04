"""Summary service — list, compare, set-default, concept diff."""

import re

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Summary, SummaryContentType
from app.db.repositories.book_repo import BookRepository
from app.db.repositories.section_repo import SectionRepository
from app.db.repositories.summary_repo import SummaryRepository
from app.exceptions import SummaryError

logger = structlog.get_logger()

BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
HEADER_PATTERN = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
NAMED_ENTITY_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


class SummaryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.summary_repo = SummaryRepository(session)
        self.book_repo = BookRepository(session)
        self.section_repo = SectionRepository(session)

    async def get_by_id(self, summary_id: int) -> Summary:
        summary = await self.summary_repo.get_by_id(summary_id)
        if not summary:
            raise SummaryError(f"Summary #{summary_id} not found.")
        return summary

    async def list_for_book(self, book_id: int) -> list[Summary]:
        return await self.summary_repo.list_by_book(book_id)

    async def list_for_content(
        self, content_type: SummaryContentType, content_id: int
    ) -> list[Summary]:
        return await self.summary_repo.list_by_content(content_type, content_id)

    async def list_book_level(self, book_id: int) -> list[Summary]:
        return await self.summary_repo.list_book_level(book_id)

    async def set_default(self, summary_id: int) -> Summary:
        summary = await self.get_by_id(summary_id)
        if summary.content_type == SummaryContentType.SECTION:
            section = await self.section_repo.get_by_id(summary.content_id)
            if not section:
                raise SummaryError(f"Section #{summary.content_id} not found.")
            await self.section_repo.update_default_summary(section.id, summary_id)
        elif summary.content_type == SummaryContentType.BOOK:
            book = await self.book_repo.get_by_id(summary.content_id)
            if not book:
                raise SummaryError(f"Book #{summary.content_id} not found.")
            await self.book_repo.update_default_summary(book.id, summary_id)
        else:
            raise SummaryError(f"Cannot set default for content_type={summary.content_type.value}")
        return summary

    @staticmethod
    def extract_concepts(text: str) -> set[str]:
        concepts = set()
        concepts.update(BOLD_PATTERN.findall(text))
        concepts.update(HEADER_PATTERN.findall(text))
        concepts.update(NAMED_ENTITY_PATTERN.findall(text))
        return concepts

    def concept_diff(self, summary_a: Summary, summary_b: Summary) -> dict[str, set[str]]:
        concepts_a = self.extract_concepts(summary_a.summary_md)
        concepts_b = self.extract_concepts(summary_b.summary_md)
        return {
            "only_in_a": concepts_a - concepts_b,
            "only_in_b": concepts_b - concepts_a,
            "shared": concepts_a & concepts_b,
        }

    async def get_last_used_preset(self, book_id: int) -> str | None:
        latest = await self.summary_repo.get_latest_for_book(book_id)
        return latest.preset_name if latest else None
