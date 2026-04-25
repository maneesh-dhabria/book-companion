"""CLI commands for export.

bookcompanion export book <id> [--format {json,markdown}] [-o PATH]
                               [--no-book-summary] [--no-toc] [--no-annotations]
                               [--exclude-section ID]...

Flags only valid with --format markdown:
  --no-book-summary    Exclude the book-level summary block from the export.
  --no-toc             Exclude the Table of Contents.
  --no-annotations     Exclude all highlights and notes.
  --exclude-section    Exclude one or more sections by ID (repeatable).

Library Markdown export was removed in v1.6. Use --format json for
full-library backups, or run 'export book' per book.
"""
import typer

from app.cli.deps import async_command, get_services
from app.cli.formatting import console, print_error, print_success
from app.services.export_service import ExportError, ExportSelection

export_app = typer.Typer(help="Export commands.")


@export_app.command("book")
@async_command
async def export_book(
    book_id: int = typer.Argument(..., help="Book ID to export."),
    fmt: str = typer.Option("json", "--format", "-f", help="Export format: json or markdown."),
    output: str = typer.Option(None, "--output", "-o", help="Output file path."),
    no_book_summary: bool = typer.Option(
        False, "--no-book-summary",
        help="Exclude the book-level summary block (markdown only).",
    ),
    no_toc: bool = typer.Option(
        False, "--no-toc",
        help="Exclude the Table of Contents (markdown only).",
    ),
    no_annotations: bool = typer.Option(
        False, "--no-annotations",
        help="Exclude all highlights and notes (markdown only).",
    ),
    exclude_section: list[int] = typer.Option(  # noqa: B008
        None,
        "--exclude-section",
        help="Exclude a section by ID (repeatable; markdown only).",
    ),
):
    """Export a single book's data.

    Flags only valid with --format markdown:
      --no-book-summary, --no-toc, --no-annotations, --exclude-section
    """
    selection_flags_used = (
        no_book_summary or no_toc or no_annotations or bool(exclude_section)
    )
    if fmt == "json" and selection_flags_used:
        print_error(
            "--no-* and --exclude-section flags are only valid with "
            "--format markdown. JSON exports are full-fidelity."
        )
        raise typer.Exit(2)

    async with get_services() as svc:
        try:
            if fmt == "markdown":
                if exclude_section:
                    from sqlalchemy import select

                    from app.db.models import BookSection
                    result = await svc["export"].session.execute(
                        select(BookSection.id).where(BookSection.book_id == book_id)
                    )
                    valid_ids = {row[0] for row in result.all()}
                    for sid in exclude_section:
                        if sid not in valid_ids:
                            print_error(
                                f"section {sid} does not belong to book {book_id}."
                            )
                            raise typer.Exit(1)
                selection = ExportSelection(
                    include_book_summary=not no_book_summary,
                    include_toc=not no_toc,
                    include_annotations=not no_annotations,
                    exclude_section_ids=frozenset(exclude_section or []),
                )
                body, _is_empty = await svc["export"].export_book_markdown(
                    book_id, selection
                )
                if output:
                    from pathlib import Path
                    Path(output).write_text(body, encoding="utf-8")
                    print_success(f"Book exported to {output}")
                else:
                    console.print(body)
            else:
                content = await svc["export"].export_book(
                    book_id, fmt="json", output_path=output
                )
                if output:
                    print_success(f"Book exported to {output}")
                else:
                    console.print(content)
        except ExportError as e:
            print_error(str(e))
            raise typer.Exit(1) from None
        except typer.Exit:
            raise
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from None


@export_app.command("library")
@async_command
async def export_library(
    fmt: str = typer.Option(
        "json", "--format", "-f",
        help="Export format: json (markdown removed in v1.6).",
    ),
    output: str = typer.Option(None, "--output", "-o", help="Output file path."),
):
    """Export the entire library.

    Note: --format markdown was removed in v1.6. Use --format json.
    """
    if fmt == "markdown":
        print_error(
            "Library Markdown export was removed in v1.6 -- use --format json "
            "for full-library backups, or run 'export book' per book."
        )
        raise typer.Exit(2)
    async with get_services() as svc:
        try:
            content = await svc["export"].export_library(fmt=fmt, output_path=output)
            if output:
                print_success(f"Library exported to {output}")
            else:
                console.print(content)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from None
