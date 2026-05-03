"""bookcompanion maintenance — periodic housekeeping subcommands."""

from __future__ import annotations

import typer
from rich.console import Console

from app.cli.deps import async_command, get_services

console = Console()

maintenance_app = typer.Typer(name="maintenance", help="Periodic maintenance commands.")


@async_command
async def audio_positions_sweep():
    """Remove audio_positions rows whose content_id no longer resolves (FR-26b)."""
    from sqlalchemy import select

    async with get_services() as svc:
        session = svc["session"]
        from app.db.models import (
            AudioPosition,
            Book,
            BookSection,
            ContentType,
            Summary,
            SummaryContentType,
        )

        rows = (await session.execute(select(AudioPosition))).scalars().all()
        removed = 0
        for row in rows:
            valid = False
            if row.content_type in (ContentType.SECTION_CONTENT, ContentType.SECTION_SUMMARY):
                target = (
                    await session.execute(
                        select(BookSection).where(BookSection.id == row.content_id)
                    )
                ).scalar_one_or_none()
                valid = target is not None
            elif row.content_type == ContentType.BOOK_SUMMARY:
                target = (
                    await session.execute(
                        select(Summary)
                        .where(Summary.id == row.content_id)
                        .where(Summary.content_type == SummaryContentType.BOOK)
                    )
                ).scalar_one_or_none()
                if target is None:
                    target = (
                        await session.execute(select(Book).where(Book.id == row.content_id))
                    ).scalar_one_or_none()
                valid = target is not None
            elif row.content_type == ContentType.ANNOTATIONS_PLAYLIST:
                target = (
                    await session.execute(select(Book).where(Book.id == row.content_id))
                ).scalar_one_or_none()
                valid = target is not None
            else:
                valid = False
            if not valid:
                await session.delete(row)
                removed += 1
        await session.commit()
        console.print(f"Removed {removed} orphan audio_position row(s).")


maintenance_app.command("audio-positions-sweep")(audio_positions_sweep)
