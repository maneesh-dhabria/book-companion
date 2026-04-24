"""v1.5c data migration — backfill annotation prefix + suffix

Populates ``annotations.prefix`` and ``annotations.suffix`` with up to 32
characters on either side of ``text_start..text_end`` from the enclosing
``book_sections.content_md``. Used by the hybrid anchor algorithm
(FR-C5.5) to re-resolve drifted offsets after data migrations.

Runs AFTER v1_5b (blockquote normalise) because the source text must
match what the runtime renderer sees.

Only annotations with non-null ``text_start`` + ``text_end`` and a
section-scoped ``content_type`` get populated. Existing prefix/suffix
values are left alone so a re-run is a no-op.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-04-24 09:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import structlog
from alembic import op

logger = structlog.get_logger(__name__)

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTEXT_CHARS = 32


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT a.id, a.text_start, a.text_end, a.content_id, bs.content_md "
            "FROM annotations a "
            "LEFT JOIN book_sections bs ON bs.id = a.content_id "
            "WHERE a.text_start IS NOT NULL "
            "AND a.text_end IS NOT NULL "
            "AND a.content_type IN ('section_content', 'section_summary') "
            "AND (a.prefix IS NULL OR a.suffix IS NULL)"
        )
    ).fetchall()
    updated = 0
    skipped = 0
    for row in rows:
        try:
            md = row.content_md or ""
            start = int(row.text_start)
            end = int(row.text_end)
            pref = md[max(0, start - CONTEXT_CHARS) : start]
            suff = md[end : end + CONTEXT_CHARS]
            conn.execute(
                sa.text(
                    "UPDATE annotations SET prefix = :p, suffix = :s WHERE id = :id"
                ),
                {"p": pref, "s": suff, "id": row.id},
            )
            updated += 1
        except (ValueError, TypeError) as exc:
            logger.warning("v1_5c_skip", row_id=row.id, err=repr(exc))
            skipped += 1
    logger.info("v1_5c_done", updated=updated, skipped=skipped, candidates=len(rows))


def downgrade() -> None:  # pragma: no cover
    pass
