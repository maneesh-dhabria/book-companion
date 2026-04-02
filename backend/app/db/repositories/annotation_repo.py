"""Annotation repository -- data access layer."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Annotation, AnnotationType, ContentType


class AnnotationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, annotation: Annotation) -> Annotation:
        self.session.add(annotation)
        await self.session.flush()
        return annotation

    async def get_by_id(self, annotation_id: int) -> Annotation | None:
        result = await self.session.execute(
            select(Annotation).where(Annotation.id == annotation_id)
        )
        return result.scalar_one_or_none()

    async def list_by_content(
        self,
        content_type: ContentType,
        content_id: int,
        annotation_type: AnnotationType | None = None,
    ) -> list[Annotation]:
        query = select(Annotation).where(
            Annotation.content_type == content_type,
            Annotation.content_id == content_id,
        )
        if annotation_type:
            query = query.where(Annotation.type == annotation_type)
        query = query.order_by(Annotation.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_book(
        self,
        book_id: int,
        annotation_type: AnnotationType | None = None,
    ) -> list[Annotation]:
        """List annotations for a book by joining through book_sections."""
        from app.db.models import BookSection

        query = (
            select(Annotation)
            .join(
                BookSection,
                BookSection.id == Annotation.content_id,
            )
            .where(BookSection.book_id == book_id)
        )
        if annotation_type:
            query = query.where(Annotation.type == annotation_type)
        query = query.order_by(Annotation.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_tag(self, tag_name: str) -> list[Annotation]:
        """List annotations that have a specific tag via taggable association."""
        from app.db.models import Tag, Taggable

        query = (
            select(Annotation)
            .join(
                Taggable,
                (Taggable.taggable_type == "annotation")
                & (Taggable.taggable_id == Annotation.id),
            )
            .join(Tag, Tag.id == Taggable.tag_id)
            .where(Tag.name == tag_name)
            .order_by(Annotation.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, annotation: Annotation) -> Annotation:
        await self.session.flush()
        return annotation

    async def delete(self, annotation_id: int) -> bool:
        result = await self.session.execute(
            delete(Annotation).where(Annotation.id == annotation_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def link_annotations(
        self, annotation_id: int, linked_annotation_id: int
    ) -> Annotation | None:
        annotation = await self.get_by_id(annotation_id)
        if annotation:
            annotation.linked_annotation_id = linked_annotation_id
            await self.session.flush()
        return annotation
