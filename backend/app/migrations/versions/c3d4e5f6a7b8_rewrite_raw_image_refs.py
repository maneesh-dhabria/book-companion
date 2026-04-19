"""rewrite raw EPUB image refs

Legacy books imported before the to_placeholder/from_placeholder pipeline have
raw EPUB-relative refs like `![image](images/00003.jpg)` or
`<img src="images/00003.jpg">` in content_md. Migration A only rewrote the
`__IMG_PLACEHOLDER__:…__ENDIMG__` token form, so these books still can't
render their images.

For each section: apply `to_placeholder` (raw → placeholder) and then
`from_placeholder` (placeholder → /api/v1/images/{id}) using the section's
own `images` rows as the filename→id map. Idempotent: sections that already
use /api/v1/images/{id} URLs have no raw refs left, so both passes are no-ops.
False-positives are bounded by the same basename requirement from_placeholder
uses — a raw ref with no matching image row stays untouched.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-19 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import structlog

from alembic import op
from app.services.parser.image_url_rewrite import from_placeholder, to_placeholder

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = structlog.get_logger()


def upgrade() -> None:
    conn = op.get_bind()

    # Only look at sections that plausibly contain a raw image ref. A
    # negative filter on `__IMG_PLACEHOLDER__` would be wrong here — those
    # were already handled by Migration A — but pre-rewrite rows never
    # carried that token in the first place. Bound the scan to rows whose
    # content_md mentions a relative image path extension.
    rows = conn.execute(
        sa.text(
            """
            SELECT id, book_id, content_md FROM book_sections
             WHERE content_md LIKE '%.jpg%'
                OR content_md LIKE '%.jpeg%'
                OR content_md LIKE '%.png%'
                OR content_md LIKE '%.gif%'
                OR content_md LIKE '%.webp%'
                OR content_md LIKE '%.svg%'
            """
        )
    ).fetchall()

    rewritten = 0
    for row in rows:
        img_rows = conn.execute(
            sa.text("SELECT id, filename FROM images WHERE section_id = :sid"),
            {"sid": row.id},
        ).fetchall()
        if not img_rows:
            continue
        # Use basename matching — `to_placeholder` strips to basename, so
        # `from_placeholder` must key on basename too.
        fn_map: dict[str, int] = {}
        for ir in img_rows:
            if ir.filename:
                fn_map[ir.filename.rsplit("/", 1)[-1]] = ir.id
        if not fn_map:
            continue
        new_md = from_placeholder(to_placeholder(row.content_md), fn_map)
        if new_md != row.content_md:
            conn.execute(
                sa.text("UPDATE book_sections SET content_md = :md WHERE id = :id"),
                {"md": new_md, "id": row.id},
            )
            rewritten += 1

    log.info("migration_rewrite_raw_image_refs_complete", rewritten=rewritten)


def downgrade() -> None:
    log.info("migration_rewrite_raw_image_refs_downgrade_noop")
