"""Book Companion CLI — Typer app entry point."""

import typer
from rich.console import Console

from app import __version__

app = typer.Typer(
    name="bookcompanion",
    help="Book Companion - Personal book summarization and knowledge extraction tool.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"bookcompanion {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=version_callback, is_eager=True
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose (DEBUG) logging."),
    format: str = typer.Option("text", "--format", help="Output format: text (default) or json."),
    no_pager: bool = typer.Option(False, "--no-pager", help="Disable pager for long output."),
):
    """Book Companion CLI."""
    from app.cli.formatting import set_output_format

    set_output_format(format)

    settings = None
    try:
        from app.cli.deps import get_settings

        settings = get_settings()
        if verbose:
            settings.logging.level = "DEBUG"
    except Exception:
        pass

    # Spec requirement: on every CLI invocation, check for orphaned background processes
    if settings:
        try:
            import asyncio

            from app.cli.deps import check_orphaned_processes

            asyncio.run(check_orphaned_processes(settings))
        except Exception:
            pass  # Non-critical

        # Spec requirement: auto-check migrations on every CLI invocation
        try:
            from app.cli.deps import auto_check_migrations

            auto_check_migrations(settings)
        except Exception:
            pass  # Non-critical


# Import and register Phase 1 command modules
from app.cli.commands import (
    books,
    config_cmd,
    eval_cmd,
    init_cmd,
    search_cmd,
    status_cmd,
    summarize_cmd,
)

app.command("init")(init_cmd.init)
app.command("add")(books.add)
app.command("list")(books.list_books)
app.command("show")(books.show)
app.command("delete")(books.delete)
app.command("read")(books.read)
app.command("authors")(books.authors)
app.command("summary")(summarize_cmd.summary)
app.command("summarize")(summarize_cmd.summarize)
app.command("search")(search_cmd.search)
app.command("eval")(eval_cmd.eval_cmd)
app.add_typer(eval_cmd.eval_app, name="eval-compare", help="Eval comparison commands. (Phase 2)")
app.command("status")(status_cmd.status)
app.add_typer(config_cmd.config_app, name="config")


# Import and register Phase 2 command modules
from app.cli.commands.annotations_cmd import annotations_app
from app.cli.commands.backup_cmd import backup_app
from app.cli.commands.concepts_cmd import concepts_app
from app.cli.commands.edit_cmd import edit_app
from app.cli.commands.export_cmd import export_app
from app.cli.commands.references_cmd import references_app
from app.cli.commands.tags_cmd import tags_app

app.add_typer(annotations_app, name="annotate", help="Create and list annotations. (Phase 2)")
app.add_typer(tags_app, name="tag", help="Add and manage tags. (Phase 2)")
app.add_typer(concepts_app, name="concepts", help="Browse and search concepts index. (Phase 2)")
app.add_typer(export_app, name="export", help="Export library data. (Phase 2)")
app.add_typer(backup_app, name="backup", help="Backup and restore database. (Phase 2)")
app.add_typer(references_app, name="references", help="External reference commands. (Phase 2)")
app.add_typer(edit_app, name="edit", help="Edit metadata and summaries. (Phase 2)")


if __name__ == "__main__":
    app()
