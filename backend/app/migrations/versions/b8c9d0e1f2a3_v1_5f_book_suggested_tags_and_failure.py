"""v1.5f schema — books suggested_tags_json + last_summary_failure_*

Adds AI-derived tag suggestion storage (FR-E4.2) and the book-level
last-summary-failure diagnostic fields (FR-F3.1, mirroring the
BookSection.last_failure_* columns added in v1.4a).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-24 09:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    with op.batch_alter_table("books", schema=None) as batch_op:
        if not _has_column("books", "suggested_tags_json"):
            batch_op.add_column(sa.Column("suggested_tags_json", sa.JSON(), nullable=True))
        if not _has_column("books", "last_summary_failure_code"):
            batch_op.add_column(
                sa.Column("last_summary_failure_code", sa.String(length=50), nullable=True)
            )
        if not _has_column("books", "last_summary_failure_stderr"):
            batch_op.add_column(sa.Column("last_summary_failure_stderr", sa.Text(), nullable=True))
        if not _has_column("books", "last_summary_failure_at"):
            batch_op.add_column(
                sa.Column("last_summary_failure_at", sa.DateTime(timezone=True), nullable=True)
            )


def downgrade() -> None:
    with op.batch_alter_table("books", schema=None) as batch_op:
        for col in (
            "last_summary_failure_at",
            "last_summary_failure_stderr",
            "last_summary_failure_code",
            "suggested_tags_json",
        ):
            if _has_column("books", col):
                batch_op.drop_column(col)
