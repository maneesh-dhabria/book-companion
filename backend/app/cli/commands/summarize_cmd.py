"""bookcompanion summarize & summary commands."""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_empty_state, print_error, print_markdown, print_success

console = Console()


@async_command
async def summarize(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID. If omitted, processes all sections."),
    force: bool = typer.Option(False, "--force", help="Re-summarize all sections, even completed."),
    detail: str = typer.Option(
        "standard", "--detail", help="Detail level: brief, standard, detailed."
    ),
    model: str = typer.Option(None, "--model", help="Override model for this run."),
    skip_eval: bool = typer.Option(
        False, "--skip-eval", help="Skip eval assertions (faster)."
    ),
    skip_images: bool = typer.Option(
        False, "--skip-images", help="Skip image captioning during summarization."
    ),
):
    """Generate or regenerate summaries via LLM."""
    async with get_services() as svc:
        summarizer = svc.get("summarizer")
        if not summarizer:
            print_error("Summarizer service not available. Service layer may not be implemented yet.")
            raise typer.Exit(1)

        if skip_images:
            summarizer.captioner = None

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
            # Summarize single section
            console.print(f'Summarizing section {section_id} of "{book.title}"...')
            try:
                await summarizer.summarize_section(
                    book_id=book_id,
                    section_id=section_id,
                    detail_level=detail,
                    model=model,
                    force=force,
                )
                print_success(f"Section {section_id} summarized.")

                if not skip_eval and svc.get("eval"):
                    console.print("Running eval assertions...")
                    await svc["eval"].evaluate_section(book_id, section_id)
                    print_success("Eval complete.")

                # Index image captions in search
                search_svc = svc.get("search")
                if search_svc:
                    try:
                        section_obj = next(
                            (s for s in (book.sections or []) if s.id == section_id),
                            None,
                        )
                        if section_obj:
                            await search_svc.index_image_captions(
                                section_obj, book_id
                            )
                    except Exception:
                        pass  # Non-blocking
            except Exception as e:
                print_error(f"Summarization failed: {e}")
                raise typer.Exit(1)
        else:
            # Summarize all sections
            sections = book.sections or []
            if not sections:
                print_empty_state(
                    "No sections found. Parse a book first with: bookcompanion add <file>"
                )
                return

            console.print(f'Summarizing "{book.title}" ({len(sections)} sections)...\n')

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Summarizing...", total=len(sections))

                for section in sections:
                    if not force and section.default_summary_id is not None:
                        progress.update(task, advance=1)
                        continue

                    progress.update(
                        task,
                        description=f"Summarizing: {section.title[:50]}...",
                    )

                    try:
                        await summarizer.summarize_section(
                            book_id=book_id,
                            section_id=section.id,
                            detail_level=detail,
                            model=model,
                            force=force,
                        )

                        if not skip_eval and svc.get("eval"):
                            await svc["eval"].evaluate_section(book_id, section.id)

                    except Exception as e:
                        console.print(
                            f"  [yellow]Warning: Section '{section.title}' failed: {e}[/yellow]"
                        )

                    # Report image stats
                    section_images = getattr(section, 'images', None) or []
                    if section_images:
                        key_count = sum(
                            1 for i in section_images
                            if getattr(i, 'relevance', None) == 'key'
                        )
                        supp_count = sum(
                            1 for i in section_images
                            if getattr(i, 'relevance', None) == 'supplementary'
                        )
                        skipped = len(section_images) - key_count - supp_count
                        console.print(
                            f"  [dim]Images: {len(section_images)} found, "
                            f"{key_count} key, {supp_count} supplementary, "
                            f"{skipped} skipped[/dim]"
                        )

                    # Index image captions in search
                    search_svc = svc.get("search")
                    if search_svc and section_images:
                        try:
                            await search_svc.index_image_captions(
                                section, book_id
                            )
                        except Exception:
                            pass  # Non-blocking

                    progress.update(task, advance=1)

            # Generate book-level summary
            console.print("\nGenerating book-level summary...")
            try:
                await summarizer.generate_book_summary(book_id)
                print_success("Book-level summary generated.")
            except Exception as e:
                print_error(f"Book summary failed: {e}")

            print_success(f'\nSummarization of "{book.title}" complete.')


@async_command
async def summary(
    book_id: int = typer.Argument(..., help="Book ID."),
    section_id: int = typer.Argument(None, help="Section ID. If omitted, shows book-level summary."),
    copy: bool = typer.Option(False, "--copy", help="Copy summary to clipboard."),
    export: str = typer.Option(None, "--export", help="Export summary to a file."),
):
    """Display a book or section summary."""
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
            # Section summary
            # TODO: V1.1 — fetch from Summary table via default_summary_id
            sections = [s for s in (book.sections or []) if s.id == section_id]
            if not sections:
                print_error(f"Section {section_id} not found.")
                raise typer.Exit(1)

            section = sections[0]
            if not section.default_summary_id:
                print_empty_state(
                    f"No summary for section '{section.title}' yet. "
                    f"Run: bookcompanion summarize {book_id}"
                )
                return

            # TODO: V1.1 — load summary_md from Summary table
            content = f"## {section.title}\n\n(summary available via Summary table)"
        else:
            # Book-level summary
            # TODO: V1.1 — fetch from Summary table via default_summary_id
            if book.default_summary_id:
                # TODO: V1.1 — load summary_md from Summary table
                content = f"# {book.title}\n\n(summary available via Summary table)"
            elif book.quick_summary:
                content = f"# {book.title} (Quick Summary)\n\n{book.quick_summary}"
            else:
                print_empty_state(
                    f'No summary for "{book.title}" yet. '
                    f"Run: bookcompanion summarize {book_id}"
                )
                return

        print_markdown(content, use_pager=True)

        if copy:
            _copy_to_clipboard(content)

        if export:
            Path(export).write_text(content)
            print_success(f"Exported to {export}")


def _copy_to_clipboard(text: str):
    """Copy text to clipboard."""
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
            print_error("Could not copy to clipboard.")
