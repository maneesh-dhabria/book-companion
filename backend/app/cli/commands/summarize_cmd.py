"""bookcompanion summarize command — faceted preset-based summarization."""

import time

import typer
from rich.console import Console

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_error, print_success

console = Console()


@async_command
async def summarize(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID. If omitted, processes all sections."),
    preset: str = typer.Option(None, "--preset", help="Preset name (e.g., practitioner_bullets)."),
    style: str = typer.Option(None, "--style", help="Override style facet."),
    audience: str = typer.Option(None, "--audience", help="Override audience facet."),
    compression: str = typer.Option(None, "--compression", help="Override compression facet."),
    content_focus: str = typer.Option(
        None, "--content-focus", help="Override content focus facet."
    ),
    model: str = typer.Option(None, "--model", help="Override LLM model."),
    force: bool = typer.Option(
        False, "--force", help="Re-summarize all sections, ignoring existing."
    ),
    skip_eval: bool = typer.Option(False, "--skip-eval", help="Skip eval assertions."),
    no_retry: bool = typer.Option(False, "--no-retry", help="Skip auto-retry on eval failure."),
    skip_images: bool = typer.Option(False, "--skip-images", help="Skip image captioning."),
    only_pending: bool = typer.Option(
        False,
        "--only-pending",
        help="Skip sections that already have a default summary (FR-H4.1).",
    ),
):
    """Generate summaries using faceted presets."""
    async with get_services() as svc:
        summarizer = svc.get("summarizer")
        preset_svc = svc.get("preset")
        if not summarizer or not preset_svc:
            print_error("Summarizer or preset service not available.")
            raise typer.Exit(1)

        # Resolve facets
        settings = svc["settings"]
        overrides = {
            "style": style,
            "audience": audience,
            "compression": compression,
            "content_focus": content_focus,
        }
        try:
            resolved_preset, facets = preset_svc.resolve_facets(
                preset, overrides, settings.summarization.default_preset
            )
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from None

        # Validate book
        book_service = svc.get("book_service")
        book = await book_service.get_book(book_id)
        if not book:
            print_error(f"Book {book_id} not found.")
            raise typer.Exit(1)

        if skip_images:
            summarizer.captioner = None

        preset_label = resolved_preset or "custom facets"
        sections = book.sections or []

        # Single section mode
        if section_id is not None:
            section = next((s for s in sections if s.id == section_id), None)
            if not section:
                print_error(f"Section {section_id} not found.")
                raise typer.Exit(1)
            console.print(
                f'Summarizing section #{section_id} "{section.title}" '
                f'with preset "{preset_label}"...'
            )
            start = time.monotonic()
            summary = await summarizer._summarize_single_section(
                book_id=book_id,
                section=section,
                facets=facets,
                preset_name=resolved_preset,
                model=model,
                cumulative_context="",
            )
            await summarizer._section_repo.update_default_summary(section_id, summary.id)
            await svc["session"].commit()
            elapsed = int(time.monotonic() - start)
            comp = (
                summary.summary_char_count / summary.input_char_count * 100
                if summary.input_char_count
                else 0
            )
            console.print(f"  Done ({elapsed}s, {comp:.1f}%)")

            if not skip_eval and svc.get("eval"):
                eval_svc = svc["eval"]
                console.print("Running eval assertions...")
                section_type = getattr(section, "section_type", "chapter")
                eval_results = await eval_svc.evaluate_summary(
                    section_id=section_id,
                    source_text=section.content_md or "",
                    summary_text=summary.summary_md,
                    facets_used=facets,
                    summary_id=summary.id,
                    preset_name=resolved_preset,
                    section_type=section_type,
                )
                from app.services.summarizer.evaluator import EvalService

                summary.eval_json = EvalService.compute_eval_json(eval_results)

                # Auto-retry
                if not no_retry and EvalService._should_retry(eval_results):
                    console.print("  Eval found issues, retrying summary...")
                    fix_prompt = EvalService._build_fix_prompt(eval_results)
                    retry_summary = await summarizer._summarize_single_section(
                        book_id=book_id,
                        section=section,
                        facets=facets,
                        preset_name=resolved_preset,
                        model=model,
                        cumulative_context="",
                        fix_instructions=fix_prompt,
                    )
                    retry_summary.retry_of_id = summary.id
                    await summarizer._section_repo.update_default_summary(
                        section_id, retry_summary.id
                    )
                    # Re-eval
                    retry_eval = await eval_svc.evaluate_summary(
                        section_id=section_id,
                        source_text=section.content_md or "",
                        summary_text=retry_summary.summary_md,
                        facets_used=facets,
                        summary_id=retry_summary.id,
                        preset_name=resolved_preset,
                        section_type=section_type,
                    )
                    retry_summary.eval_json = EvalService.compute_eval_json(retry_eval)
                    console.print("  Retry complete.")

                await svc["session"].commit()
                print_success("Eval complete.")
            return

        # Full book mode
        console.print(f'Summarizing {len(sections)} sections with preset "{preset_label}"...')

        eval_svc = svc.get("eval") if not skip_eval else None
        stats = await summarizer.summarize_book(
            book_id=book_id,
            preset_name=resolved_preset,
            facets=facets,
            force=force,
            model=model,
            skip_eval=skip_eval,
            no_retry=no_retry,
            eval_service=eval_svc,
            only_pending=only_pending,
            on_section_complete=lambda _sid, i, total, title, elapsed, comp: console.print(
                f"  [{i}/{total}] {title[:35]:<35} done  ({elapsed}s, {comp:.1f}%)"
            ),
            on_section_skip=lambda _sid, i, total, title, reason=None: console.print(
                f"  [{i}/{total}] {title[:35]:<35} skipped ({reason or 'already summarized'})"
            ),
            on_section_fail=lambda _sid, i, total, title, err: console.print(
                f"  [{i}/{total}] {title[:35]:<35} FAILED ({err})"
            ),
            on_section_retry=lambda _sid, i, total, title: console.print(
                f"  [{i}/{total}] {title[:35]:<35} retried (eval issues found)"
            ),
        )

        # Book-level summary
        console.print("Generating book-level summary...     ", end="")
        try:
            await summarizer._generate_book_summary(
                book_id,
                facets,
                resolved_preset,
                model,
                eval_service=eval_svc,
                skip_eval=skip_eval,
                no_retry=no_retry,
            )
            await svc["session"].commit()
            console.print("done")
        except Exception as e:
            console.print(f"FAILED ({e})")

        # Final report
        completed = stats.get("completed", 0)
        skipped = stats.get("skipped", 0)
        failed = stats.get("failed", [])
        retried = stats.get("retried", [])
        parts = [f"{completed} section summaries"]
        if not failed:
            parts.append("1 book summary generated")
        if skipped:
            parts.append(f"{skipped} skipped")
        if retried:
            parts.append(f"{len(retried)} retried")
        if failed:
            parts.append(f"{len(failed)} failed")
        print_success(f"Done. {'. '.join(parts)}.")

        if skip_eval:
            console.print(
                f"\n  [dim]Tip: Run bookcompanion eval {book_id} to evaluate quality[/dim]"
            )
