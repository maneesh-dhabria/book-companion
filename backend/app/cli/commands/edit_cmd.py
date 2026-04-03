"""CLI commands for metadata and summary editing (Phase 2)."""

import typer
from rich.table import Table
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
    """Edit a summary in $EDITOR."""
    # TODO: V1.1 — rewrite to load/save via Summary table
    async with get_services() as svc:
        session = svc["session"]

        if section_id:
            from app.db.models import BookSection, Summary

            result = await session.execute(
                select(BookSection).where(BookSection.id == section_id)
            )
            section = result.scalar_one_or_none()
            if not section:
                print_error(f"Section {section_id} not found.")
                raise typer.Exit(1)

            if not section.default_summary_id:
                print_error(
                    f"No summary for section {section_id}. "
                    f"Run `bookcompanion summarize {book_id}` first."
                )
                raise typer.Exit(1)

            # Load summary from Summary table
            result = await session.execute(
                select(Summary).where(Summary.id == section.default_summary_id)
            )
            summary_obj = result.scalar_one_or_none()
            if not summary_obj:
                print_error("Summary record not found.")
                raise typer.Exit(1)

            edited = edit_in_editor(summary_obj.summary_md, suffix=".md")
            if edited.strip() != summary_obj.summary_md.strip():
                summary_obj.summary_md = edited
                await session.flush()
                print_success(f"Section {section_id} summary updated.")
            else:
                console.print("No changes detected.")
        else:
            from app.db.models import Book, Summary
            from app.db.repositories.book_repo import BookRepository

            book_repo = BookRepository(session)
            book = await book_repo.get_by_id(book_id)
            if not book:
                print_error(f"Book {book_id} not found.")
                raise typer.Exit(1)

            summary_obj = None
            if book.default_summary_id:
                result = await session.execute(
                    select(Summary).where(Summary.id == book.default_summary_id)
                )
                summary_obj = result.scalar_one_or_none()
                summary_text = summary_obj.summary_md if summary_obj else None
            else:
                summary_text = book.quick_summary

            if not summary_text:
                print_error(
                    f"No summary for book {book_id}. "
                    f"Run `bookcompanion summarize {book_id}` first."
                )
                raise typer.Exit(1)

            edited = edit_in_editor(summary_text, suffix=".md")
            if edited.strip() != summary_text.strip():
                if book.default_summary_id and summary_obj:
                    summary_obj.summary_md = edited
                else:
                    book.quick_summary = edited
                await session.flush()
                print_success(f"Book {book_id} summary updated.")
            else:
                console.print("No changes detected.")


@edit_app.command("sections")
@async_command
async def edit_sections(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Interactive section merge/split/reorder/delete (post-save)."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        section_edit_svc = svc.get("section_edit")
        if not section_edit_svc:
            print_error("Section edit service not available.")
            raise typer.Exit(1)

        try:
            book = await book_service.get_book(book_id)
        except Exception:
            book = None

        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        if not book.sections:
            print_error("No sections found for this book.")
            raise typer.Exit(1)

        # Display current structure
        console.print(f'\n[bold]{book.title}[/bold] — {len(book.sections)} sections\n')
        _show_db_sections(book.sections)

        console.print(
            "\n[bold]Section Editor[/bold] — commands: "
            "show, merge 1,2 [\"title\"], split <id> --at-char <pos>, "
            "delete 1,2 (by section ID), move <id> --after <id>, done"
        )

        from app.exceptions import SectionEditError
        from app.services.section_edit_service import parse_command

        modified = False

        while True:
            try:
                raw = typer.prompt("edit>", default="done")
            except (KeyboardInterrupt, EOFError):
                console.print("\nAborted.")
                break

            try:
                cmd = parse_command(raw)
            except SectionEditError as e:
                print_error(str(e))
                continue

            if cmd.action == "done":
                break

            if cmd.action == "show":
                book = await book_service.get_book(book_id)
                _show_db_sections(book.sections or [])
                continue

            if cmd.action == "undo":
                console.print(
                    "Undo not available in DB mode. Changes are applied immediately."
                )
                continue

            if cmd.action == "delete":
                section_ids = cmd.indices
                names = []
                for s in (book.sections or []):
                    if s.id in section_ids:
                        names.append(f"{s.id}: {s.title}")
                if not names:
                    print_error("No matching section IDs found.")
                    continue
                if typer.confirm(f"Delete {', '.join(names)}?", default=False):
                    try:
                        count = await section_edit_svc.db_delete(book_id, section_ids)
                        await svc["session"].flush()
                        console.print(f"Deleted {count} section(s).")
                        modified = True
                        book = await book_service.get_book(book_id)
                        _show_db_sections(book.sections or [])
                    except SectionEditError as e:
                        print_error(str(e))
                continue

            if cmd.action == "merge":
                section_ids = cmd.indices
                if typer.confirm(
                    f"Merge section IDs {section_ids} into one?", default=True
                ):
                    try:
                        merged = await section_edit_svc.db_merge(
                            book_id, section_ids, cmd.title
                        )
                        await svc["session"].flush()
                        console.print(f'Merged into: "{merged.title}"')
                        modified = True
                        book = await book_service.get_book(book_id)
                        _show_db_sections(book.sections or [])
                    except SectionEditError as e:
                        print_error(str(e))
                continue

            if cmd.action == "split":
                section_id = cmd.indices[0]
                try:
                    if cmd.split_mode == "char":
                        parts = await section_edit_svc.db_split_at_char(
                            book_id, section_id, cmd.split_value
                        )
                    else:
                        print_error(
                            "Only --at-char split is available in DB mode. "
                            "Use: split <id> --at-char <pos>"
                        )
                        continue
                    await svc["session"].flush()
                    console.print(f"Split into {len(parts)} sections.")
                    modified = True
                    book = await book_service.get_book(book_id)
                    _show_db_sections(book.sections or [])
                except SectionEditError as e:
                    print_error(str(e))
                continue

            if cmd.action == "move":
                section_id = cmd.indices[0]
                after_id = cmd.target_after if cmd.target_after != 0 else None
                try:
                    await section_edit_svc.db_move(book_id, section_id, after_id)
                    await svc["session"].flush()
                    console.print("Moved.")
                    modified = True
                    book = await book_service.get_book(book_id)
                    _show_db_sections(book.sections or [])
                except SectionEditError as e:
                    print_error(str(e))
                continue

            print_error(f"Unknown command: {cmd.action}")

        if modified:
            summarizer = svc.get("summarizer")
            if summarizer and typer.confirm(
                "\nStructure changed. Re-summarize affected sections?",
                default=False,
            ):
                console.print(
                    f"Run: bookcompanion summarize {book_id} --force "
                    "to regenerate summaries."
                )


def _show_db_sections(sections):
    """Display DB sections as a table."""
    table = Table()
    table.add_column("#", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Chars", justify="right")
    for s in sections:
        status = (
            "[green]Completed[/green]"
            if s.default_summary_id
            else "[yellow]Pending[/yellow]"
        )
        char_count = len(s.content_md) if s.content_md else 0
        table.add_row(
            str(s.order_index + 1),
            str(s.id),
            s.title,
            status,
            f"{char_count:,}",
        )
    console.print(table)
