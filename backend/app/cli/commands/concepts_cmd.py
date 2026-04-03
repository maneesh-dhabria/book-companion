"""CLI commands for concepts index (Phase 2)."""

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    console,
    edit_in_editor,
    print_concept_table,
    print_empty_state,
    print_error,
    print_success,
)

concepts_app = typer.Typer(help="Concepts index commands.")


@concepts_app.command("list")
@async_command
async def list_concepts(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Show concepts index for a book."""
    async with get_services() as svc:
        concepts = await svc["concept"].list_by_book(book_id)
        if not concepts:
            print_empty_state(
                "No concepts found for this book. Concepts are extracted during summarization."
            )
            return
        print_concept_table(concepts)


@concepts_app.command("search")
@async_command
async def search_concepts(
    term: str = typer.Argument(..., help="Search term."),
):
    """Search concepts across all books."""
    async with get_services() as svc:
        try:
            concepts = await svc["concept"].search(term)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        if not concepts:
            print_empty_state(f'No concepts found matching "{term}".')
            return
        print_concept_table(concepts)


@concepts_app.command("edit")
@async_command
async def edit_concepts(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Edit concepts for a book in $EDITOR. Marks edited entries as user_edited."""
    async with get_services() as svc:
        concepts = await svc["concept"].list_by_book(book_id)
        if not concepts:
            print_empty_state("No concepts to edit.")
            return

        # Build editable content
        lines = [
            "# Concepts Index",
            "# Edit definitions below. Lines starting with # are ignored.",
            "# Format: CONCEPT_ID | TERM | DEFINITION",
            "",
        ]
        for c in concepts:
            lines.append(f"{c.id} | {c.term} | {c.definition}")

        content = "\n".join(lines)
        edited = edit_in_editor(content, suffix=".md")

        # Parse edited content
        updates = []
        for line in edited.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 2)
            if len(parts) != 3:
                continue
            try:
                concept_id = int(parts[0].strip())
                definition = parts[2].strip()
                updates.append({"id": concept_id, "definition": definition})
            except ValueError:
                continue

        if updates:
            updated = await svc["concept"].bulk_update_definitions(updates)
            print_success(f"Updated {len(updated)} concept(s).")
        else:
            console.print("No changes detected.")
