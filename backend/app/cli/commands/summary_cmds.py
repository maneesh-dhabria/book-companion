"""bookcompanion summary — summary log commands."""

import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_empty_state, print_error, print_markdown, print_success
from app.db.models import SummaryContentType

summary_app = typer.Typer(help="Summary management commands.")
console = Console()


def _format_eval(eval_json: dict | None) -> str:
    if not eval_json or not isinstance(eval_json, dict):
        return "-"
    passed = eval_json.get("passed", 0)
    total = eval_json.get("total", 0)
    return f"{passed}/{total}"


@summary_app.callback(invoke_without_command=True)
def summary_callback(ctx: typer.Context):
    """Summary management. Use subcommands or: bookcompanion summary read <book_id>"""
    if ctx.invoked_subcommand is None:
        console.print("Usage: bookcompanion summary <command>")
        console.print("Commands: read, list, compare, set-default, show")
        console.print("\nRun: bookcompanion summary --help")


@summary_app.command("read")
@async_command
async def summary_read(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID (optional)."),
):
    """Read the default summary for a book or section."""
    async with get_services() as svc:
        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        if section_id is not None:
            section = next((s for s in (book.sections or []) if s.id == section_id), None)
            if not section:
                print_error(f"Section {section_id} not found.")
                raise typer.Exit(1)
            if not section.default_summary_id:
                preset = svc["settings"].summarization.default_preset
                print_empty_state(
                    f'No summary for section #{section_id} "{section.title}".\n'
                    f"Run: bookcompanion summarize {book_id} --preset {preset}"
                )
                return
            summary = await summary_service.get_by_id(section.default_summary_id)
            content = f"## {section.title}\n\n{summary.summary_md}"
        else:
            if not book.default_summary_id:
                preset = svc["settings"].summarization.default_preset
                print_empty_state(
                    f'No summary for "{book.title}".\n'
                    f"Run: bookcompanion summarize {book_id} --preset {preset}"
                )
                return
            summary = await summary_service.get_by_id(book.default_summary_id)
            content = f"# {book.title}\n\n{summary.summary_md}"

        print_markdown(content, use_pager=True)


@summary_app.command("list")
@async_command
async def summary_list(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID for detailed list."),
    book_level: bool = typer.Option(False, "--book-level", help="Show book-level summaries only."),
):
    """List summaries for a book or section."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        book_service = svc.get("book_service")
        if not summary_service or not book_service:
            print_error("Required services not available.")
            raise typer.Exit(1)

        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        if book_level:
            summaries = await summary_service.list_book_level(book_id)
            table = Table(title=f'Book-level summaries -- "{book.title}"')
            table.add_column("ID")
            table.add_column("Preset")
            table.add_column("Model")
            table.add_column("Compression")
            table.add_column("Chars")
            table.add_column("Eval")
            table.add_column("Created")
            for s in summaries:
                comp = (
                    f"{s.summary_char_count / s.input_char_count * 100:.1f}%"
                    if s.input_char_count
                    else "-"
                )
                default_marker = " *" if book.default_summary_id == s.id else ""
                table.add_row(
                    str(s.id) + default_marker,
                    s.preset_name or "-",
                    s.model_used,
                    comp,
                    f"{s.summary_char_count:,}",
                    _format_eval(s.eval_json),
                    str(s.created_at.strftime("%Y-%m-%d %H:%M")),
                )
            console.print(table)
            return

        if section_id is not None:
            summaries = await summary_service.list_for_content(
                SummaryContentType.SECTION, section_id
            )
            section = next((s for s in (book.sections or []) if s.id == section_id), None)
            title = section.title if section else f"Section {section_id}"
            table = Table(title=f'Section "{title}" -- {len(summaries)} summaries')
            table.add_column("ID")
            table.add_column("Preset")
            table.add_column("Model")
            table.add_column("Chars")
            table.add_column("Eval")
            table.add_column("Created")
            for s in summaries:
                default_marker = " *" if section and section.default_summary_id == s.id else ""
                table.add_row(
                    str(s.id) + default_marker,
                    s.preset_name or "-",
                    s.model_used,
                    f"{s.summary_char_count:,}",
                    _format_eval(s.eval_json),
                    str(s.created_at.strftime("%Y-%m-%d %H:%M")),
                )
            console.print(table)
        else:
            sections = book.sections or []
            all_summaries = await summary_service.list_for_book(book_id)
            section_counts: dict[int, int] = {}
            for s in all_summaries:
                if s.content_type == SummaryContentType.SECTION:
                    section_counts[s.content_id] = section_counts.get(s.content_id, 0) + 1
            book_summaries = [s for s in all_summaries if s.content_type == SummaryContentType.BOOK]
            total_count = sum(section_counts.values())

            console.print(
                f'Book: "{book.title}" -- {total_count} section summaries '
                f"across {len(sections)} sections\n"
            )
            table = Table()
            table.add_column("#")
            table.add_column("ID")
            table.add_column("Title")
            table.add_column("Summaries")
            for i, section in enumerate(sections, 1):
                count = section_counts.get(section.id, 0)
                indent = "  " * section.depth
                table.add_row(str(i), str(section.id), f"{indent}{section.title}", str(count))
            console.print(table)

            if book_summaries:
                console.print(f"\n  Book-level summaries: {len(book_summaries)}")


@summary_app.command("show")
@async_command
async def summary_show(
    summary_id: int = typer.Argument(..., help="Summary ID."),
):
    """Show full details for a specific summary."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        try:
            summary = await summary_service.get_by_id(summary_id)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from None

        console.print(f"[bold]Summary #{summary.id}[/bold]")
        console.print(f"Content type: {summary.content_type.value}")
        console.print(f"Content ID: {summary.content_id}")
        console.print(f"Preset: {summary.preset_name or '-'}")
        console.print(f"Model: {summary.model_used}")
        comp = (
            f"{summary.summary_char_count / summary.input_char_count * 100:.1f}%"
            if summary.input_char_count
            else "-"
        )
        console.print(f"Compression: {comp}")
        console.print(f"Input chars: {summary.input_char_count:,}")
        console.print(f"Summary chars: {summary.summary_char_count:,}")
        console.print(f"Eval: {_format_eval(summary.eval_json)}")
        console.print(f"Created: {summary.created_at}")
        console.print()
        print_markdown(summary.summary_md, use_pager=True)


@summary_app.command("compare")
@async_command
async def summary_compare(
    summary_a_id: int = typer.Argument(..., help="First summary ID."),
    summary_b_id: int = typer.Argument(..., help="Second summary ID."),
):
    """Compare two summaries side-by-side with concept diff."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        try:
            summary_a = await summary_service.get_by_id(summary_a_id)
            summary_b = await summary_service.get_by_id(summary_b_id)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from None

        # Metadata comparison table
        table = Table(title="Summary Comparison")
        table.add_column("Field")
        table.add_column(f"#{summary_a.id}")
        table.add_column(f"#{summary_b.id}")

        table.add_row("Preset", summary_a.preset_name or "-", summary_b.preset_name or "-")
        table.add_row("Model", summary_a.model_used, summary_b.model_used)
        table.add_row(
            "Chars",
            f"{summary_a.summary_char_count:,}",
            f"{summary_b.summary_char_count:,}",
        )
        table.add_row("Eval", _format_eval(summary_a.eval_json), _format_eval(summary_b.eval_json))
        console.print(table)

        # Concept diff
        diff = summary_service.concept_diff(summary_a, summary_b)
        if diff["only_in_a"] or diff["only_in_b"]:
            console.print("\n[bold]Concept Diff[/bold]")
            if diff["only_in_a"]:
                console.print(f"  Only in #{summary_a.id}: {', '.join(sorted(diff['only_in_a']))}")
            if diff["only_in_b"]:
                console.print(f"  Only in #{summary_b.id}: {', '.join(sorted(diff['only_in_b']))}")
            if diff["shared"]:
                console.print(f"  Shared: {len(diff['shared'])} concepts")

        # Side-by-side panels
        console.print()
        panels = Columns(
            [
                Panel(
                    summary_a.summary_md[:3000],
                    title=f"#{summary_a.id} ({summary_a.preset_name or 'no preset'})",
                ),
                Panel(
                    summary_b.summary_md[:3000],
                    title=f"#{summary_b.id} ({summary_b.preset_name or 'no preset'})",
                ),
            ],
            equal=True,
        )
        console.print(panels)


@summary_app.command("set-default")
@async_command
async def summary_set_default(
    summary_id: int = typer.Argument(..., help="Summary ID to set as default."),
):
    """Set a summary as the default for its book or section."""
    async with get_services() as svc:
        summary_service = svc.get("summary_service")
        if not summary_service:
            print_error("Summary service not available.")
            raise typer.Exit(1)

        try:
            summary = await summary_service.set_default(summary_id)
            await svc["session"].commit()
            print_success(
                f"Summary #{summary_id} set as default for "
                f"{summary.content_type.value} #{summary.content_id}."
            )
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from None
