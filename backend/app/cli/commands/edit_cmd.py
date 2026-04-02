"""CLI commands for metadata and summary editing (Phase 2)."""

import typer
from sqlalchemy import select

from app.cli.deps import async_command, get_services
from app.cli.formatting import (
    console,
    edit_in_editor,
    print_error,
    print_success,
)

edit_app = typer.Typer(help="Edit commands.")


@edit_app.command("metadata")
@async_command
async def edit_metadata(
    book_id: int = typer.Argument(..., help="Book ID."),
    title: str = typer.Option(None, "--title", help="New title."),
    author: str = typer.Option(None, "--author", help="New author name (replaces all)."),
):
    """Edit book metadata (title, author)."""
    if not title and not author:
        print_error("Provide at least one of --title or --author.")
        raise typer.Exit(1)

    async with get_services() as svc:
        from app.db.models import Book
        from app.db.repositories.book_repo import AuthorRepository, BookRepository

        session = svc["session"]
        book_repo = BookRepository(session)
        book = await book_repo.get_by_id(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        if title:
            book.title = title

        if author:
            author_repo = AuthorRepository(session)
            new_author = await author_repo.get_or_create(author)
            # Clear existing authors and set new one
            from app.db.models import BookAuthor

            await session.execute(
                select(BookAuthor).where(BookAuthor.book_id == book_id)
            )
            # Remove old associations
            from sqlalchemy import delete

            await session.execute(
                delete(BookAuthor).where(BookAuthor.book_id == book_id)
            )
            session.add(BookAuthor(book_id=book_id, author_id=new_author.id))

        await session.flush()
        print_success(f"Book {book_id} updated.")


@edit_app.command("summary")
@async_command
async def edit_summary(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID. Omit for book-level summary."),
):
    """Edit a summary in $EDITOR. Marks as user_edited=True."""
    async with get_services() as svc:
        session = svc["session"]

        if section_id:
            from app.db.models import BookSection

            result = await session.execute(
                select(BookSection).where(BookSection.id == section_id)
            )
            section = result.scalar_one_or_none()
            if not section:
                print_error(f"Section {section_id} not found.")
                raise typer.Exit(1)

            if not section.summary_md:
                print_error(
                    f"No summary for section {section_id}. "
                    f"Run `bookcompanion summarize {book_id}` first."
                )
                raise typer.Exit(1)

            edited = edit_in_editor(section.summary_md, suffix=".md")
            if edited.strip() != section.summary_md.strip():
                section.summary_md = edited
                section.user_edited = True
                await session.flush()
                print_success(
                    f"Section {section_id} summary updated (marked as user_edited)."
                )
            else:
                console.print("No changes detected.")
        else:
            from app.db.models import Book
            from app.db.repositories.book_repo import BookRepository

            book_repo = BookRepository(session)
            book = await book_repo.get_by_id(book_id)
            if not book:
                print_error(f"Book {book_id} not found.")
                raise typer.Exit(1)

            summary = book.overall_summary or book.quick_summary
            if not summary:
                print_error(
                    f"No summary for book {book_id}. "
                    f"Run `bookcompanion summarize {book_id}` first."
                )
                raise typer.Exit(1)

            edited = edit_in_editor(summary, suffix=".md")
            if edited.strip() != summary.strip():
                book.overall_summary = edited
                await session.flush()
                print_success(f"Book {book_id} summary updated.")
            else:
                console.print("No changes detected.")
