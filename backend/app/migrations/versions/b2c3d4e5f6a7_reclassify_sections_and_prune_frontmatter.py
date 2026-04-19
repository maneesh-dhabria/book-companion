"""reclassify sections and prune frontmatter

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-19 00:00:01
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

import sqlalchemy as sa
import structlog
from alembic import op

from app.services.parser.section_classifier import (
    FRONT_MATTER_TYPES,
    detect_section_type,
)

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = structlog.get_logger()


def _parse_sqlite_timestamp(value):
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unrecognized SQLite timestamp format: {value!r}")
    return value


def upgrade() -> None:
    conn = op.get_bind()
    totals = {
        "reclassified": 0,
        "auto_summaries_pruned": 0,
        "user_summaries_preserved": 0,
        "books_affected": 0,
    }

    book_ids = [
        r.id for r in conn.execute(sa.text("SELECT id FROM books ORDER BY id"))
    ]

    for book_id in book_ids:
        rows = conn.execute(
            sa.text(
                "SELECT id, title, content_md, section_type "
                "FROM book_sections WHERE book_id = :b ORDER BY order_index"
            ),
            {"b": book_id},
        ).fetchall()

        per_book = {"reclassified": 0, "pruned": 0, "preserved": 0}

        batch_end = conn.execute(
            sa.text(
                "SELECT max(s.created_at) FROM summaries s "
                "JOIN book_sections bs ON bs.id = s.content_id "
                "WHERE s.content_type='section' AND bs.book_id = :b"
            ),
            {"b": book_id},
        ).scalar()
        cutoff = None
        if batch_end is not None:
            batch_end_dt = _parse_sqlite_timestamp(batch_end)
            cutoff = batch_end_dt - timedelta(seconds=60)

        for row in rows:
            new_type = detect_section_type(row.title or "", row.content_md)
            if new_type == row.section_type:
                continue

            conn.execute(
                sa.text(
                    "UPDATE book_sections SET section_type = :t WHERE id = :id"
                ),
                {"t": new_type, "id": row.id},
            )
            per_book["reclassified"] += 1

            if (
                new_type in FRONT_MATTER_TYPES
                and row.section_type not in FRONT_MATTER_TYPES
            ):
                count = (
                    conn.execute(
                        sa.text(
                            "SELECT count(*) FROM summaries "
                            "WHERE content_type='section' AND content_id = :sid"
                        ),
                        {"sid": row.id},
                    ).scalar()
                    or 0
                )

                if count == 1:
                    conn.execute(
                        sa.text(
                            "DELETE FROM summaries "
                            "WHERE content_type='section' AND content_id = :sid"
                        ),
                        {"sid": row.id},
                    )
                    conn.execute(
                        sa.text(
                            "UPDATE book_sections "
                            "SET default_summary_id = NULL WHERE id = :sid"
                        ),
                        {"sid": row.id},
                    )
                    per_book["pruned"] += 1
                elif count > 1 and cutoff is not None:
                    newest_non_batch = conn.execute(
                        sa.text(
                            "SELECT id FROM summaries "
                            "WHERE content_type='section' AND content_id = :sid "
                            "  AND created_at < :cutoff "
                            "ORDER BY created_at DESC LIMIT 1"
                        ),
                        {"sid": row.id, "cutoff": cutoff},
                    ).scalar()
                    if newest_non_batch is not None:
                        conn.execute(
                            sa.text(
                                "UPDATE book_sections "
                                "SET default_summary_id = :new "
                                "WHERE id = :sid"
                            ),
                            {"new": newest_non_batch, "sid": row.id},
                        )
                    per_book["preserved"] += 1

        if per_book["reclassified"] > 0:
            totals["books_affected"] += 1
            totals["reclassified"] += per_book["reclassified"]
            totals["auto_summaries_pruned"] += per_book["pruned"]
            totals["user_summaries_preserved"] += per_book["preserved"]
            log.info("migration_reclassify_book", book_id=book_id, **per_book)

    log.info("migration_reclassify_complete", **totals)


def downgrade() -> None:
    log.info("migration_reclassify_downgrade_noop")
