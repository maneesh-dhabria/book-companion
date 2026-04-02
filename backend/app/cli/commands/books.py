"""Book management CLI commands: add, list, show, delete, read, authors."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    print_book_table,
    print_empty_state,
    print_error,
    print_json_or_table,
    print_markdown,
    print_success,
    should_json,
)

console = Console()


@async_command
async def add(
    file_path: Path = typer.Argument(..., help="Path to the book file."),
    quick: bool = typer.Option(False, "--quick", help="Parse + generate a rough book-level summary."),
    async_mode: bool = typer.Option(False, "--async", help="Parse + summarize in background."),
    force: bool = typer.Option(False, "--force", help="Re-import or retry failed parse."),
):
    """Upload and parse a book file (EPUB, MOBI, or PDF)."""
    if not file_path.exists():
        print_error(f"File not found: {file_path}")
        raise typer.Exit(1)

    if not file_path.suffix.lower() in (".epub", ".mobi", ".pdf"):
        print_error(f"Unsupported format: {file_path.suffix}. Supported: .epub, .mobi, .pdf")
        raise typer.Exit(1)

    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available. Service layer may not be implemented yet.")
            raise typer.Exit(1)

        console.print(f'\nParsing "{file_path.name}"...')

        try:
            book = await book_service.add_book(str(file_path), force=force)
        except Exception as e:
            if "already exists" in str(e).lower():
                print_error(str(e))
                console.print("Use --force to re-import.")
                raise typer.Exit(1)
            raise

        # Reload book with eager-loaded relationships
        book = await book_service.get_book(book.id)

        authors = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"
        console.print(f'Title: "{book.title}"')
        console.print(f"Author(s): {authors}")
        console.print(f"Format: {book.file_format.upper()}")

        section_count = len(book.sections) if book.sections else 0

        if not async_mode and section_count > 0:
            console.print(f"\nDetected structure ({section_count} sections):")
            for section in (book.sections or []):
                indent = "  " * (section.depth + 1)
                console.print(f"{indent}{section.order_index + 1}. {section.title}")

            if not typer.confirm("\nAccept this structure?", default=True):
                console.print("Structure rejected. Use --force to re-import with different parsing.")
                raise typer.Exit(0)

        print_success(f"\nBook saved (ID: {book.id}). {section_count} sections parsed and stored.")

        if quick and svc.get("summarizer"):
            console.print("Generating quick summary...")
            try:
                await svc["summarizer"].quick_summary(book.id)
                print_success("Quick summary generated.")
            except Exception as e:
                print_error(f"Quick summary failed: {e}")

        if async_mode:
            console.print(
                f"Processing in background. Run `bookcompanion status {book.id}` to check."
            )
        else:
            console.print(f"Run `bookcompanion summarize {book.id}` to generate summaries.")


@async_command
async def list_books(
    recent: bool = typer.Option(False, "--recent", help="Sort by most recently accessed."),
    tag: str = typer.Option(None, "--tag", help="Filter by tag name. (Phase 2)"),
    author: str = typer.Option(None, "--author", help="Filter by author name (partial match)."),
    status: str = typer.Option(None, "--status", help="Filter by status."),
):
    """List all books in the library."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        try:
            books = await book_service.list_books(
                recent=recent, author=author, status=status
            )
        except Exception:
            # Fallback: try simpler call if service doesn't support filters
            try:
                books = await book_service.list_books()
            except Exception as e:
                print_error(f"Failed to list books: {e}")
                raise typer.Exit(1)

        # Phase 2: filter by tag if provided
        if tag and books:
            from app.db.models import Tag, Taggable
            from sqlalchemy import select

            session = svc["session"]
            result = await session.execute(
                select(Taggable.taggable_id)
                .join(Tag, Tag.id == Taggable.tag_id)
                .where(Tag.name == tag, Taggable.taggable_type == "book")
            )
            tagged_ids = set(result.scalars().all())
            books = [b for b in books if b.id in tagged_ids]

        if not books:
            print_empty_state("No books in your library yet. Run: bookcompanion add <file_path>")
            return

        if should_json():
            import json

            data = [
                {
                    "id": b.id,
                    "title": b.title,
                    "authors": [a.name for a in b.authors] if b.authors else [],
                    "status": b.status.value if b.status else "unknown",
                    "sections": len(b.sections) if b.sections else 0,
                    "created_at": str(b.created_at),
                }
                for b in books
            ]
            console.print(json.dumps(data, indent=2, default=str))
        else:
            print_book_table(books)


@async_command
async def show(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Show book details: metadata, section list, eval summary."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        try:
            book = await book_service.get_book(book_id)
        except Exception as e:
            print_error(f"Book not found: {e}")
            raise typer.Exit(1)

        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        authors = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"
        console.print(f"\n[bold]{book.title}[/bold]")
        console.print(f"Author(s): {authors}")
        console.print(f"Status: {book.status.value if book.status else 'unknown'}")
        console.print(f"Format: {book.file_format.upper()}")
        console.print(f"Created: {book.created_at}")

        if book.sections:
            console.print(f"\n[bold]Sections ({len(book.sections)}):[/bold]")
            table = Table()
            table.add_column("#", style="cyan")
            table.add_column("Title")
            table.add_column("Status")
            table.add_column("Tokens", justify="right")

            for section in book.sections:
                table.add_row(
                    str(section.order_index + 1),
                    section.title,
                    section.summary_status.value if section.summary_status else "pending",
                    str(section.content_token_count or "—"),
                )
            console.print(table)

        if book.overall_summary_eval:
            console.print("\n[bold]Eval Summary:[/bold]")
            eval_data = book.overall_summary_eval
            if isinstance(eval_data, dict):
                for k, v in eval_data.items():
                    console.print(f"  {k}: {v}")


@async_command
async def delete(
    book_id: int = typer.Argument(..., help="Book ID."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
):
    """Delete a book and all related data."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        try:
            book = await book_service.get_book(book_id)
        except Exception:
            book = None

        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        if not yes:
            if not typer.confirm(
                f'Delete "{book.title}" (ID: {book_id}) and all related data?'
            ):
                console.print("Cancelled.")
                raise typer.Exit(0)

        try:
            await book_service.delete_book(book_id)
            await svc["session"].commit()
            print_success(f"Book {book_id} deleted.")
        except Exception as e:
            print_error(f"Failed to delete: {e}")
            raise typer.Exit(1)


@async_command
async def read(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID. If omitted, shows all sections."),
    with_summary: bool = typer.Option(
        False, "--with-summary", help="Show content and summary side-by-side."
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy content to clipboard."),
    export: str = typer.Option(None, "--export", help="Export content to a file."),
):
    """Read original book content."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        try:
            book = await book_service.get_book(book_id)
        except Exception:
            book = None

        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        if section_id is not None:
            sections = [s for s in (book.sections or []) if s.id == section_id]
            if not sections:
                print_error(f"Section {section_id} not found in book {book_id}.")
                raise typer.Exit(1)
        else:
            sections = book.sections or []

        if not sections:
            print_empty_state("No sections found for this book.")
            return

        content_parts = []
        for section in sections:
            content = section.content_md or ""
            if with_summary and section.summary_md:
                from rich.columns import Columns
                from rich.panel import Panel

                cols = Columns(
                    [
                        Panel(content[:2000], title=f"{section.title} — Content"),
                        Panel(section.summary_md[:2000], title=f"{section.title} — Summary"),
                    ],
                    equal=True,
                )
                console.print(cols)
            else:
                content_parts.append(f"## {section.title}\n\n{content}")

        if content_parts and not with_summary:
            full_content = "\n\n".join(content_parts)
            print_markdown(full_content, use_pager=True)

            if copy:
                _copy_to_clipboard(full_content)

            if export:
                Path(export).write_text(full_content)
                print_success(f"Exported to {export}")


@async_command
async def authors():
    """List all authors with book counts."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        try:
            author_list = await book_service.list_authors()
        except Exception as e:
            print_error(f"Failed to list authors: {e}")
            raise typer.Exit(1)

        if not author_list:
            print_empty_state("No authors found. Add a book first.")
            return

        table = Table(title="Authors")
        table.add_column("Author Name", style="bold")
        table.add_column("Book Count", justify="right")
        table.add_column("Book Titles")

        for item in author_list:
            # list_with_book_counts returns Row(Author, count)
            author = item[0]
            count = item[1]
            table.add_row(author.name, str(count), "")
        console.print(table)


def _copy_to_clipboard(text: str):
    """Copy text to clipboard using pyperclip or pbcopy fallback."""
    try:
        import pyperclip

        pyperclip.copy(text)
        print_success("Copied to clipboard.")
    except Exception:
        import subprocess

        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            print_success("Copied to clipboard.")
        except Exception:
            print_error("Could not copy to clipboard. Install pyperclip or use macOS.")
