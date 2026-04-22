"""v1.4a schema — BookSection failure cols + partial UNIQUE processing_jobs

Additive schema migration preparing for v1.4 failure-surfacing and concurrency
guards. Introduces five new columns on ``book_sections`` tracking the most
recent summarization attempt, and a partial UNIQUE index on ``processing_jobs``
that prevents concurrent PENDING/RUNNING jobs for the same book.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-22 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    with op.batch_alter_table("book_sections", schema=None) as batch:
        batch.add_column(
            sa.Column("last_failure_type", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("last_failure_message", sa.Text(), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "last_attempted_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch.add_column(
            sa.Column(
                "attempt_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column("last_preset_used", sa.String(length=200), nullable=True)
        )

    op.create_index(
        "ix_book_sections_last_attempted_at",
        "book_sections",
        ["last_attempted_at"],
    )

    if not _has_column("processing_jobs", "pid"):
        with op.batch_alter_table("processing_jobs", schema=None) as batch:
            batch.add_column(sa.Column("pid", sa.Integer(), nullable=True))

    op.create_index(
        "ix_processing_jobs_one_active_per_book",
        "processing_jobs",
        ["book_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('PENDING','RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processing_jobs_one_active_per_book",
        table_name="processing_jobs",
    )
    op.drop_index(
        "ix_book_sections_last_attempted_at", table_name="book_sections"
    )
    with op.batch_alter_table("book_sections", schema=None) as batch:
        batch.drop_column("last_preset_used")
        batch.drop_column("attempt_count")
        batch.drop_column("last_attempted_at")
        batch.drop_column("last_failure_message")
        batch.drop_column("last_failure_type")
