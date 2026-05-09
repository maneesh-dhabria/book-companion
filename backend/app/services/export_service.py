"""Export service -- JSON and Markdown export for books and library."""

import json
import re
from dataclasses import dataclass, field
from datetime import date as _date
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
from app.services.slug import gfm_slug


class ExportError(BookCompanionError):
    """Export-related errors."""


class QuizExportError(ExportError):
    """Raised when a quiz session cannot be exported (e.g., abandoned)."""


_BLOCK_TRIGGER_LINE_RE = re.compile(r"^(\s*)([>#\-*+]|\d+\.)")


def _escape_block_triggers(text: str) -> str:
    """Collapse newlines so block-level triggers cannot start a new line."""
    return text.replace("\r\n", " ").replace("\n", " ")


def _escape_at_line_start(s: str) -> str:
    """Escape if the string begins with a block-level markdown trigger."""
    return _BLOCK_TRIGGER_LINE_RE.sub(r"\1\\\2", s)


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
            book_anns = await self._collect_book_annotations(book)
            body, _is_empty = await self._render_summary_markdown(
                book_data, ExportSelection(), book_annotations=book_anns
            )
            content = body
        else:
            raise ExportError(f"Unsupported format: {fmt}. Use 'json' or 'markdown'.")

        if output_path:
            Path(output_path).write_text(content, encoding="utf-8")

        return content

    async def export_library(self, fmt: str = "json", output_path: str | None = None) -> str:
        """Export the entire library in the specified format."""
        if fmt != "json":
            raise ExportError(
                "Library Markdown export was removed in v1.6 -- use --format json "
                "for full-library backups, or run 'export book' per book."
            )
        books = await self.book_repo.list_all()
        all_data = []
        for book in books:
            book_data = await self._collect_book_data(book)
            all_data.append(book_data)

        content = self._render_json(all_data)

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

    async def _render_summary_markdown(
        self,
        book_data: dict,
        selection: ExportSelection,
        book_annotations: list[dict] | None = None,
    ) -> tuple[str, bool]:
        """Render the summaries-focused Markdown shape.

        Returns (body, is_empty) where is_empty is True iff none of TOC,
        book-summary, per-section, or notes-footer was emitted (FR-A6).
        """
        toc_emitted = False
        book_summary_emitted = False
        any_section_emitted = False
        notes_emitted = False
        lines: list[str] = []

        # Front matter
        lines.append(f"# {book_data['title']}")
        authors = book_data.get("authors") or []
        if not authors:
            lines.append("**Author:** Unknown")
        elif len(authors) == 1:
            lines.append(f"**Author:** {authors[0]}")
        else:
            lines.append(f"**Authors:** {', '.join(authors)}")
        lines.append(f"**Exported:** {_date.today().isoformat()}")
        lines.append("")

        rendered_sections = sorted(
            [
                s
                for s in (book_data.get("sections") or [])
                if s.get("has_summary")
                and s.get("summary_md")
                and s["id"] not in selection.exclude_section_ids
            ],
            key=lambda s: s["order_index"],
        )

        # Slug-disambiguation table over rendered_sections
        slug_table: dict[int, str] = {}
        slug_counter: dict[str, int] = {}
        for s in rendered_sections:
            base = gfm_slug(s["title"]) or f"section-{s['order_index']:03d}"
            n = slug_counter.get(base, 0)
            slug_table[s["id"]] = base if n == 0 else f"{base}-{n}"
            slug_counter[base] = n + 1

        if selection.include_toc and rendered_sections:
            lines.append("## Table of Contents")
            for s in rendered_sections:
                indent = "  " * (s.get("depth", 0) or 0)
                lines.append(f"{indent}- [{s['title']}](#{slug_table[s['id']]})")
            lines.append("")
            toc_emitted = True

        # Highlights + Notes footer: extended in T6

        summary = book_data.get("quick_summary")
        if selection.include_book_summary and summary:
            lines.append(_sanitize_image_urls(summary))
            lines.append("")
            book_summary_emitted = True

        section_anns_by_id: dict[int, list[dict]] = {}
        if selection.include_annotations:
            for a in book_data.get("annotations") or []:
                if a.get("content_type") not in ("section_content", "section_summary"):
                    continue
                if not (a.get("selected_text") or "").strip():
                    continue
                section_anns_by_id.setdefault(a.get("content_id"), []).append(a)

        for s in rendered_sections:
            lines.append(f"## {s['title']}")
            lines.append(_sanitize_image_urls(s["summary_md"]))
            lines.append("")
            any_section_emitted = True

            section_anns = section_anns_by_id.get(s["id"], [])
            if section_anns:
                lines.append("### Highlights")
                for a in section_anns:
                    sel = _escape_at_line_start(
                        _escape_block_triggers(a.get("selected_text") or "")
                    )
                    lines.append(f"> {sel}")
                    note = (a.get("note") or "").strip()
                    if note:
                        note_e = _escape_at_line_start(_escape_block_triggers(note))
                        lines.append(f"> — Note: {note_e}")
                    lines.append("")

        if selection.include_annotations and book_annotations:
            rendered_notes: list[str] = []
            for a in book_annotations:
                sel = (a.get("selected_text") or "").strip()
                note = (a.get("note") or "").strip()
                if sel and note:
                    sel_e = _escape_at_line_start(_escape_block_triggers(sel))
                    note_e = _escape_at_line_start(_escape_block_triggers(note))
                    rendered_notes.append(f'- > "{sel_e}"\n  — {note_e}')
                elif note:
                    note_e = _escape_at_line_start(_escape_block_triggers(note))
                    rendered_notes.append(f"- {note_e}")
                elif sel:
                    sel_e = _escape_at_line_start(_escape_block_triggers(sel))
                    rendered_notes.append(f'- > "{sel_e}"')
            if rendered_notes:
                lines.append("## Notes")
                lines.extend(rendered_notes)
                lines.append("")
                notes_emitted = True

        body = "\n".join(lines)
        is_empty = not (toc_emitted or book_summary_emitted or any_section_emitted or notes_emitted)
        return body, is_empty

    async def export_book_markdown(
        self, book_id: int, selection: ExportSelection
    ) -> tuple[str, bool]:
        """Public orchestrator for the new Markdown shape.

        Single call site for HTTP route + CLI. Returns (body, is_empty).
        Raises ExportError when book is not found (callers translate to 404).
        """
        book = await self.book_repo.get_by_id(book_id)
        if not book:
            raise ExportError(f"Book {book_id} not found.")
        book_data = await self._collect_book_data(book)
        book_anns = await self._collect_book_annotations(book)
        return await self._render_summary_markdown(book_data, selection, book_annotations=book_anns)

    async def export_quiz_session(
        self,
        session_id: int,
        fmt: str = "markdown",
    ) -> str:
        """Render a single quiz session to Markdown (FR-100..FR-105, §9.10).

        - Refuses to export ``abandoned`` sessions (E15 / FR-105).
        - Sanitizes in-app `/api/v1/images/{id}` references in citation
          snippets and feedback fields so the exported Markdown is portable.
        - Uses ``app/templates/exports/quiz_session.md.j2`` via Jinja2.
        """
        if fmt != "markdown":
            raise ExportError(f"Unsupported quiz-session export format: {fmt!r}")

        from sqlalchemy.orm import selectinload

        from app.db.models import QuizSession

        result = await self.session.execute(
            select(QuizSession)
            .where(QuizSession.id == session_id)
            .options(selectinload(QuizSession.questions))
        )
        qs = result.scalar_one_or_none()
        if qs is None:
            raise ExportError(f"Quiz session {session_id} not found.")
        if qs.status == "abandoned":
            raise QuizExportError(
                f"Cannot export an abandoned session — answer at least one "
                f"question first. (session_id={session_id})"
            )

        book = await self.book_repo.get_by_id(qs.book_id)
        if book is None:
            raise ExportError(f"Book {qs.book_id} for session {session_id} not found.")

        questions_sorted = sorted(
            (q for q in (qs.questions or []) if not q.is_stale),
            key=lambda q: (q.created_at, q.id),
        )

        # Tally — single source of truth lives in the API route helper, but
        # to avoid pulling that into a service-layer dep we recompute here
        # using the same predicate.
        tally = {"got_it": 0, "partial": 0, "missed": 0, "skipped": 0, "discarded": 0}
        for q in questions_sorted:
            if q.discarded:
                tally["discarded"] += 1
                continue
            if q.skip_count > 0 and q.user_answer is None and q.self_assessment is None:
                tally["skipped"] += 1
                continue
            if q.self_assessment in tally:
                tally[q.self_assessment] += 1

        # Inflate each question into a template-friendly dict.
        question_views = [_quiz_question_to_view(q) for q in questions_sorted]

        import jinja2

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                str(Path(__file__).resolve().parent.parent / "templates" / "exports")
            ),
            autoescape=False,
            trim_blocks=False,
            lstrip_blocks=False,
            keep_trailing_newline=True,
        )
        env.filters["sanitize_image_urls"] = _sanitize_image_urls
        template = env.get_template("quiz_session.md.j2")
        return template.render(
            book={"title": book.title},
            session=qs,
            questions=question_views,
            tally=tally,
        )


def _quiz_question_to_view(q) -> dict:
    """Translate a QuizQuestion ORM row into a flat dict for the Jinja2 template."""
    citation_raw = q.citation_json or "{}"
    try:
        citation = json.loads(citation_raw)
    except (TypeError, json.JSONDecodeError):
        citation = {"section_title": "", "snippet": str(citation_raw)}
    feedback = None
    if q.feedback_json:
        try:
            feedback = json.loads(q.feedback_json)
        except (TypeError, json.JSONDecodeError):
            feedback = None
    mcq_options: list[str] = []
    if q.mcq_options_json:
        try:
            mcq_options = json.loads(q.mcq_options_json) or []
        except (TypeError, json.JSONDecodeError):
            mcq_options = []
    return {
        "id": q.id,
        "shape": q.shape,
        "stem": q.stem,
        "concept_label": q.concept_label,
        "citation": {
            "section_title": citation.get("section_title", ""),
            "snippet": citation.get("snippet", ""),
        },
        "mcq_options": mcq_options,
        "user_answer": q.user_answer,
        "feedback": feedback,
        "self_assessment": q.self_assessment,
        "override_note": q.override_note,
        "skip_count": q.skip_count,
        "discarded": q.discarded,
        "warm_up": q.warm_up,
    }
