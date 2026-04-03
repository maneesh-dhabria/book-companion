"""Concept and ConceptSection repository — data access layer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Concept, ConceptSection


class ConceptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bulk(self, concepts: list[Concept]) -> list[Concept]:
        self.session.add_all(concepts)
        await self.session.flush()
        return concepts

    async def get_by_book(self, book_id: int) -> list[Concept]:
        result = await self.session.execute(
            select(Concept).where(Concept.book_id == book_id).order_by(Concept.term)
        )
        return list(result.scalars().all())

    async def search_across_books(self, term: str) -> list[Concept]:
        result = await self.session.execute(
            select(Concept).where(Concept.term.ilike(f"%{term}%")).order_by(Concept.term)
        )
        return list(result.scalars().all())

    async def update(self, concept_id: int, **kwargs) -> Concept | None:
        result = await self.session.execute(select(Concept).where(Concept.id == concept_id))
        concept = result.scalar_one_or_none()
        if concept:
            for key, value in kwargs.items():
                if hasattr(concept, key):
                    setattr(concept, key, value)
            await self.session.flush()
        return concept

    async def get_by_id(self, concept_id: int) -> Concept | None:
        result = await self.session.execute(select(Concept).where(Concept.id == concept_id))
        return result.scalar_one_or_none()

    async def get_by_term(self, book_id: int, term: str) -> Concept | None:
        result = await self.session.execute(
            select(Concept).where(Concept.book_id == book_id, Concept.term == term)
        )
        return result.scalar_one_or_none()

    async def update_definition(
        self,
        concept_id: int,
        definition: str,
        user_edited: bool = True,
    ) -> Concept | None:
        concept = await self.get_by_id(concept_id)
        if concept:
            concept.definition = definition
            concept.user_edited = user_edited
            await self.session.flush()
        return concept

    async def link_section(self, concept_id: int, section_id: int) -> None:
        existing = await self.session.execute(
            select(ConceptSection).where(
                ConceptSection.concept_id == concept_id,
                ConceptSection.section_id == section_id,
            )
        )
        if not existing.scalar_one_or_none():
            link = ConceptSection(concept_id=concept_id, section_id=section_id)
            self.session.add(link)
            await self.session.flush()

    async def get_sections_for_concept(self, concept_id: int) -> list[int]:
        result = await self.session.execute(
            select(ConceptSection.section_id).where(ConceptSection.concept_id == concept_id)
        )
        return list(result.scalars().all())
