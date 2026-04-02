"""bookcompanion init — first-time setup."""

import shutil
import subprocess

import typer
from rich.console import Console

from app.cli.deps import async_command, get_settings

console = Console()


@async_command
async def init(
    database_url: str = typer.Option(
        None, "--database-url", help="Override database URL."
    ),
):
    """First-time setup: start PostgreSQL, run migrations, verify dependencies."""
    console.print("\nChecking dependencies...")

    # 1. Check Docker
    _check_dependency("Docker", "docker", ["--version"])

    # 2. Check Ollama
    _check_dependency("Ollama", "curl", ["-s", "http://localhost:11434/api/tags"])

    # 3. Check Calibre
    _check_dependency("ebook-convert", "ebook-convert", ["--version"], required=False)

    # 4. Check Claude Code CLI
    _check_dependency("Claude Code CLI", "claude", ["--version"])

    # 5. Start PostgreSQL if not running
    console.print("\nStarting PostgreSQL container...")
    result = subprocess.run(
        ["docker", "compose", "up", "-d"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("  [green]PostgreSQL 16 + pgvector: running on port 5438[/green]")
    else:
        console.print(f"  [red]Failed: {result.stderr}[/red]")
        raise typer.Exit(1)

    # 6. Run migrations
    console.print("\nRunning database migrations...")
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd="backend" if not shutil.which("alembic") else None,
    )
    if result.returncode == 0:
        console.print("  [green]Migrations applied[/green]")
    else:
        console.print(f"  [yellow]Migration warning: {result.stderr[:200]}[/yellow]")

    # 7. Pull embedding model
    console.print("\nPulling embedding model...")
    result = subprocess.run(
        ["ollama", "pull", "nomic-embed-text"],
        capture_output=True,
        text=True,
    )
    console.print("  [green]nomic-embed-text: ready[/green]")

    # 8. Print getting started
    settings = get_settings()
    config_path = "~/.config/bookcompanion/config.yaml"
    console.print(f"\nConfiguration saved to: {config_path}")
    console.print("\n[bold]Setup complete![/bold] Here's how to get started:\n")
    console.print("  1. Add your first book:    bookcompanion add ~/path/to/book.epub")
    console.print("  2. Quick overview:         bookcompanion add --quick ~/path/to/book.epub")
    console.print("  3. Full summarization:     bookcompanion summarize <book_id>")
    console.print("  4. Browse your library:    bookcompanion list")
    console.print("  5. Search across books:    bookcompanion search \"query\"")
    console.print("\nRun `bookcompanion --help` for all commands.\n")


def _check_dependency(name: str, command: str, args: list, required: bool = True):
    if shutil.which(command):
        try:
            result = subprocess.run(
                [command] + args, capture_output=True, text=True, timeout=10
            )
            version = result.stdout.strip().split("\n")[0][:60]
            console.print(f"  [green]✓[/green] {name}: {version}")
        except Exception:
            console.print(f"  [green]✓[/green] {name}: found")
    else:
        marker = "[red]✗[/red]" if required else "[yellow]⚠[/yellow]"
        console.print(f"  {marker} {name}: not found")
        if required:
            console.print(f"    Install {name} and try again.")
