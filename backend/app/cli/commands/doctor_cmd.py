"""CLI diagnostic commands — orphan-tag detection, etc. (FR-E1.5)."""

from __future__ import annotations

import typer
from sqlalchemy import text

from app.cli.deps import async_command, get_services
from app.cli.formatting import print_success

doctor_app = typer.Typer(help="Diagnostic commands.")


@doctor_app.command("orphan-tags")
@async_command
async def orphan_tags(
    fix: bool = typer.Option(False, "--fix", help="Delete the orphaned Tag rows."),
):
    """List Tag rows with no remaining Taggable associations.

    Book / section deletion cascades Taggable rows (per BookService.delete_book)
    but leaves Tag rows intact. This subcommand surfaces the orphans — and
    deletes them with --fix.
    """
    async with get_services() as svc:
        session = svc["session"]
        result = await session.execute(
            text(
                "SELECT t.id, t.name FROM tags t "
                "LEFT JOIN taggables tg ON tg.tag_id = t.id "
                "WHERE tg.tag_id IS NULL"
            )
        )
        rows = result.fetchall()
        if not rows:
            print_success("No orphaned tags found.")
            return
        for r in rows:
            typer.echo(f"{r.id}\t{r.name}")
        if fix:
            ids = [r.id for r in rows]
            await session.execute(
                text("DELETE FROM tags WHERE id IN :ids"),
                {"ids": tuple(ids)},
            )
            await session.commit()
            print_success(f"Deleted {len(ids)} orphaned tag rows.")
        else:
            typer.echo(f"\n{len(rows)} orphaned tag(s). Re-run with --fix to delete.")
