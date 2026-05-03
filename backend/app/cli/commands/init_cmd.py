"""bookcompanion init — first-time setup."""

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import typer
from rich.console import Console

from app.cli.deps import async_command, get_settings

console = Console()


def _run_migrations() -> None:
    """Run alembic migrations programmatically.

    Runs in a worker thread so env.py's `asyncio.run(run_migrations_online())`
    can create a fresh event loop. The caller (`init`) is itself inside an
    `asyncio.run` (via `@async_command`), and nested `asyncio.run` is forbidden.
    """
    import threading

    from alembic.command import upgrade
    from alembic.config import Config

    ini_path = files("app.migrations") / "alembic.ini"
    cfg = Config(str(ini_path))
    err: list[Exception] = []

    def _worker() -> None:
        try:
            upgrade(cfg, "head")
        except Exception as e:
            err.append(e)

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    if err:
        raise err[0]


@async_command
async def init(
    tts_engine: str = typer.Option(
        "",
        "--tts-engine",
        help="Eagerly download model for the given TTS engine ('kokoro').",
    ),
):
    """First-time setup: create data directory, initialize database, download embedding model."""
    settings = get_settings()
    data_dir = Path(settings.data.directory)

    console.print("\n[bold]Book Companion — First-Time Setup[/bold]\n")

    # 1. Create data directory
    console.print("Creating data directory...")
    data_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"  [green]✓[/green] {data_dir}")

    # 2. Check optional dependencies
    console.print("\nChecking dependencies...")
    _check_dependency("ebook-convert (Calibre)", "ebook-convert", ["--version"], required=False)

    # 3. Detect LLM providers
    from app.services.summarizer import detect_llm_provider

    provider = detect_llm_provider()
    if provider:
        console.print(f"  [green]✓[/green] LLM provider: {provider}")
    else:
        console.print(
            "  [yellow]⚠[/yellow] No LLM provider found (claude/codex). "
            "Summarization will be unavailable."
        )

    # 4. Run database migrations (in-process; no subprocess/PATH dependency)
    console.print("\nInitializing database...")
    try:
        _run_migrations()
        console.print("  [green]✓[/green] Database initialized")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Migration warning: {e}")

    # 5. Download embedding model (warm-up)
    console.print("\nDownloading embedding model (first time only, ~23MB)...")
    try:
        from fastembed import TextEmbedding

        model_cache = str(data_dir / "models")
        TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", cache_dir=model_cache)
        console.print("  [green]✓[/green] all-MiniLM-L6-v2: ready")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Model download failed: {e}")
        console.print("    Embedding model will be downloaded on first use.")

    # 6. Optional TTS engine bootstrap (F6 / F7)
    effective_tts_engine = tts_engine or getattr(settings.tts, "engine", "")
    if effective_tts_engine == "kokoro":
        console.print("\nChecking Kokoro prerequisites...")
        if shutil.which("ffmpeg") is None:
            console.print(
                "  [red]✗[/red] ffmpeg not found on PATH.\n"
                "    Install via [bold]brew install ffmpeg[/bold] (macOS) or your distro's package manager,\n"
                "    then re-run [bold]bookcompanion init[/bold]."
            )
            raise typer.Exit(code=1)
        console.print("  [green]✓[/green] ffmpeg: found")

        if tts_engine == "kokoro":
            console.print("Downloading Kokoro model (~330MB, one-time)...")
            try:
                from app.services.tts.kokoro_provider import KokoroProvider

                KokoroProvider._ensure_model_downloaded(data_dir / "tts_model")
                console.print("  [green]✓[/green] Kokoro model: ready")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Kokoro download failed: {e}")

    # 7. Print getting started
    console.print("\n[bold]Setup complete![/bold] Here's how to get started:\n")
    console.print("  1. Start the web UI:       bookcompanion serve")
    console.print("  2. Add your first book:    bookcompanion add ~/path/to/book.epub")
    console.print("  3. Full summarization:     bookcompanion summarize <book_id>")
    console.print("  4. Browse your library:    bookcompanion list")
    console.print('  5. Search across books:    bookcompanion search "query"')
    console.print(f"\nData stored in: {data_dir}")
    console.print("Run `bookcompanion --help` for all commands.\n")


def _check_dependency(name: str, command: str, args: list, required: bool = True):
    if shutil.which(command):
        try:
            result = subprocess.run([command] + args, capture_output=True, text=True, timeout=10)
            version = result.stdout.strip().split("\n")[0][:60]
            console.print(f"  [green]✓[/green] {name}: {version}")
        except Exception:
            console.print(f"  [green]✓[/green] {name}: found")
    else:
        marker = "[red]✗[/red]" if required else "[yellow]⚠[/yellow]"
        console.print(f"  {marker} {name}: not found")
        if required:
            console.print(f"    Install {name} and try again.")
