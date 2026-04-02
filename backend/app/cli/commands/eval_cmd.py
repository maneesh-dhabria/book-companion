"""bookcompanion eval — show evaluation results."""

import typer
from rich.console import Console
from rich.table import Table

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_empty_state, print_error, print_success

console = Console()

eval_app = typer.Typer(help="Evaluation commands.")


@async_command
async def eval_cmd(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID for detailed results."),
):
    """Show evaluation results."""
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

        session = svc["session"]

        if section_id is not None:
            # Detailed per-assertion results for a section
            from sqlalchemy import select

            from app.db.models import EvalTrace

            result = await session.execute(
                select(EvalTrace)
                .where(EvalTrace.section_id == section_id)
                .order_by(EvalTrace.assertion_category, EvalTrace.assertion_name)
            )
            traces = result.scalars().all()

            if not traces:
                print_empty_state("No eval results. Summaries must be generated first.")
                return

            table = Table(title=f"Eval Results — Section {section_id}")
            table.add_column("Category")
            table.add_column("Assertion")
            table.add_column("Result")
            table.add_column("Reasoning")

            for trace in traces:
                result_str = "[green]PASS[/green]" if trace.passed else "[red]FAIL[/red]"
                table.add_row(
                    trace.assertion_category,
                    trace.assertion_name,
                    result_str,
                    (trace.reasoning or "")[:100],
                )
            console.print(table)
        else:
            # Summary across all sections
            sections = book.sections or []
            if not sections:
                print_empty_state("No sections found.")
                return

            has_evals = any(s.summary_eval for s in sections)
            if not has_evals:
                print_empty_state(
                    f"No eval results for \"{book.title}\". "
                    f"Run: bookcompanion summarize {book_id}"
                )
                return

            table = Table(title=f"Eval Summary — {book.title}")
            table.add_column("Section")
            table.add_column("Pass Rate")
            table.add_column("Status")

            for section in sections:
                eval_data = section.summary_eval
                if eval_data and isinstance(eval_data, dict):
                    passed = eval_data.get("passed", 0)
                    total = eval_data.get("total", 0)
                    rate = f"{passed}/{total}"
                    status = "[green]OK[/green]" if passed == total else "[yellow]Issues[/yellow]"
                else:
                    rate = "—"
                    status = "[dim]Not evaluated[/dim]"

                table.add_row(section.title[:50], rate, status)
            console.print(table)


@eval_app.command("compare-prompts")
@async_command
async def compare_prompts(
    book: int = typer.Option(..., "--book", help="Book ID."),
    section: int = typer.Option(..., "--section", help="Section ID."),
    prompt_a: str = typer.Option(..., "--prompt-a", help="Prompt version A (e.g., v1)."),
    prompt_b: str = typer.Option(..., "--prompt-b", help="Prompt version B (e.g., v2)."),
):
    """Compare summaries from two prompt versions side-by-side. (Phase 2)"""
    async with get_services() as svc:
        summarizer = svc.get("summarizer")
        eval_service = svc.get("eval")

        if not summarizer:
            print_error("Summarizer service not available.")
            raise typer.Exit(1)

        book_service = svc.get("book_service")
        if not book_service:
            print_error("Book service not available.")
            raise typer.Exit(1)

        try:
            book_obj = await book_service.get_book(book)
        except Exception:
            print_error(f"Book {book} not found.")
            raise typer.Exit(1)

        # Get the section
        from sqlalchemy import select
        from app.db.models import BookSection

        session = svc["session"]
        result = await session.execute(
            select(BookSection).where(BookSection.id == section)
        )
        section_obj = result.scalar_one_or_none()
        if not section_obj:
            print_error(f"Section {section} not found.")
            raise typer.Exit(1)

        console.print(f"Generating summary with prompt version {prompt_a}...")
        try:
            summary_a = await summarizer.summarize_section(
                book_id=book, section_id=section, detail_level="standard"
            )
        except Exception as e:
            print_error(f"Failed to generate summary A: {e}")
            raise typer.Exit(1)

        console.print(f"Generating summary with prompt version {prompt_b}...")
        try:
            summary_b = await summarizer.summarize_section(
                book_id=book, section_id=section, detail_level="standard"
            )
        except Exception as e:
            print_error(f"Failed to generate summary B: {e}")
            raise typer.Exit(1)

        # Display side-by-side
        from rich.columns import Columns
        from rich.panel import Panel

        cols = Columns(
            [
                Panel(summary_a[:3000], title=f"Prompt {prompt_a}"),
                Panel(summary_b[:3000], title=f"Prompt {prompt_b}"),
            ],
            equal=True,
        )
        console.print(cols)

        # Run eval on both if eval service available
        if eval_service:
            console.print("\nRunning eval on both summaries...")
            source_text = section_obj.content_md or ""

            table = Table(title="Eval Comparison")
            table.add_column("Assertion")
            table.add_column(f"Prompt {prompt_a}")
            table.add_column(f"Prompt {prompt_b}")

            try:
                results_a = await eval_service.evaluate_summary(section, source_text, summary_a)
                results_b = await eval_service.evaluate_summary(section, source_text, summary_b)

                for name in results_a:
                    pass_a = "[green]PASS[/green]" if results_a[name].get("passed") else "[red]FAIL[/red]"
                    pass_b = "[green]PASS[/green]" if results_b.get(name, {}).get("passed") else "[red]FAIL[/red]"
                    table.add_row(name, pass_a, pass_b)

                console.print(table)
            except Exception as e:
                print_error(f"Eval comparison failed: {e}")
