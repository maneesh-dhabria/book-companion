"""Annotation service -- business logic for annotations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Annotation,
    AnnotationType,
    Book,
    BookSection,
    ContentType,
)
from app.db.repositories.annotation_repo import AnnotationRepository
from app.db.repositories.tag_repo import TagRepository
from app.exceptions import BookCompanionError


class AnnotationError(BookCompanionError):
    """Annotation-related errors."""


class AnnotationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AnnotationRepository(session)
        self.tag_repo = TagRepository(session)

    async def create_annotation(
        self,
        content_type: ContentType,
        content_id: int,
        selected_text: str | None = None,
        note: str | None = None,
        annotation_type: AnnotationType = AnnotationType.NOTE,
        text_start: int | None = None,
        text_end: int | None = None,
        linked_annotation_id: int | None = None,
        tag_name: str | None = None,
    ) -> Annotation:
        """Create an annotation with optional tag and cross-book linking."""
        # Validate content reference exists
        await self._validate_content_reference(content_type, content_id)

        # Validate linked annotation exists if provided
        if linked_annotation_id:
            linked = await self.repo.get_by_id(linked_annotation_id)
            if not linked:
                raise AnnotationError(f"Linked annotation {linked_annotation_id} not found.")

        annotation = Annotation(
            content_type=content_type,
            content_id=content_id,
            selected_text=selected_text,
            note=note,
            type=annotation_type,
            text_start=text_start,
            text_end=text_end,
            linked_annotation_id=linked_annotation_id,
        )
        annotation = await self.repo.create(annotation)

        # Add tag if provided
        if tag_name:
            tag = await self.tag_repo.get_or_create(tag_name)
            await self.tag_repo.add_taggable(tag.id, "annotation", annotation.id)

        return annotation

    async def list_annotations(
        self,
        book_id: int | None = None,
        tag: str | None = None,
        annotation_type: AnnotationType | None = None,
    ) -> list[Annotation]:
        """List annotations filtered by book, tag, or type."""
        if tag:
            return await self.repo.list_by_tag(tag)
        if book_id:
            return await self.repo.list_by_book(book_id, annotation_type)
        return []

    async def link_annotations(self, annotation_id: int, linked_annotation_id: int) -> Annotation:
        """Link two annotations for cross-book referencing."""
        annotation = await self.repo.get_by_id(annotation_id)
        if not annotation:
            raise AnnotationError(f"Annotation {annotation_id} not found.")

        linked = await self.repo.get_by_id(linked_annotation_id)
        if not linked:
            raise AnnotationError(f"Linked annotation {linked_annotation_id} not found.")

        result = await self.repo.link_annotations(annotation_id, linked_annotation_id)
        if not result:
            raise AnnotationError("Failed to link annotations.")
        return result

    async def get_annotation(self, annotation_id: int) -> Annotation | None:
        return await self.repo.get_by_id(annotation_id)

    async def delete_annotation(self, annotation_id: int) -> bool:
        return await self.repo.delete(annotation_id)

    async def _validate_content_reference(self, content_type: ContentType, content_id: int) -> None:
        """Validate that the referenced content actually exists."""
        from sqlalchemy import select

        if content_type in (ContentType.SECTION_CONTENT, ContentType.SECTION_SUMMARY):
            result = await self.session.execute(
                select(BookSection).where(BookSection.id == content_id)
            )
            if not result.scalar_one_or_none():
                raise AnnotationError(
                    f"Section {content_id} not found for content_type={content_type.value}."
                )
        elif content_type == ContentType.BOOK_SUMMARY:
            result = await self.session.execute(select(Book).where(Book.id == content_id))
            if not result.scalar_one_or_none():
                raise AnnotationError(
                    f"Book {content_id} not found for content_type={content_type.value}."
                )
