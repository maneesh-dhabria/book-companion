"""bookcompanion serve — start the web server."""

import socket
from pathlib import Path

import typer
import uvicorn
from rich.console import Console

from app.cli.deps import get_settings

console = Console()


def serve(
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
):
    """Start the Book Companion web server."""
    settings = get_settings()
    data_dir = Path(settings.data.directory)
    db_path = data_dir / "library.db"

    # Auto-init if no database exists
    if not db_path.exists():
        console.print("[yellow]First run detected, initializing...[/yellow]")
        import asyncio

        from app.cli.commands.init_cmd import init

        asyncio.run(init.wrapped())  # Call the unwrapped async function

    console.print(f"\n[bold]Book Companion[/bold] — serving at http://localhost:{port}")

    # Show LAN IP if available
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                console.print(f"  Also available at: http://{ip}:{port}")
                break
    except Exception:
        pass

    console.print()
    uvicorn.run("app.api.main:app", host=host, port=port)
