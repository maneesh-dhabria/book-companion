"""CLI commands for export (Phase 2)."""

import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import console, print_error, print_success

export_app = typer.Typer(help="Export commands.")


@export_app.command("book")
@async_command
async def export_book(
    book_id: int = typer.Argument(..., help="Book ID to export."),
    fmt: str = typer.Option("json", "--format", "-f", help="Export format: json or markdown."),
    output: str = typer.Option(None, "--output", "-o", help="Output file path."),
):
    """Export a single book's data."""
    async with get_services() as svc:
        try:
            content = await svc["export"].export_book(book_id, fmt=fmt, output_path=output)
            if output:
                print_success(f"Book exported to {output}")
            else:
                console.print(content)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)


@export_app.command("library")
@async_command
async def export_library(
    fmt: str = typer.Option("json", "--format", "-f", help="Export format: json or markdown."),
    output: str = typer.Option(None, "--output", "-o", help="Output file path."),
):
    """Export the entire library."""
    async with get_services() as svc:
        try:
            content = await svc["export"].export_library(fmt=fmt, output_path=output)
            if output:
                print_success(f"Library exported to {output}")
            else:
                console.print(content)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)
