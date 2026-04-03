"""Concept service -- business logic for concept index browsing and editing."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Concept
from app.db.repositories.concept_repo import ConceptRepository
from app.exceptions import BookCompanionError


class ConceptError(BookCompanionError):
    """Concept-related errors."""


class ConceptService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConceptRepository(session)

    async def list_by_book(self, book_id: int) -> list[Concept]:
        """Return sorted concept index for a book."""
        return await self.repo.get_by_book(book_id)

    async def search(self, term: str) -> list[Concept]:
        """Search concepts across all books by term (case-insensitive partial match)."""
        if not term or not term.strip():
            raise ConceptError("Search term cannot be empty.")
        return await self.repo.search_across_books(term.strip())

    async def get_concept(self, concept_id: int) -> Concept | None:
        return await self.repo.get_by_id(concept_id)

    async def edit(self, concept_id: int, definition: str) -> Concept:
        """Edit a concept definition and mark as user_edited."""
        concept = await self.repo.update_definition(concept_id, definition, user_edited=True)
        if not concept:
            raise ConceptError(f"Concept {concept_id} not found.")
        return concept

    async def get_by_term(self, book_id: int, term: str) -> Concept | None:
        return await self.repo.get_by_term(book_id, term)

    async def bulk_update_definitions(self, updates: list[dict]) -> list[Concept]:
        """Bulk update concept definitions from $EDITOR output.

        Each dict should have: {"id": int, "definition": str}
        """
        results = []
        for item in updates:
            concept = await self.repo.update_definition(
                item["id"], item["definition"], user_edited=True
            )
            if concept:
                results.append(concept)
        return results
