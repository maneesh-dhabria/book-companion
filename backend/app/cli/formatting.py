"""Shared rich formatting helpers for CLI output."""

import os
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_book_table(books):
    """Print books as a rich table."""
    table = Table(title="Library")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Author(s)")
    table.add_column("Status")
    table.add_column("Sections", justify="right")
    table.add_column("Created")

    for book in books:
        authors = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"
        table.add_row(
            str(book.id),
            book.title,
            authors,
            book.status.value if book.status else "unknown",
            str(len(book.sections)) if book.sections else "0",
            book.created_at.strftime("%Y-%m-%d") if book.created_at else "",
        )
    console.print(table)


def print_markdown(content: str, use_pager: bool = True):
    """Render markdown content with optional pager."""
    md = Markdown(content)
    if use_pager:
        with console.pager():
            console.print(md)
    else:
        console.print(md)


def print_error(message: str):
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str):
    console.print(f"[green]{message}[/green]")


def print_empty_state(message: str):
    console.print(Panel(message, style="dim"))


# Global format flag — set in main callback
_output_format: str = "text"


def set_output_format(fmt: str):
    global _output_format
    _output_format = fmt


def should_json() -> bool:
    return _output_format == "json"


def print_json_or_table(data: list[dict] | dict, table_fn):
    """If --format json, print JSON. Otherwise use the provided table function."""
    if should_json():
        import json

        console.print(json.dumps(data, indent=2, default=str))
    else:
        table_fn()


def print_warning(message: str):
    console.print(f"[yellow]{message}[/yellow]")


def edit_in_editor(content: str, suffix: str = ".md") -> str:
    """Open content in $EDITOR, return modified content.

    Uses $EDITOR, then $VISUAL, then falls back to 'vim'.
    """
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    with tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False) as f:
        f.write(content)
        f.flush()
        tmp_path = f.name

    try:
        subprocess.call([editor, tmp_path])
        with open(tmp_path) as edited:
            return edited.read()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def print_annotation_table(annotations):
    """Print annotations as a rich table."""
    table = Table(title="Annotations")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Type")
    table.add_column("Content Type")
    table.add_column("Text", max_width=40)
    table.add_column("Note", max_width=40)
    table.add_column("Created")

    for ann in annotations:
        ann_type = ann.type.value if ann.type else "note"
        ct = ann.content_type.value if ann.content_type else "-"
        text = (
            (ann.selected_text[:37] + "...")
            if ann.selected_text and len(ann.selected_text) > 40
            else (ann.selected_text or "-")
        )
        note = (ann.note[:37] + "...") if ann.note and len(ann.note) > 40 else (ann.note or "-")
        created = ann.created_at.strftime("%Y-%m-%d") if ann.created_at else "-"
        table.add_row(str(ann.id), ann_type, ct, text, note, created)

    console.print(table)


def print_concept_table(concepts):
    """Print concepts as a rich table."""
    table = Table(title="Concepts Index")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Term", style="bold")
    table.add_column("Definition", max_width=60)
    table.add_column("Edited", justify="center")

    for concept in concepts:
        defn = (
            (concept.definition[:57] + "...")
            if len(concept.definition) > 60
            else concept.definition
        )
        edited = "Yes" if concept.user_edited else ""
        table.add_row(str(concept.id), concept.term, defn, edited)

    console.print(table)


def print_tag_table(tags):
    """Print tags as a rich table."""
    table = Table(title="Tags")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("Color")

    for tag in tags:
        color = tag.color or "-"
        table.add_row(str(tag.id), tag.name, color)

    console.print(table)


def print_reference_table(refs):
    """Print external references as a rich table."""
    table = Table(title="External References")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Title", style="bold", max_width=40)
    table.add_column("Source")
    table.add_column("URL", max_width=50)
    table.add_column("Snippet", max_width=40)

    for ref in refs:
        snippet = (
            (ref.snippet[:37] + "...")
            if ref.snippet and len(ref.snippet) > 40
            else (ref.snippet or "-")
        )
        table.add_row(str(ref.id), ref.title, ref.source_name, ref.url, snippet)

    console.print(table)


def print_backup_table(backups):
    """Print backup files as a rich table."""
    table = Table(title="Backups")
    table.add_column("Filename")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Created")

    for b in backups:
        table.add_row(
            b["filename"],
            str(b["size_mb"]),
            b.get("created") or "-",
        )

    console.print(table)


def eval_status(eval_json: dict | None) -> str:
    """Derive eval status: —/passed/partial/failed."""
    if not eval_json or not isinstance(eval_json, dict):
        return "—"
    total = eval_json.get("total", 0)
    passed = eval_json.get("passed", 0)
    if total == 0:
        return "—"
    if passed == total:
        return "[green]passed[/green]"
    results = eval_json.get("results", eval_json.get("assertions", {}))
    if isinstance(results, dict):
        try:
            from app.services.summarizer.evaluator import ASSERTION_REGISTRY

            for name, r in results.items():
                if isinstance(r, dict) and not r.get("passed"):
                    if ASSERTION_REGISTRY.get(name, {}).get("category") == "critical":
                        return "[red]failed[/red]"
        except ImportError:
            pass
    return "[yellow]partial[/yellow]"


def eval_results(eval_json: dict | None) -> str:
    """Format eval pass/total."""
    if not eval_json or not isinstance(eval_json, dict):
        return "—"
    passed = eval_json.get("passed", 0)
    total = eval_json.get("total", 0)
    return f"{passed}/{total}" if total else "—"
