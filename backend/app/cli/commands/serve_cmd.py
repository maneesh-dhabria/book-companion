"""bookcompanion serve — start the web server."""

import contextlib
import os
import shutil
import signal
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


def _find_frontend_dir() -> Path | None:
    """Walk up from this file to locate a sibling `frontend/` with package.json.

    Returns None in installed-wheel contexts (no adjacent source tree).
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "frontend" / "package.json"
        if candidate.is_file():
            return candidate.parent
    return None


def _spawn_vite(frontend_dir: Path, api_port: int) -> subprocess.Popen[bytes]:
    """Launch `npm run dev` in its own process group so we can kill its
    children (esbuild, etc.) on shutdown without leaking processes.

    Exports BC_API_PORT so vite.config.ts's proxy target follows the backend
    when auto-bump picks a non-default port.
    """
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm not found on PATH — install Node.js or drop --dev")
    env = os.environ.copy()
    env["BC_API_PORT"] = str(api_port)
    return subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(frontend_dir),
        start_new_session=True,
        env=env,
    )


def _pick_available_port(host: str, preferred: int, max_tries: int = 20) -> int:
    """Return `preferred` if free, else the next free port in [preferred, preferred+max_tries).

    Tiny TOCTOU window between probe and uvicorn bind — acceptable for a
    single-user tool. If every port in the window is occupied, raise so the
    user sees a clear error instead of a cryptic uvicorn stack trace.
    """
    for candidate in range(preferred, preferred + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
                return candidate
            except OSError:
                continue
    raise RuntimeError(
        f"No free port found in range {preferred}..{preferred + max_tries - 1} on {host}"
    )


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
    dev: bool = typer.Option(
        False,
        "--dev",
        help=(
            "Dev mode: spawn `npm run dev` in the sibling frontend/ directory, "
            "run the backend API-only, and print the Vite URL to open. Requires "
            "a source checkout (no installed-wheel effect)."
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

    # --dev implies API-only: Vite serves the SPA, backend just answers /api.
    vite_proc: subprocess.Popen[bytes] | None = None
    if dev:
        frontend_dir = _find_frontend_dir()
        if frontend_dir is None:
            console.print(
                "[red]--dev requires a source checkout with a sibling "
                "frontend/ directory; nothing found walking up from this file."
                "[/red]"
            )
            raise typer.Exit(code=1)
        api_only = True
        os.environ["BOOKCOMPANION_API_ONLY"] = "1"

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

    actual_port = _pick_available_port(host, port)
    if actual_port != port:
        console.print(
            f"[yellow]Port {port} is busy; falling back to {actual_port}.[/yellow]"
        )
    port = actual_port

    if dev:
        try:
            vite_proc = _spawn_vite(frontend_dir, port)
        except RuntimeError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1) from e
        console.print(
            "[green]→ Open [bold]http://localhost:5173[/bold] "
            "(Vite proxies /api to the backend).[/green]"
        )

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
    try:
        uvicorn.run("app.api.main:app", host=host, port=port)
    finally:
        if vite_proc is not None:
            # Kill the whole Vite process group (esbuild children, etc.) so
            # nothing lingers after the backend shuts down.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(vite_proc.pid), signal.SIGTERM)
            vite_proc.wait(timeout=10)
