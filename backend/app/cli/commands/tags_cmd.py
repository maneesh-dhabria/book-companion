"""CLI commands for tags (Phase 2)."""

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    print_empty_state,
    print_error,
    print_success,
    print_tag_table,
)

tags_app = typer.Typer(help="Tag commands.")


@tags_app.command("add")
@async_command
async def add_tag(
    book_id: int = typer.Argument(..., help="Book ID to tag."),
    tag_name: str = typer.Argument(..., help="Tag name."),
    color: str = typer.Option(None, "--color", help="Tag color (hex, e.g., #FF5733)."),
):
    """Add a tag to a book."""
    async with get_services() as svc:
        try:
            tag = await svc["tag"].add_tag(
                taggable_type="book",
                taggable_id=book_id,
                tag_name=tag_name,
                color=color,
            )
            print_success(f'Tagged book {book_id} with "{tag.name}".')
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)


@tags_app.command("list")
@async_command
async def list_tags():
    """List all tags in the system."""
    async with get_services() as svc:
        tags = await svc["tag"].list_tags()
        if not tags:
            print_empty_state("No tags found. Use `bookcompanion tag add` to create tags.")
            return
        print_tag_table(tags)


@tags_app.command("remove")
@async_command
async def remove_tag(
    book_id: int = typer.Argument(..., help="Book ID."),
    tag_name: str = typer.Argument(..., help="Tag name to remove."),
):
    """Remove a tag from a book."""
    async with get_services() as svc:
        removed = await svc["tag"].remove_tag("book", book_id, tag_name)
        if removed:
            print_success(f'Removed tag "{tag_name}" from book {book_id}.')
        else:
            print_error(f'Tag "{tag_name}" not found on book {book_id}.')
