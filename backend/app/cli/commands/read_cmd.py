"""bookcompanion read — display original section content."""

import typer
from rich.console import Console

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_error, print_markdown

console = Console()


@async_command
async def read(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(..., help="Section ID."),
    with_summary: bool = typer.Option(
        False, "--with-summary", help="Show default summary below content."
    ),
):
    """Read original section content, optionally with its default summary."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        section = next((s for s in (book.sections or []) if s.id == section_id), None)
        if not section:
            print_error(f"Section {section_id} not found.")
            raise typer.Exit(1)

        content = f"## {section.title}\n\n{section.content_md or '(no content)'}"

        if with_summary and section.default_summary_id:
            summary_service = svc.get("summary_service")
            if summary_service:
                summary = await summary_service.get_by_id(section.default_summary_id)
                content += f"\n\n{'---' * 13}\n\n## Summary\n\n{summary.summary_md}"
        elif with_summary:
            content += "\n\n(no summary available)"

        print_markdown(content, use_pager=True)
