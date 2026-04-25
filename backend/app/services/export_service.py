"""Export service -- JSON and Markdown export for books and library."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Annotation,
    Book,
    BookSection,
    Concept,
    ContentType,
    ExternalReference,
)
from app.db.repositories.book_repo import BookRepository
from app.db.repositories.summary_repo import SummaryRepository
from app.exceptions import BookCompanionError


class ExportError(BookCompanionError):
    """Export-related errors."""


_MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(/api/v1/images/\d+(?:\s+"[^"]*")?\)')
_HTML_IMG_RE = re.compile(
    r'<img\s+[^>]*src=["\']/api/v1/images/\d+["\'][^>]*?>',
    re.IGNORECASE,
)
_ALT_ATTR_RE = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)


def _sanitize_image_urls(text: str) -> str:
    """Replace in-app image references with portable [Image: alt] placeholders.

    Targets two patterns (per spec FR-B5):
      1. Markdown image: ![alt](/api/v1/images/{id}) optionally with " title"
      2. HTML <img src="/api/v1/images/{id}" alt="...">
    """

    def _md_repl(m: re.Match) -> str:
        alt = (m.group(1) or "").strip()
        return f"[Image: {alt}]" if alt else "[Image]"

    def _html_repl(m: re.Match) -> str:
        alt_match = _ALT_ATTR_RE.search(m.group(0))
        alt = alt_match.group(1).strip() if alt_match else ""
        return f"[Image: {alt}]" if alt else "[Image]"

    out = _MD_IMG_RE.sub(_md_repl, text)
    out = _HTML_IMG_RE.sub(_html_repl, out)
    return out


@dataclass(frozen=True)
class ExportSelection:
    """Immutable selection passed to the markdown renderer."""

    include_book_summary: bool = True
    include_toc: bool = True
    include_annotations: bool = True
    exclude_section_ids: frozenset[int] = field(default_factory=frozenset)


class ExportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.book_repo = BookRepository(session)
        self.summary_repo = SummaryRepository(session)

    async def export_book(
        self, book_id: int, fmt: str = "json", output_path: str | None = None
    ) -> str:
        """Export a single book's data in the specified format."""
        book = await self.book_repo.get_by_id(book_id)
        if not book:
            raise ExportError(f"Book {book_id} not found.")

        book_data = await self._collect_book_data(book)

        if fmt == "json":
            content = self._render_json([book_data])
        elif fmt == "markdown":
            content = self._render_markdown([book_data])
        else:
            raise ExportError(f"Unsupported format: {fmt}. Use 'json' or 'markdown'.")

        if output_path:
            Path(output_path).write_text(content, encoding="utf-8")

        return content

    async def export_library(self, fmt: str = "json", output_path: str | None = None) -> str:
        """Export the entire library in the specified format."""
        books = await self.book_repo.list_all()
        all_data = []
        for book in books:
            book_data = await self._collect_book_data(book)
            all_data.append(book_data)

        if fmt == "json":
            content = self._render_json(all_data)
        elif fmt == "markdown":
            content = self._render_markdown(all_data)
        else:
            raise ExportError(f"Unsupported format: {fmt}. Use 'json' or 'markdown'.")

        if output_path:
            Path(output_path).write_text(content, encoding="utf-8")

        return content

    async def _collect_book_annotations(self, book: Book) -> list[dict]:
        """Load annotations whose content_type=BOOK_SUMMARY and content_id=book.id.

        Sibling to _collect_book_data. Kept separate so JSON export remains
        byte-identical (FR-B3); the markdown render path is the only consumer.
        """
        result = await self.session.execute(
            select(Annotation).where(
                Annotation.content_type == ContentType.BOOK_SUMMARY,
                Annotation.content_id == book.id,
            )
        )
        anns = list(result.scalars().all())
        return [
            {
                "id": a.id,
                "selected_text": a.selected_text or "",
                "note": a.note or "",
                "type": a.type.value if a.type else None,
            }
            for a in anns
        ]

    async def _collect_book_data(self, book: Book) -> dict:
        """Collect all data for a book into a serializable dict."""
        # Sections
        sections_result = await self.session.execute(
            select(BookSection)
            .where(BookSection.book_id == book.id)
            .order_by(BookSection.order_index)
        )
        sections = list(sections_result.scalars().all())

        # Concepts
        concepts_result = await self.session.execute(
            select(Concept).where(Concept.book_id == book.id).order_by(Concept.term)
        )
        concepts = list(concepts_result.scalars().all())

        # External references
        refs_result = await self.session.execute(
            select(ExternalReference).where(ExternalReference.book_id == book.id)
        )
        refs = list(refs_result.scalars().all())

        # Annotations (via sections)
        section_ids = [s.id for s in sections]
        annotations = []
        if section_ids:
            ann_result = await self.session.execute(
                select(Annotation).where(Annotation.content_id.in_(section_ids))
            )
            annotations = list(ann_result.scalars().all())

        authors = [a.name for a in book.authors] if book.authors else []

        # Load book-level summary from Summary table
        book_summary_md = None
        if book.default_summary_id:
            book_summary = await self.summary_repo.get_by_id(book.default_summary_id)
            if book_summary:
                book_summary_md = book_summary.summary_md
        if not book_summary_md:
            book_summary_md = book.quick_summary

        # Load section summaries
        section_data = []
        for s in sections:
            section_summary_md = None
            if s.default_summary_id:
                sec_summary = await self.summary_repo.get_by_id(s.default_summary_id)
                if sec_summary:
                    section_summary_md = sec_summary.summary_md
            section_data.append(
                {
                    "id": s.id,
                    "title": s.title,
                    "order_index": s.order_index,
                    "depth": s.depth,
                    "has_summary": s.default_summary_id is not None,
                    "summary_md": section_summary_md,
                }
            )

        return {
            "id": book.id,
            "title": book.title,
            "authors": authors,
            "status": book.status.value if book.status else None,
            "quick_summary": book_summary_md,
            "created_at": book.created_at.isoformat() if book.created_at else None,
            "sections": section_data,
            "concepts": [
                {
                    "id": c.id,
                    "term": c.term,
                    "definition": c.definition,
                    "user_edited": c.user_edited,
                }
                for c in concepts
            ],
            "annotations": [
                {
                    "id": a.id,
                    "content_type": a.content_type.value if a.content_type else None,
                    "content_id": a.content_id,
                    "selected_text": a.selected_text,
                    "note": a.note,
                    "type": a.type.value if a.type else None,
                }
                for a in annotations
            ],
            "external_references": [
                {
                    "id": r.id,
                    "url": r.url,
                    "title": r.title,
                    "source_name": r.source_name,
                    "snippet": r.snippet,
                }
                for r in refs
            ],
        }

    def _render_json(self, books_data: list[dict]) -> str:
        """Render book data as formatted JSON."""

        def _default(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)

        return json.dumps(
            {"library": books_data, "exported_at": datetime.now().isoformat()},
            indent=2,
            default=_default,
            ensure_ascii=False,
        )

    def _render_markdown(self, books_data: list[dict]) -> str:
        """Render book data as a readable Markdown document."""
        lines = ["# Book Companion Library Export", ""]

        for book in books_data:
            authors_str = ", ".join(book["authors"]) if book["authors"] else "Unknown"
            lines.append(f"## {book['title']}")
            lines.append(f"**Author(s):** {authors_str}  ")
            lines.append(f"**Status:** {book.get('status', 'unknown')}  ")
            lines.append("")

            # Book summary
            if book.get("quick_summary"):
                lines.append("### Quick Summary")
                lines.append(book["quick_summary"])
                lines.append("")

            # Sections
            if book.get("sections"):
                lines.append("### Sections")
                lines.append("")
                for section in book["sections"]:
                    indent = "  " * section.get("depth", 0)
                    status = "summarized" if section.get("has_summary") else "pending"
                    lines.append(f"{indent}- **{section['title']}** ({status})")
                    if section.get("summary_md"):
                        for line in section["summary_md"].split("\n"):
                            lines.append(f"{indent}  {line}")
                lines.append("")

            # Concepts
            if book.get("concepts"):
                lines.append("### Concepts Index")
                lines.append("")
                for concept in book["concepts"]:
                    edited = " (user edited)" if concept.get("user_edited") else ""
                    lines.append(f"- **{concept['term']}**{edited}: {concept['definition']}")
                lines.append("")

            # Annotations
            if book.get("annotations"):
                lines.append("### Annotations")
                lines.append("")
                for ann in book["annotations"]:
                    ann_type = ann.get("type", "note")
                    if ann.get("selected_text"):
                        lines.append(f'- [{ann_type}] "{ann["selected_text"]}"')
                    if ann.get("note"):
                        lines.append(f"  Note: {ann['note']}")
                    lines.append("")

            # External references
            if book.get("external_references"):
                lines.append("### External References")
                lines.append("")
                for ref in book["external_references"]:
                    lines.append(f"- [{ref['title']}]({ref['url']}) — {ref['source_name']}")
                    if ref.get("snippet"):
                        lines.append(f"  {ref['snippet']}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
