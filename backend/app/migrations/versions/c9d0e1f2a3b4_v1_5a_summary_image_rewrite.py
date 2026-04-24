"""v1.5a data migration — rewrite summary image placeholders

Walks every ``summaries`` row whose ``summary_md`` still contains a
``__IMG_PLACEHOLDER__`` token and resolves each to ``/api/v1/images/{id}``.
Missing filenames are stripped (``on_missing='strip'``) so orphaned
references from pre-v1.5 summaries don't render as raw tokens.

Idempotent: a second run finds zero rows needing an update because the
placeholder pattern no longer matches.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-24 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import structlog
from alembic import op

from app.services.parser.image_url_rewrite import from_placeholder

logger = structlog.get_logger(__name__)

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, summary_md, book_id "
            "FROM summaries "
            "WHERE summary_md LIKE '%__IMG_PLACEHOLDER__:%'"
        )
    ).fetchall()

    updated = 0
    skipped = 0
    for row in rows:
        try:
            imgs = conn.execute(
                sa.text(
                    "SELECT i.filename, i.id FROM images i "
                    "JOIN book_sections bs ON i.section_id = bs.id "
                    "WHERE bs.book_id = :bid"
                ),
                {"bid": row.book_id},
            ).fetchall()
            fmap = {i.filename: i.id for i in imgs if i.filename}
            new_md = from_placeholder(row.summary_md, fmap, on_missing="strip")
            if new_md != row.summary_md:
                conn.execute(
                    sa.text(
                        "UPDATE summaries SET summary_md = :m WHERE id = :id"
                    ),
                    {"m": new_md, "id": row.id},
                )
                updated += 1
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("v1_5a_skip", row_id=row.id, err=repr(exc))
            skipped += 1

    logger.info("v1_5a_done", updated=updated, skipped=skipped, candidates=len(rows))


def downgrade() -> None:  # pragma: no cover
    # Data migration — rewrite is a one-way normalization.
    pass
