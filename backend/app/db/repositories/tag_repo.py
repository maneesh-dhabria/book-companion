"""Tag and Taggable repository -- data access layer for polymorphic tagging."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tag, Taggable


class TagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, name: str, color: str | None = None) -> Tag:
        result = await self.session.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name, color=color)
            self.session.add(tag)
            await self.session.flush()
        elif color and tag.color != color:
            tag.color = color
            await self.session.flush()
        return tag

    async def get_by_name(self, name: str) -> Tag | None:
        result = await self.session.execute(select(Tag).where(Tag.name == name))
        return result.scalar_one_or_none()

    async def get_by_id(self, tag_id: int) -> Tag | None:
        result = await self.session.execute(select(Tag).where(Tag.id == tag_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Tag]:
        result = await self.session.execute(select(Tag).order_by(Tag.name))
        return list(result.scalars().all())

    async def delete_tag(self, tag_id: int) -> bool:
        result = await self.session.execute(delete(Tag).where(Tag.id == tag_id))
        await self.session.flush()
        return result.rowcount > 0

    async def add_taggable(
        self, tag_id: int, taggable_type: str, taggable_id: int
    ) -> Taggable:
        """Add a tag association to an entity (book, section, annotation)."""
        existing = await self.session.execute(
            select(Taggable).where(
                Taggable.tag_id == tag_id,
                Taggable.taggable_type == taggable_type,
                Taggable.taggable_id == taggable_id,
            )
        )
        taggable = existing.scalar_one_or_none()
        if taggable:
            return taggable
        taggable = Taggable(
            tag_id=tag_id,
            taggable_type=taggable_type,
            taggable_id=taggable_id,
        )
        self.session.add(taggable)
        await self.session.flush()
        return taggable

    async def remove_taggable(
        self, tag_id: int, taggable_type: str, taggable_id: int
    ) -> bool:
        result = await self.session.execute(
            delete(Taggable).where(
                Taggable.tag_id == tag_id,
                Taggable.taggable_type == taggable_type,
                Taggable.taggable_id == taggable_id,
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def get_tags_for_entity(
        self, taggable_type: str, taggable_id: int
    ) -> list[Tag]:
        result = await self.session.execute(
            select(Tag)
            .join(Taggable, Tag.id == Taggable.tag_id)
            .where(
                Taggable.taggable_type == taggable_type,
                Taggable.taggable_id == taggable_id,
            )
            .order_by(Tag.name)
        )
        return list(result.scalars().all())

    async def get_entities_by_tag(
        self, tag_name: str, taggable_type: str | None = None
    ) -> list[Taggable]:
        """Get all entities tagged with a given tag name."""
        query = (
            select(Taggable)
            .join(Tag, Tag.id == Taggable.tag_id)
            .where(Tag.name == tag_name)
        )
        if taggable_type:
            query = query.where(Taggable.taggable_type == taggable_type)
        result = await self.session.execute(query)
        return list(result.scalars().all())
