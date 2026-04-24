"""Tag service -- business logic for polymorphic tagging."""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tag, Taggable
from app.db.repositories.tag_repo import TagRepository
from app.exceptions import BookCompanionError

VALID_TAGGABLE_TYPES = {"book", "section", "annotation"}

_WS = re.compile(r"\s+")


def normalize_tag_name(name: str) -> str:
    """Trim leading/trailing whitespace and collapse internal whitespace.

    Raises ``ValueError`` when the resulting name is empty — callers should
    treat this as a 422 / CLI validation error, not a tag mutation.
    """
    if name is None:
        raise ValueError("tag name cannot be empty")
    cleaned = _WS.sub(" ", name).strip()
    if not cleaned:
        raise ValueError("tag name cannot be empty")
    return cleaned


class TagError(BookCompanionError):
    """Tag-related errors."""


class TagService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TagRepository(session)

    async def add_tag(
        self,
        taggable_type: str,
        taggable_id: int,
        tag_name: str,
        color: str | None = None,
    ) -> Tag:
        """Add a tag to an entity (book, section, or annotation).

        Idempotent per FR-E2.5: retrying the same (taggable, name) is a no-op
        on the association row but still returns the Tag. Name is normalised
        (whitespace-collapse + trim) and rejected if empty.
        """
        if taggable_type not in VALID_TAGGABLE_TYPES:
            raise TagError(
                f"Invalid taggable_type '{taggable_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_TAGGABLE_TYPES))}"
            )
        try:
            tag_name = normalize_tag_name(tag_name)
        except ValueError as e:
            raise TagError(str(e)) from e
        await self._validate_entity_exists(taggable_type, taggable_id)

        tag = await self.repo.get_or_create(tag_name, color=color)
        await self.repo.add_taggable(tag.id, taggable_type, taggable_id)
        return tag

    async def remove_tag(self, taggable_type: str, taggable_id: int, tag_name: str) -> bool:
        try:
            tag_name = normalize_tag_name(tag_name)
        except ValueError:
            return False
        tag = await self.repo.get_by_name(tag_name)
        if not tag:
            return False
        return await self.repo.remove_taggable(tag.id, taggable_type, taggable_id)

    async def list_tags(self) -> list[Tag]:
        """List all tags in the system."""
        return await self.repo.list_all()

    async def list_tags_for_entity(self, taggable_type: str, taggable_id: int) -> list[Tag]:
        return await self.repo.get_tags_for_entity(taggable_type, taggable_id)

    async def list_by_tag(self, tag_name: str, taggable_type: str | None = None) -> list[Taggable]:
        """Get all entities tagged with a specific tag name."""
        return await self.repo.get_entities_by_tag(tag_name, taggable_type)

    async def _validate_entity_exists(self, taggable_type: str, taggable_id: int) -> None:
        """Validate that the entity being tagged exists in the database."""
        from sqlalchemy import select

        from app.db.models import Annotation, Book, BookSection

        model_map = {
            "book": Book,
            "section": BookSection,
            "annotation": Annotation,
        }
        model = model_map.get(taggable_type)
        if not model:
            return
        result = await self.session.execute(select(model).where(model.id == taggable_id))
        if not result.scalar_one_or_none():
            raise TagError(f"{taggable_type.title()} {taggable_id} not found.")
