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
    summary_id: int = typer.Option(None, "--summary-id", help="Evaluate a specific summary."),
    book_only: bool = typer.Option(False, "--book-only", help="Show only book-level results."),
    force: bool = typer.Option(False, "--force", help="Re-run eval (mark old traces as stale)."),
):
    """Show or run evaluation results."""
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

        # --summary-id mode: evaluate a specific summary
        if summary_id is not None:
            summary_service = svc.get("summary_service")
            eval_service = svc.get("eval")
            if not summary_service:
                print_error("Summary service not available.")
                raise typer.Exit(1)
            if not eval_service:
                print_error("Eval service not available.")
                raise typer.Exit(1)

            try:
                summary = await summary_service.get_by_id(summary_id)
            except Exception as e:
                print_error(str(e))
                raise typer.Exit(1) from None

            # Get source text
            from app.db.models import SummaryContentType

            source_text = ""
            target_section_id = None
            section_type = "chapter"
            if summary.content_type == SummaryContentType.SECTION:
                section = next(
                    (s for s in (book.sections or []) if s.id == summary.content_id),
                    None,
                )
                if section:
                    source_text = section.content_md or ""
                    target_section_id = section.id
                    section_type = getattr(section, "section_type", "chapter")

            # Mark old traces as stale if --force
            if force:
                from app.db.repositories.eval_repo import EvalTraceRepository

                eval_repo = EvalTraceRepository(session)
                await eval_repo.mark_stale_by_summary(summary_id)

            console.print(f"Running eval on summary #{summary_id}...")
            results = await eval_service.evaluate_summary(
                section_id=target_section_id or 0,
                source_text=source_text,
                summary_text=summary.summary_md,
                facets_used=summary.facets_used,
                summary_id=summary.id,
                preset_name=summary.preset_name,
                section_type=section_type,
            )

            from app.services.summarizer.evaluator import EvalService

            summary.eval_json = EvalService.compute_eval_json(results)
            await session.commit()

            # Display results
            _display_eval_results(results, f"Eval Results — Summary #{summary_id}")
            passed = results.get("passed", 0)
            total = results.get("total", 0)
            print_success(f"Eval complete: {passed}/{total} passed.")
            return

        if section_id is not None:
            # Detailed per-assertion results for a section
            from sqlalchemy import select

            from app.db.models import EvalTrace

            query = (
                select(EvalTrace)
                .where(
                    EvalTrace.section_id == section_id,
                    EvalTrace.is_stale.is_(False),
                )
                .order_by(EvalTrace.assertion_category, EvalTrace.assertion_name)
            )
            result = await session.execute(query)
            traces = result.scalars().all()

            if not traces:
                # If --force, run eval now
                if force:
                    eval_service = svc.get("eval")
                    if not eval_service:
                        print_error("Eval service not available.")
                        raise typer.Exit(1)
                    section = next((s for s in (book.sections or []) if s.id == section_id), None)
                    if not section:
                        print_error(f"Section {section_id} not found.")
                        raise typer.Exit(1)
                    if not section.default_summary_id:
                        print_error("Section has no summary. Run summarize first.")
                        raise typer.Exit(1)

                    summary_service = svc.get("summary_service")
                    summary = await summary_service.get_by_id(section.default_summary_id)

                    # Build cumulative context from prior sections
                    sections = book.sections or []
                    cumulative_parts = []
                    for s in sections:
                        if s.order_index >= section.order_index:
                            break
                        if s.default_summary_id:
                            try:
                                prior_summary = await summary_service.get_by_id(
                                    s.default_summary_id
                                )
                                cumulative_parts.append(
                                    f"- {s.title}: {prior_summary.summary_md[:500]}"
                                )
                            except Exception:
                                pass
                    cumulative_context = "\n".join(cumulative_parts) if cumulative_parts else None

                    section_type = getattr(section, "section_type", "chapter")
                    console.print(f"Running eval on section #{section_id}...")
                    results = await eval_service.evaluate_summary(
                        section_id=section_id,
                        source_text=section.content_md or "",
                        summary_text=summary.summary_md,
                        facets_used=summary.facets_used,
                        summary_id=summary.id,
                        preset_name=summary.preset_name,
                        cumulative_context=cumulative_context,
                        section_type=section_type,
                    )
                    from app.services.summarizer.evaluator import EvalService

                    summary.eval_json = EvalService.compute_eval_json(results)
                    await session.commit()
                    _display_eval_results(results, f"Eval Results — Section {section_id}")
                    return

                print_empty_state("No eval results. Run with --force to evaluate now.")
                return

            table = Table(title=f"Eval Results — Section {section_id}")
            table.add_column("Category")
            table.add_column("Assertion")
            table.add_column("Result")
            table.add_column("Reasoning")
            table.add_column("Cause")
            table.add_column("Suggestion")

            for trace in traces:
                if trace.model_used == "skipped":
                    result_str = "[dim]SKIP[/dim]"
                elif trace.passed:
                    result_str = "[green]PASS[/green]"
                else:
                    result_str = "[red]FAIL[/red]"
                table.add_row(
                    trace.assertion_category,
                    trace.assertion_name,
                    result_str,
                    (trace.reasoning or "")[:80],
                    trace.likely_cause or "",
                    (trace.suggestion or "")[:60],
                )
            console.print(table)
        else:
            # Summary across all sections — read eval_json from default summaries
            sections = book.sections or []
            if not sections:
                print_empty_state("No sections found.")
                return

            summary_service = svc.get("summary_service")

            # Show book-level eval if available
            if book.default_summary_id and summary_service:
                try:
                    book_summary = await summary_service.get_by_id(book.default_summary_id)
                    if book_summary.eval_json and isinstance(book_summary.eval_json, dict):
                        _display_eval_results(
                            book_summary.eval_json, f"Book-Level Eval — {book.title}"
                        )
                        console.print()
                except Exception:
                    pass

            if book_only:
                return

            table = Table(title=f"Section Eval Summary — {book.title}")
            table.add_column("Section")
            table.add_column("Pass Rate")
            table.add_column("Status")

            for section in sections:
                if section.default_summary_id and summary_service:
                    try:
                        summary = await summary_service.get_by_id(section.default_summary_id)
                        eval_data = summary.eval_json
                        if eval_data and isinstance(eval_data, dict):
                            passed = eval_data.get("passed", 0)
                            total = eval_data.get("total", 0)
                            rate = f"{passed}/{total}"
                            status = (
                                "[green]Passed[/green]"
                                if passed == total
                                else "[yellow]Partial[/yellow]"
                            )
                        else:
                            rate = "—"
                            status = "[dim]Not evaluated[/dim]"
                    except Exception:
                        rate = "—"
                        status = "[dim]Error loading[/dim]"
                else:
                    rate = "—"
                    status = "[dim]Not evaluated[/dim]"
                table.add_row(section.title[:50], rate, status)
            console.print(table)


def _display_eval_results(results: dict, title: str):
    """Display eval results in a table from the new wrapped format."""
    assertions = results.get("assertions", results)
    table = Table(title=title)
    table.add_column("Assertion")
    table.add_column("Category")
    table.add_column("Result")
    table.add_column("Reasoning")
    table.add_column("Cause")
    table.add_column("Suggestion")

    for name, result in assertions.items():
        if result.get("skipped"):
            result_str = "[dim]SKIP[/dim]"
        elif result.get("error"):
            result_str = "[red]ERROR[/red]"
        elif result.get("passed"):
            result_str = "[green]PASS[/green]"
        else:
            result_str = "[red]FAIL[/red]"
        table.add_row(
            name,
            result.get("category", ""),
            result_str,
            (result.get("reasoning") or "")[:80],
            result.get("likely_cause") or "",
            (result.get("suggestion") or "")[:60],
        )
    console.print(table)
    passed = results.get("passed", sum(1 for r in assertions.values() if r.get("passed")))
    total = results.get("total", len(assertions))
    console.print(f"  {passed}/{total} passed")


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
            await book_service.get_book(book)
        except Exception:
            print_error(f"Book {book} not found.")
            raise typer.Exit(1) from None

        # Get the section
        from sqlalchemy import select

        from app.db.models import BookSection

        session = svc["session"]
        result = await session.execute(select(BookSection).where(BookSection.id == section))
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
            raise typer.Exit(1) from None

        console.print(f"Generating summary with prompt version {prompt_b}...")
        try:
            summary_b = await summarizer.summarize_section(
                book_id=book, section_id=section, detail_level="standard"
            )
        except Exception as e:
            print_error(f"Failed to generate summary B: {e}")
            raise typer.Exit(1) from None

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

                assertions_a = results_a.get("assertions", results_a)
                assertions_b = results_b.get("assertions", results_b)
                for name in assertions_a:
                    pass_a = (
                        "[green]PASS[/green]"
                        if assertions_a[name].get("passed")
                        else "[red]FAIL[/red]"
                    )
                    pass_b = (
                        "[green]PASS[/green]"
                        if assertions_b.get(name, {}).get("passed")
                        else "[red]FAIL[/red]"
                    )
                    table.add_row(name, pass_a, pass_b)

                console.print(table)
            except Exception as e:
                print_error(f"Eval comparison failed: {e}")
