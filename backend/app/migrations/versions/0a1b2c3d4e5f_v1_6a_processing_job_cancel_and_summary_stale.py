"""v1.6a — processing job cancel + summary is_stale + queue index

Adds three things in one ship:
* ``processing_jobs.cancel_requested BOOLEAN NOT NULL DEFAULT 0`` (D8 / FR-B13)
* ``processing_jobs.created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP``
  used by the new global queue worker to atomically pick the oldest PENDING
  job (FR-B11). The pre-existing ProcessingJob model had no created_at
  column — back-fill via SQLite's CURRENT_TIMESTAMP.
* ``processing_jobs.last_event_at TIMESTAMP NULL`` — used by the frontend
  jobQueue store to reconcile SSE buffer vs initial fetch (FR-F19b).
* ``summaries.is_stale BOOLEAN NOT NULL DEFAULT 0`` (P2, FR-B19) — set when
  a structure-edit invalidates a section's existing summaries.
* ``ix_processing_jobs_status_created (status, created_at)`` — supports
  the queue worker's ``WHERE status='PENDING' ORDER BY created_at``
  promotion query (P5).

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-04-30 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0a1b2c3d4e5f"
down_revision: str | None = "a5459240fea0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("processing_jobs") as batch:
        batch.add_column(
            sa.Column(
                "cancel_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch.add_column(
            sa.Column(
                "last_event_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "request_params",
                sa.JSON(),
                nullable=True,
            )
        )

    with op.batch_alter_table("summaries") as batch:
        batch.add_column(
            sa.Column(
                "is_stale",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )

    op.create_index(
        "ix_processing_jobs_status_created",
        "processing_jobs",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_status_created", table_name="processing_jobs")
    with op.batch_alter_table("summaries") as batch:
        batch.drop_column("is_stale")
    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_column("request_params")
        batch.drop_column("last_event_at")
        batch.drop_column("created_at")
        batch.drop_column("cancel_requested")
