"""backfill image placeholders

Revision ID: a1b2c3d4e5f6
Revises: e152941ea209
Create Date: 2026-04-19 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import structlog
from alembic import op

from app.services.parser.image_url_rewrite import from_placeholder

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "e152941ea209"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = structlog.get_logger()


def upgrade() -> None:
    conn = op.get_bind()

    # FR-08: only process rows containing both ends of the placeholder token.
    rows = conn.execute(
        sa.text(
            r"""
            SELECT id, book_id, content_md
              FROM book_sections
             WHERE content_md LIKE '%\_\_IMG\_PLACEHOLDER\_\_:%\_\_ENDIMG\_\_%' ESCAPE '\'
            """
        )
    ).fetchall()

    rewritten = 0
    for row in rows:
        img_rows = conn.execute(
            sa.text("SELECT id, filename FROM images WHERE section_id = :sid"),
            {"sid": row.id},
        ).fetchall()
        fn_map = {ir.filename: ir.id for ir in img_rows if ir.filename}
        if not fn_map:
            continue  # FR-12: no matching images; leave placeholder intact
        new_md = from_placeholder(row.content_md, fn_map)
        if new_md != row.content_md:
            conn.execute(
                sa.text("UPDATE book_sections SET content_md = :md WHERE id = :id"),
                {"md": new_md, "id": row.id},
            )
            rewritten += 1
    log.info("migration_image_placeholders_complete", rewritten=rewritten)


def downgrade() -> None:
    log.info("migration_image_placeholders_downgrade_noop")
