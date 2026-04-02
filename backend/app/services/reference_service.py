"""External reference discovery service -- LLM-powered discovery of summaries/reviews."""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book, ExternalReference
from app.db.repositories.book_repo import BookRepository
from app.exceptions import BookCompanionError

logger = logging.getLogger(__name__)


class ReferenceError(BookCompanionError):
    """Reference discovery errors."""


class ReferenceService:
    def __init__(self, session: AsyncSession, llm_service=None):
        self.session = session
        self.book_repo = BookRepository(session)
        self.llm = llm_service

    async def discover_references(self, book_id: int) -> list[ExternalReference]:
        """Use LLM with web search to find 4-5 external summaries/reviews.

        Stores discovered references in the external_references table.
        """
        book = await self.book_repo.get_by_id(book_id)
        if not book:
            raise ReferenceError(f"Book {book_id} not found.")

        authors = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"

        prompt = self._build_discovery_prompt(book.title, authors)

        if not self.llm:
            raise ReferenceError(
                "LLM service not configured. Cannot discover references."
            )

        try:
            response = await self.llm.generate(prompt=prompt)
            references_data = self._parse_references_response(response.content)
        except Exception as e:
            logger.error("Reference discovery failed for book %d: %s", book_id, e)
            raise ReferenceError(f"Reference discovery failed: {e}")

        # Store references
        created_refs = []
        for ref_data in references_data:
            ref = ExternalReference(
                book_id=book_id,
                url=ref_data.get("url", ""),
                title=ref_data.get("title", "Unknown"),
                source_name=ref_data.get("source_name", "Unknown"),
                snippet=ref_data.get("snippet"),
                quality_notes=ref_data.get("quality_notes"),
            )
            self.session.add(ref)
            created_refs.append(ref)

        await self.session.flush()
        return created_refs

    async def list_references(self, book_id: int) -> list[ExternalReference]:
        """Return stored external references for a book."""
        result = await self.session.execute(
            select(ExternalReference)
            .where(ExternalReference.book_id == book_id)
            .order_by(ExternalReference.discovered_at.desc())
        )
        return list(result.scalars().all())

    def _build_discovery_prompt(self, title: str, authors: str) -> str:
        """Build the prompt for external reference discovery."""
        return f"""Find 4-5 high-quality external summaries, reviews, or analyses of the book "{title}" by {authors}.

For each reference, provide:
- url: The full URL
- title: The title of the article/review
- source_name: The website or publication name
- snippet: A 1-2 sentence description of what the reference covers
- quality_notes: Brief note on why this reference is valuable

Return the results as a JSON array. Example format:
[
  {{
    "url": "https://example.com/review",
    "title": "Review of {title}",
    "source_name": "Example Blog",
    "snippet": "A thorough chapter-by-chapter analysis...",
    "quality_notes": "Well-researched academic review"
  }}
]

Prioritize:
1. Detailed chapter-by-chapter summaries
2. Academic reviews or analyses
3. Well-known book review sites (e.g., Brain Pickings, Farnam Street, The Marginalian)
4. Author interviews about the book

Return ONLY the JSON array, no other text."""

    def _parse_references_response(self, response_text: str) -> list[dict]:
        """Parse the LLM response into a list of reference dicts."""
        try:
            # Try to extract JSON from response
            text = response_text.strip()
            # Handle case where response is wrapped in markdown code block
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
            data = json.loads(text)
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            logger.warning("Failed to parse reference discovery response as JSON")
            return []
