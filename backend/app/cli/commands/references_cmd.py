"""CLI commands for external references (Phase 2)."""

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    console,
    print_empty_state,
    print_error,
    print_reference_table,
    print_success,
)

references_app = typer.Typer(help="External reference commands.")


@references_app.command("list")
@async_command
async def list_references(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """List external references for a book."""
    async with get_services() as svc:
        refs = await svc["reference"].list_references(book_id)
        if not refs:
            print_empty_state(
                "No external references found. "
                "Run `bookcompanion references discover <book_id>` to find some."
            )
            return
        print_reference_table(refs)


@references_app.command("discover")
@async_command
async def discover_references(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Search the web for external summaries/reviews of a book."""
    async with get_services() as svc:
        try:
            console.print("Discovering external references...")
            refs = await svc["reference"].discover_references(book_id)
            if refs:
                print_success(f"Found {len(refs)} external reference(s).")
                print_reference_table(refs)
            else:
                print_empty_state("No references discovered.")
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)
