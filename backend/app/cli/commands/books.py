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


def _display_section_table(sections, title="Sections"):
    """Display a table of SectionItem objects (used by REPL)."""
    table = Table(title=title)
    table.add_column("#", style="cyan")
    table.add_column("Title")
    table.add_column("Depth", justify="right")
    table.add_column("Chars", justify="right")
    for s in sections:
        table.add_row(str(s.index), s.title, str(s.depth), f"{s.char_count:,}")
    console.print(table)


def _run_edit_repl(edit_service):
    """Run the interactive section editing REPL. Returns True if user finished with 'done'."""
    from app.exceptions import SectionEditError
    from app.services.section_edit_service import parse_command

    console.print(
        "\n[bold]Section Editor[/bold] — commands: "
        "show, merge 1,2 [\"title\"], split <n> --at-heading, "
        "delete 1,2, move <n> --after <m>, undo, done"
    )

    while True:
        try:
            raw = typer.prompt("edit>", default="done")
        except (KeyboardInterrupt, EOFError):
            console.print("\nAborted.")
            return False

        try:
            cmd = parse_command(raw)
        except SectionEditError as e:
            print_error(str(e))
            continue

        if cmd.action == "done":
            return True

        if cmd.action == "show":
            _display_section_table(edit_service.get_sections())
            continue

        if cmd.action == "undo":
            if edit_service.undo():
                console.print("Undone.")
                _display_section_table(edit_service.get_sections())
            else:
                console.print("Nothing to undo.")
            continue

        if cmd.action == "delete":
            try:
                count = edit_service.delete(cmd.indices)
                console.print(f"Deleted {count} section(s).")
                _display_section_table(edit_service.get_sections())
            except SectionEditError as e:
                print_error(str(e))
            continue

        if cmd.action == "merge":
            try:
                merged = edit_service.merge(cmd.indices, cmd.title)
                console.print(f'Merged into: "{merged.title}" ({merged.char_count:,} chars)')
                _display_section_table(edit_service.get_sections())
            except SectionEditError as e:
                print_error(str(e))
            continue

        if cmd.action == "split":
            try:
                if cmd.split_mode == "heading":
                    parts = edit_service.split_at_headings(cmd.indices[0])
                elif cmd.split_mode == "char":
                    parts = edit_service.split_at_char(cmd.indices[0], cmd.split_value)
                elif cmd.split_mode == "paragraph":
                    parts = edit_service.split_at_paragraph(cmd.indices[0], cmd.split_value)
                else:
                    print_error(f"Unknown split mode: {cmd.split_mode}")
                    continue
                console.print(f"Split into {len(parts)} sections.")
                _display_section_table(edit_service.get_sections())
            except SectionEditError as e:
                print_error(str(e))
            continue

        if cmd.action == "move":
            try:
                edit_service.move(cmd.indices[0], cmd.target_after or 0)
                console.print("Moved.")
                _display_section_table(edit_service.get_sections())
            except SectionEditError as e:
                print_error(str(e))
            continue

        print_error(f"Unknown command: {cmd.action}")


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

            # Quality checks on detected sections
            quality_svc = svc.get("quality")
            issues = []
            if quality_svc:
                section_dicts = [
                    {
                        "index": s.order_index,
                        "title": s.title,
                        "content": s.content_md or "",
                        "depth": s.depth,
                        "image_count": len(s.images) if s.images else 0,
                    }
                    for s in (book.sections or [])
                ]
                issues = quality_svc.check_sections(section_dicts)

                if issues:
                    console.print(f"\n[yellow]Quality issues ({len(issues)}):[/yellow]")
                    for issue in issues:
                        severity_style = {
                            "error": "red",
                            "warning": "yellow",
                            "info": "dim",
                        }.get(issue.severity, "")
                        console.print(
                            f"  [{severity_style}]{issue.severity.upper()}[/{severity_style}] "
                            f"Section {issue.section_index}: {issue.message}"
                        )

                    actions = quality_svc.suggested_actions(issues)
                    if actions:
                        console.print("\n[bold]Suggested actions:[/bold]")
                        for action in actions:
                            console.print(f"  - {action}")

                        choice = typer.prompt(
                            "\nApply suggested actions? [Y/n/customize]",
                            default="Y",
                        ).strip().lower()

                        if choice == "y":
                            # Auto-delete non-content sections
                            delete_indices = [
                                i.section_index
                                for i in issues
                                if i.suggested_action == "delete"
                                and i.severity in ("error", "warning")
                            ]
                            if delete_indices:
                                section_edit_svc = svc.get("section_edit")
                                if section_edit_svc:
                                    # Map order_index to section IDs
                                    idx_to_id = {
                                        s.order_index: s.id
                                        for s in (book.sections or [])
                                    }
                                    ids_to_delete = [
                                        idx_to_id[idx]
                                        for idx in delete_indices
                                        if idx in idx_to_id
                                    ]
                                    if ids_to_delete:
                                        count = await section_edit_svc.db_delete(
                                            book.id, ids_to_delete
                                        )
                                        await svc["session"].flush()
                                        console.print(
                                            f"Deleted {count} non-content section(s)."
                                        )
                                        # Reload book
                                        book = await book_service.get_book(book.id)
                                        section_count = (
                                            len(book.sections) if book.sections else 0
                                        )

                        elif choice == "customize":
                            # Enter interactive REPL with in-memory mode
                            section_edit_svc = svc.get("section_edit")
                            if section_edit_svc:
                                from app.services.section_edit_service import SectionItem

                                items = [
                                    SectionItem(
                                        index=s.order_index + 1,
                                        id=s.id,
                                        title=s.title,
                                        content=s.content_md or "",
                                        depth=s.depth,
                                        char_count=len(s.content_md or ""),
                                    )
                                    for s in (book.sections or [])
                                ]
                                section_edit_svc.init_memory_mode(items)
                                _display_section_table(items)

                                if _run_edit_repl(section_edit_svc):
                                    # Apply edits back to DB
                                    final_sections = section_edit_svc.get_sections()
                                    original_ids = {s.id for s in (book.sections or [])}
                                    final_ids = {
                                        s.id for s in final_sections if s.id is not None
                                    }

                                    # Delete removed sections
                                    removed_ids = [
                                        sid
                                        for sid in original_ids
                                        if sid not in final_ids and sid is not None
                                    ]
                                    if removed_ids:
                                        from app.db.repositories.section_repo import (
                                            SectionRepository,
                                        )

                                        repo = SectionRepository(svc["session"])
                                        await repo.delete_by_ids(removed_ids)

                                    # Create new sections (merged/split - id is None)
                                    from app.db.models import BookSection

                                    for item in final_sections:
                                        if item.id is None:
                                            new_section = BookSection(
                                                book_id=book.id,
                                                title=item.title,
                                                order_index=item.index - 1,
                                                depth=item.depth,
                                                content_md=item.content,
                                                content_token_count=item.char_count // 4,
                                                derived_from=item.derived_from,
                                            )
                                            svc["session"].add(new_section)

                                    await svc["session"].flush()

                                    # Reindex
                                    from app.db.repositories.section_repo import (
                                        SectionRepository,
                                    )

                                    repo = SectionRepository(svc["session"])
                                    await repo.reindex_order(book.id)

                                    # Reload
                                    book = await book_service.get_book(book.id)
                                    section_count = (
                                        len(book.sections) if book.sections else 0
                                    )
                                    console.print(
                                        f"Applied edits. {section_count} sections."
                                    )
                            else:
                                console.print(
                                    "Section edit service not available."
                                )
                        # else 'n' — accept as-is

            if not issues and not typer.confirm(
                "\nAccept this structure?", default=True
            ):
                console.print(
                    "Structure rejected. Use --force to re-import with different parsing."
                )
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

        # Quality check
        quality_svc = svc.get("quality")
        if quality_svc and book.sections:
            section_dicts = [
                {
                    "index": s.order_index,
                    "title": s.title,
                    "content": s.content_md or "",
                    "depth": s.depth,
                    "image_count": len(s.images) if s.images else 0,
                }
                for s in book.sections
            ]
            issues = quality_svc.check_sections(section_dicts)
            ok_count = len(book.sections) - len(
                {i.section_index for i in issues if i.severity in ("error", "warning")}
            )
            warning_count = len(issues)
            console.print(
                f"Quality: {ok_count}/{len(book.sections)} sections OK. "
                f"{warning_count} warning(s)"
            )

        if book.sections:
            # Determine terminal width for adaptive columns
            term_width = console.width or 80
            wide_mode = term_width >= 100

            console.print(f"\n[bold]Sections ({len(book.sections)}):[/bold]")
            table = Table()
            table.add_column("#", style="cyan")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Status")
            table.add_column("Chars", justify="right")
            if wide_mode:
                table.add_column("Compression", justify="right")
                table.add_column("Eval", justify="right")

            # Pre-fetch summaries for compression/eval if wide mode
            summary_service = svc.get("summary_service") if wide_mode else None

            for section in book.sections:
                summary_status = (
                    "[green]Completed[/green]"
                    if section.default_summary_id
                    else "[yellow]Pending[/yellow]"
                )
                char_count = len(section.content_md) if section.content_md else 0

                row = [
                    str(section.order_index + 1),
                    str(section.id),
                    section.title,
                    summary_status,
                    f"{char_count:,}",
                ]

                if wide_mode:
                    compression = "-"
                    eval_display = "-"
                    if section.default_summary_id and summary_service:
                        try:
                            summary = await summary_service.get_by_id(
                                section.default_summary_id
                            )
                            if summary and summary.summary_md and char_count > 0:
                                ratio = len(summary.summary_md) / char_count
                                compression = f"{ratio:.0%}"
                            if summary and summary.eval_json:
                                passed = sum(
                                    1
                                    for v in summary.eval_json.values()
                                    if v is True
                                )
                                total = len(summary.eval_json)
                                eval_display = f"{passed}/{total}"
                        except Exception:
                            pass
                    row.extend([compression, eval_display])

                table.add_row(*row)
            console.print(table)


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
            # TODO: V1.1 — with_summary should load from Summary table
            if with_summary and section.default_summary_id:
                from rich.columns import Columns
                from rich.panel import Panel

                cols = Columns(
                    [
                        Panel(content[:2000], title=f"{section.title} — Content"),
                        Panel("(summary in Summary table)", title=f"{section.title} — Summary"),
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
