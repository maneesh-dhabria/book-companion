"""bookcompanion serve — start the web server."""

import os
import socket
import subprocess
from pathlib import Path

import typer
import uvicorn
from rich.console import Console

from app.api.static_files import _assets_present, _resolve_static_dir
from app.cli.deps import get_settings

console = Console()


DEV_MODE_ERROR = """\
Frontend assets not found at {path}.

This usually means you're running from a cloned repo without a built frontend.
Two valid workflows:

  1. Build the SPA once, then run the server:
       cd frontend && npm install && npm run build
       bookcompanion serve

  2. Run API-only and use the Vite dev server for the UI:
       bookcompanion serve --api-only
       (in another terminal) cd frontend && npm run dev
       open http://localhost:5173

Or pass --api-only to suppress this check.
"""

INSTALLED_MODE_ERROR = """\
Frontend assets missing from the installed package at {path}.
This is a packaging bug — please report it with your installed version
(bookcompanion --version) and platform.

Running with --api-only will start the API without the web UI.
"""


def _is_installed_mode(static_dir: Path | None = None) -> bool:
    """Distinguish installed (site-packages) vs dev (source checkout) mode."""
    path = static_dir if static_dir is not None else _resolve_static_dir()
    return "site-packages" in path.resolve().parts


def _auto_init_if_needed(settings) -> None:
    db_path = Path(settings.data.directory) / "library.db"
    if not db_path.exists():
        console.print("[yellow]First run detected, initializing...[/yellow]")
        subprocess.run(["bookcompanion", "init"], check=False)


def serve(
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    api_only: bool = typer.Option(
        False,
        "--api-only/--no-api-only",
        help=(
            "Start only the JSON API; do not require or mount the Vue SPA. "
            "Also settable via BOOKCOMPANION_API_ONLY=1."
        ),
    ),
) -> None:
    """Start the Book Companion web server."""
    if not api_only and os.environ.get("BOOKCOMPANION_API_ONLY", "") not in (
        "",
        "0",
        "false",
        "False",
    ):
        api_only = True

    settings = get_settings()
    _auto_init_if_needed(settings)

    if not api_only and not _assets_present():
        static_dir = _resolve_static_dir()
        if _is_installed_mode(static_dir):
            msg = INSTALLED_MODE_ERROR.format(path=static_dir)
        else:
            msg = DEV_MODE_ERROR.format(path=static_dir)
        console.print(msg, style="red")
        raise typer.Exit(code=1)

    if api_only:
        console.print("[yellow]Running in API-only mode; no static assets mounted at /.[/yellow]")

    console.print(f"\n[bold]Book Companion[/bold] — serving at http://localhost:{port}")
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                console.print(f"  Also available at: http://{ip}:{port}")
                break
    except Exception:
        pass

    # Propagate --api-only to the app factory for the --reload re-import case (D3).
    if api_only:
        os.environ["BOOKCOMPANION_API_ONLY"] = "1"

    console.print()
    uvicorn.run("app.api.main:app", host=host, port=port)
