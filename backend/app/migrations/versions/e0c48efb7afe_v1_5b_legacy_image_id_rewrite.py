"""v1.5b data migration — rewrite legacy ``![alt](image:N)`` markdown refs

Older summarizer prompts emitted in-app image references using the
``image:NNN`` URL scheme. The frontend renders these as broken links since
v1.5 standardized on ``/api/v1/images/{ID}``. This one-shot migration
rewrites every ``summaries.summary_md`` row that still uses the legacy
form, resolving each ``image:NNN`` against the row's book images map. IDs
that don't belong to the section's book are stripped to ``[alt](#)`` so
the rendered output stays readable (FR-07, NFR-06).

Idempotent: rewritten output uses absolute ``/api/v1/images/N`` URLs which
the legacy regex no longer matches, so re-running finds zero candidates.

Revision ID: e0c48efb7afe
Revises: 0a1b2c3d4e5f
Create Date: 2026-05-01 00:18:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
import structlog
from alembic import op

from app.services.parser.image_url_rewrite import from_image_id_scheme

logger = structlog.get_logger(__name__)

revision: str = "e0c48efb7afe"
down_revision: str | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, summary_md, book_id FROM summaries WHERE summary_md LIKE '%](image:%'")
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
            # The dict's values (image ids) are what from_image_id_scheme
            # checks against; filenames are unused for this rewrite path
            # but keep the same shape as from_placeholder for consistency.
            fmap = {i.filename: i.id for i in imgs if i.filename}
            new_md = from_image_id_scheme(row.summary_md, fmap, on_missing="strip")
            if new_md != row.summary_md:
                conn.execute(
                    sa.text("UPDATE summaries SET summary_md = :m WHERE id = :id"),
                    {"m": new_md, "id": row.id},
                )
                updated += 1
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("v1_5b_legacy_image_skip", row_id=row.id, err=repr(exc))
            skipped += 1

    logger.info(
        "v1_5b_legacy_image_id_rewrite",
        updated=updated,
        skipped=skipped,
        candidates=len(rows),
    )


def downgrade() -> None:  # pragma: no cover
    # One-shot data fix; rewriting back to the broken legacy scheme is
    # both pointless and lossy (we'd need to know which rows we touched).
    pass
