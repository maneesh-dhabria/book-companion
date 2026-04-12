"""Health check CLI command — checks DB, migrations, LLM, disk."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.cli.deps import async_command, get_settings

console = Console()


@async_command
async def health(
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed information"),
):
    """Check system health: database, migrations, LLM provider, disk space."""
    settings = get_settings()
    table = Table(title="Book Companion Health Check")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    # Data directory
    data_dir = Path(settings.data.directory)
    table.add_row(
        "Data Directory",
        "[green]OK[/green]" if data_dir.exists() else "[red]Missing[/red]",
        str(data_dir),
    )

    # LLM provider
    from app.services.summarizer import detect_llm_provider

    provider = detect_llm_provider()
    table.add_row(
        "LLM Provider",
        "[green]OK[/green]" if provider else "[yellow]None[/yellow]",
        provider or "No claude/codex CLI found",
    )

    # DB connectivity
    try:
        from app.cli.deps import check_db_health

        db_ok = await check_db_health(settings)
        table.add_row(
            "Database",
            "[green]OK[/green]" if db_ok else "[red]FAIL[/red]",
            settings.database.url.split("@")[-1] if db_ok else "Connection failed",
        )
    except Exception as e:
        table.add_row("Database", "[red]ERROR[/red]", str(e)[:60])

    # Migration status
    try:
        result = subprocess.run(
            ["uv", "run", "alembic", "current"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        is_head = "head" in result.stdout
        table.add_row(
            "Migrations",
            "[green]Current[/green]" if is_head else "[yellow]Behind[/yellow]",
            "At head" if is_head else "Needs migration",
        )
    except Exception as e:
        table.add_row("Migrations", "[yellow]?[/yellow]", str(e)[:60])

    # Disk space
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        table.add_row(
            "Disk Space",
            "[green]OK[/green]" if free_gb > 1 else "[yellow]LOW[/yellow]",
            f"{free_gb:.1f} GB free",
        )
    except Exception:
        table.add_row("Disk Space", "[yellow]?[/yellow]", "Could not check")

    # Web access URL
    host = settings.network.host
    port = settings.network.port
    table.add_row(
        "Web Interface",
        "[cyan]URL[/cyan]",
        f"http://{host}:{port}",
    )

    console.print(table)
