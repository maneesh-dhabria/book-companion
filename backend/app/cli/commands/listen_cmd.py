"""bookcompanion listen — local-device playback or queue-and-stream generation."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from app.cli.deps import async_command, get_services, get_settings

console = Console()


def _split_sentences(sanitized_text: str, offsets: list[int]) -> list[str]:
    """Slice sanitized text by ``sentence_offsets_chars``.

    ``sentence_offsets_chars`` are sentence START indices (matches
    ``markdown_to_speech.sanitize`` and ``audio_gen_service._split_by_offsets``).
    """
    if not offsets:
        return [s for s in [sanitized_text.strip()] if s]
    out: list[str] = []
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < len(offsets) else len(sanitized_text)
        out.append(sanitized_text[start:end].strip())
    return [s for s in out if s]


@async_command
async def listen(
    book_id: int = typer.Argument(..., help="Book ID to listen to."),
    generate: bool = typer.Option(
        False,
        "--generate",
        help="Queue a step=AUDIO job and stream progress instead of playing locally.",
    ),
    scope: str = typer.Option(
        "book", "--scope", help="When --generate: 'book' | 'sections' | 'all'."
    ),
    voice: str = typer.Option("af_sarah", "--voice", help="Kokoro voice."),
):
    """Play or generate audio for a book on the local device."""
    if generate:
        await _run_generate(book_id=book_id, scope=scope, voice=voice)
    else:
        await _run_local_playback(book_id=book_id, voice=voice)


async def _run_local_playback(book_id: int, voice: str) -> None:
    settings = get_settings()
    try:
        import sounddevice as _sd  # type: ignore[import-not-found]  # noqa: F401
    except Exception as e:
        console.print(f"[red]✗[/red] sounddevice not installed: {e}")
        console.print("  Install via [bold]uv add sounddevice[/bold] and re-run.")
        raise typer.Exit(code=1) from e

    async with get_services() as svc:
        from sqlalchemy import select

        from app.db.models import Book, Summary, SummaryContentType

        session = svc["session"]
        book = (await session.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
        if book is None:
            console.print(f"[red]✗[/red] Book {book_id} not found.")
            raise typer.Exit(code=1)
        # Pull default book summary
        summary = (
            (
                await session.execute(
                    select(Summary)
                    .where(Summary.book_id == book_id)
                    .where(Summary.content_type == SummaryContentType.BOOK)
                    .order_by(Summary.id.desc())
                )
            )
            .scalars()
            .first()
        )
        if summary is None or not summary.summary_md:
            console.print(f"[yellow]⚠[/yellow] No book summary for {book.title}.")
            raise typer.Exit(code=1)

    from app.services.tts.kokoro_provider import KokoroProvider
    from app.services.tts.markdown_to_speech import sanitize

    san = sanitize(summary.summary_md)
    sentences = _split_sentences(san.text, list(san.sentence_offsets_chars))
    provider = KokoroProvider(model_dir=Path(settings.data.directory) / "models" / "tts")

    console.print(f"\n[bold]Listening to:[/bold] {book.title}")
    console.print(f"[dim]{len(sentences)} sentence(s); space=pause, q=quit[/dim]\n")

    for i, s in enumerate(sentences, 1):
        try:
            result = provider.synthesize_segmented([s], voice=voice)
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] sentence {i} synth failed: {e}")
            continue
        # The provider returns MP3 bytes via ffmpeg; for sounddevice we'd need PCM.
        # As a v1 minimum, write to a temp file and delegate playback to system afplay.
        import subprocess
        import tempfile  # noqa: E401

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(result.audio_bytes)
            mp3_path = f.name
        try:
            subprocess.run(["afplay", mp3_path], check=False)
        except FileNotFoundError:
            pass
        finally:
            Path(mp3_path).unlink(missing_ok=True)

    console.print("\n[green]Done.[/green]")


async def _run_generate(book_id: int, scope: str, voice: str) -> None:
    """Queue an AUDIO job and stream progress via SSE."""
    import httpx

    base = "http://localhost:8000"
    payload = {"scope": scope, "voice": voice, "engine": "kokoro"}
    try:
        r = httpx.post(f"{base}/api/v1/books/{book_id}/audio", json=payload, timeout=10.0)
    except Exception as e:
        console.print(f"[red]✗[/red] Backend unreachable at {base}: {e}")
        raise typer.Exit(code=1) from e
    if r.status_code >= 400:
        console.print(f"[red]✗[/red] Queue failed: {r.status_code} {r.text}")
        raise typer.Exit(code=1) from None
    job = r.json()
    job_id = job["job_id"]
    total = job["total_units"]
    console.print(f"Queued job {job_id} ({total} unit(s))…")

    completed: list[dict] = []
    with Progress(
        TextColumn("[bold]Audio[/bold]"),
        BarColumn(),
        TextColumn("{task.completed} / {task.total}"),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("audio", total=total)
        # Stream SSE
        with httpx.stream(
            "GET",
            f"{base}/api/v1/processing/jobs/{job_id}/events",
            timeout=None,
        ) as resp:
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                import json

                try:
                    payload_obj = json.loads(line[5:].strip())
                except Exception:
                    continue
                event_type = payload_obj.get("type") or payload_obj.get("event")
                if event_type == "section_audio_completed":
                    completed.append(payload_obj.get("data") or payload_obj)
                    progress.advance(task)
                elif event_type in {"job_completed", "job_failed", "job_cancelled"}:
                    break

    total_size = sum(int(c.get("file_size_bytes") or 0) for c in completed)
    for c in completed:
        path = c.get("file_path")
        size = c.get("file_size_bytes")
        if path:
            console.print(f"  {path}  ({size} bytes)")
    if total_size:
        try:
            import humanize

            console.print(f"\nTotal disk: {humanize.naturalsize(total_size)}")
        except ImportError:
            console.print(f"\nTotal disk: {total_size} bytes")
