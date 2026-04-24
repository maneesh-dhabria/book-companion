"""v1.5b data migration — normalize content_md blockquotes

Applies ``normalize_blockquotes`` to every ``book_sections.content_md`` row
so already-parsed content ships with collapsed ``>`` chains and no
boundary ``---`` HRs. Idempotent — a re-run updates zero rows because
the normaliser is itself idempotent.

Must run AFTER v1_5a (summary image rewrite) and BEFORE v1_5c
(annotation prefix/suffix backfill) per spec §10.2: the backfill reads
``content_md`` and must see post-normalisation text.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-24 09:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import structlog
from alembic import op

from app.services.parser.blockquote_normalizer import normalize_blockquotes

logger = structlog.get_logger(__name__)

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, content_md FROM book_sections "
            "WHERE content_md IS NOT NULL AND content_md != ''"
        )
    ).fetchall()
    updated = 0
    skipped = 0
    for row in rows:
        try:
            new_md = normalize_blockquotes(row.content_md)
            if new_md != row.content_md:
                conn.execute(
                    sa.text(
                        "UPDATE book_sections SET content_md = :m WHERE id = :id"
                    ),
                    {"m": new_md, "id": row.id},
                )
                updated += 1
        except (ValueError, TypeError) as exc:
            logger.warning("v1_5b_skip", row_id=row.id, err=repr(exc))
            skipped += 1
    logger.info("v1_5b_done", updated=updated, skipped=skipped, candidates=len(rows))


def downgrade() -> None:  # pragma: no cover
    pass
