"""CLI commands for tags — book + section scopes, suggestions, filter."""

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    print_empty_state,
    print_error,
    print_success,
    print_tag_table,
)

tags_app = typer.Typer(help="Tag commands.")


def _validate_scope(scope: str) -> str:
    if scope not in {"book", "section"}:
        print_error(f"Invalid scope '{scope}'. Use 'book' or 'section'.")
        raise typer.Exit(2)
    return scope


@tags_app.command("add")
@async_command
async def add_tag(
    scope: str = typer.Argument(..., help="Scope: 'book' or 'section'."),
    entity_id: int = typer.Argument(..., help="Book or section id."),
    tag_name: str = typer.Argument(..., help="Tag name."),
    color: str = typer.Option(None, "--color", help="Tag color (hex, e.g., #FF5733)."),
):
    """Add a tag to a book or section. Idempotent."""
    scope = _validate_scope(scope)
    async with get_services() as svc:
        try:
            tag = await svc["tag"].add_tag(
                taggable_type=scope,
                taggable_id=entity_id,
                tag_name=tag_name,
                color=color,
            )
            await svc["session"].commit()
            print_success(f'Tagged {scope} {entity_id} with "{tag.name}".')
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from e


@tags_app.command("list")
@async_command
async def list_tags(
    scope: str = typer.Option(None, "--scope", help="Filter: 'book' or 'section'."),
    entity_id: int = typer.Option(
        None, "--id", help="Restrict to tags on a specific entity id."
    ),
):
    """List tags. With --scope + --id: tags for that entity. Otherwise all tags."""
    async with get_services() as svc:
        if scope and entity_id:
            _validate_scope(scope)
            tags = await svc["tag"].list_tags_for_entity(scope, entity_id)
        else:
            tags = await svc["tag"].list_tags()
        if not tags:
            print_empty_state("No tags found.")
            return
        print_tag_table(tags)


@tags_app.command("remove")
@async_command
async def remove_tag(
    scope: str = typer.Argument(..., help="Scope: 'book' or 'section'."),
    entity_id: int = typer.Argument(..., help="Book or section id."),
    tag_name: str = typer.Argument(..., help="Tag name to remove."),
):
    """Remove a tag association."""
    scope = _validate_scope(scope)
    async with get_services() as svc:
        removed = await svc["tag"].remove_tag(scope, entity_id, tag_name)
        await svc["session"].commit()
        if removed:
            print_success(f'Removed tag "{tag_name}" from {scope} {entity_id}.')
        else:
            print_error(f'Tag "{tag_name}" not found on {scope} {entity_id}.')


@tags_app.command("filter")
@async_command
async def filter_by_tag(
    tag_name: str = typer.Argument(..., help="Tag name to filter by."),
    scope: str = typer.Option(
        None, "--scope", help="Optional scope filter: 'book' or 'section'."
    ),
):
    """List entities tagged with a given tag name."""
    async with get_services() as svc:
        if scope:
            _validate_scope(scope)
        taggables = await svc["tag"].list_by_tag(tag_name, scope)
        if not taggables:
            print_empty_state(f"No entities found tagged '{tag_name}'.")
            return
        for t in taggables:
            typer.echo(f"{t.taggable_type}#{t.taggable_id}")


@tags_app.command("suggest")
@async_command
async def suggest_tags(
    book_id: int = typer.Argument(..., help="Book id."),
):
    """Print the LLM-suggested tags stored on a book (FR-E4.2)."""
    async with get_services() as svc:
        from app.db.models import Book

        book = await svc["session"].get(Book, book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)
        suggestions = book.suggested_tags_json or []
        if not suggestions:
            print_empty_state("No AI tag suggestions stored for this book.")
            return
        for s in suggestions:
            typer.echo(s)
