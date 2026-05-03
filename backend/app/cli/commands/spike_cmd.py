"""bookcompanion spike tts — generate Kokoro MP3 + spike findings template."""

from __future__ import annotations

from datetime import date
from importlib.resources import files
from pathlib import Path

import typer
from jinja2 import Template
from rich.console import Console

from app.cli.deps import async_command, get_settings

console = Console()

spike_app = typer.Typer(name="spike", help="Spike commands (engine comparisons, etc.).")


def _repo_root() -> Path:
    """Climb out of backend/ to repo root that holds docs/."""
    return Path(__file__).resolve().parents[4]


@async_command
async def spike_tts(
    book_id: int = typer.Option(..., "--book-id", help="Book ID for the spike sample."),
    section_id: int = typer.Option(..., "--section-id", help="Section ID for the spike sample."),
    voice: str = typer.Option("af_sarah", "--voice", help="Kokoro voice for the sample."),
):
    """Generate a Kokoro MP3 spike clip and a findings template for engine comparison."""
    settings = get_settings()
    repo_root = _repo_root()
    spikes_dir = repo_root / "docs" / "spikes"
    spikes_dir.mkdir(parents=True, exist_ok=True)

    # Fetch section content
    section_title = f"Section {section_id}"
    book_title = f"Book {book_id}"
    sample_text = ""
    try:
        from app.cli.deps import get_services

        async with get_services() as svc:  # type: ignore[attr-defined]
            session = svc["session"]
            from sqlalchemy import select

            from app.db.models import Book, BookSection

            section = (
                await session.execute(select(BookSection).where(BookSection.id == section_id))
            ).scalar_one_or_none()
            if section is not None:
                section_title = section.title or section_title
                sample_text = (section.content_md or "")[:2000]
            book = (
                await session.execute(select(Book).where(Book.id == book_id))
            ).scalar_one_or_none()
            if book is not None:
                book_title = book.title or book_title
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not load book/section: {e}")

    if not sample_text:
        sample_text = (
            "The quick brown fox jumps over the lazy dog. "
            "Listening helps the words land differently than reading."
        )

    # Generate Kokoro clip
    clip_path = spikes_dir / "clip-kokoro.mp3"
    try:
        from app.services.tts.kokoro_provider import KokoroProvider

        model_dir = Path(settings.data.directory) / "tts_model"
        provider = KokoroProvider(model_dir=model_dir)
        result = provider.synthesize(sample_text, voice=voice)
        clip_path.write_bytes(result.audio_bytes)
        console.print(f"  [green]✓[/green] Wrote {clip_path}")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Kokoro synthesis failed: {e}")
        clip_path.write_bytes(b"")

    # Render findings template
    today_iso = date.today().isoformat()
    out_path = spikes_dir / f"{today_iso}-tts-engine-spike.md"
    try:
        tpl_path = files("app.cli.templates") / "spike_tts_findings.md.j2"
        tpl = Template(tpl_path.read_text())
    except Exception:
        tpl = Template(
            "# TTS engine spike — {{ today_iso }}\n\n"
            "**Book:** {{ book_title }} (id={{ book_id }})\n"
            "**Section:** {{ section_title }} (id={{ section_id }})\n\n"
            "Kokoro vs Web Speech findings here.\n"
        )
    rendered = tpl.render(
        today_iso=today_iso,
        book_id=book_id,
        section_id=section_id,
        book_title=book_title,
        section_title=section_title,
        kokoro_voice=voice,
        sample_chars=len(sample_text),
    )
    out_path.write_text(rendered)
    console.print(f"  [green]✓[/green] Wrote {out_path}")
    console.print(
        "\nOpen [bold]http://localhost:8765/spike-helper.html[/bold] to listen to the "
        "Web Speech version of the same passage. Edit the spike doc with your impressions."
    )


spike_app.command("tts")(spike_tts)
