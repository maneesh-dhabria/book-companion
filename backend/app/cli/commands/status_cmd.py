"""bookcompanion status — show processing status for a book."""

import os

import typer
from rich.console import Console
from rich.table import Table

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_empty_state, print_error

console = Console()


@async_command
async def status(
    book_id: int = typer.Argument(..., help="Book ID."),
):
    """Show processing status for a book."""
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

        console.print(f'\n[bold]{book.title}[/bold]')
        console.print(f"Status: {book.status.value if book.status else 'unknown'}")

        # Show processing jobs
        session = svc["session"]
        from sqlalchemy import select

        from app.db.models import ProcessingJob

        result = await session.execute(
            select(ProcessingJob)
            .where(ProcessingJob.book_id == book_id)
            .order_by(ProcessingJob.id.desc())
        )
        jobs = result.scalars().all()

        if jobs:
            table = Table(title="Processing Jobs")
            table.add_column("Step")
            table.add_column("Status")
            table.add_column("PID")
            table.add_column("Started")
            table.add_column("Error")

            for job in jobs:
                # Check if PID is alive
                pid_status = ""
                if job.pid:
                    try:
                        os.kill(job.pid, 0)
                        pid_status = f"{job.pid} [green](alive)[/green]"
                    except OSError:
                        pid_status = f"{job.pid} [red](dead)[/red]"
                else:
                    pid_status = "—"

                status_str = job.status.value if job.status else "unknown"
                if status_str == "running":
                    status_str = f"[yellow]{status_str}[/yellow]"
                elif status_str == "completed":
                    status_str = f"[green]{status_str}[/green]"
                elif status_str == "failed":
                    status_str = f"[red]{status_str}[/red]"

                table.add_row(
                    job.step.value if job.step else "?",
                    status_str,
                    pid_status,
                    str(job.started_at or "—"),
                    (job.error_message or "")[:80],
                )
            console.print(table)
        else:
            print_empty_state(
                f"Book parsed but not yet summarized. "
                f"Run: bookcompanion summarize {book_id}"
            )

        # Show section progress
        sections = book.sections or []
        if sections:
            completed = sum(
                1 for s in sections
                if s.default_summary_id is not None
            )
            total = len(sections)
            console.print(f"\nSection progress: {completed}/{total} summarized")
