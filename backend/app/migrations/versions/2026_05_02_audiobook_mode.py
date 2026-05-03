"""audiobook mode — audio_files, audio_positions, processing_jobs index swap

Adds:
* ``audio_files`` — generated MP3 inventory keyed (book_id, content_type, content_id, voice).
* ``audio_positions`` — per-browser resume position; composite PK (content_type, content_id, browser_id).
* Drops ``ix_processing_jobs_one_active_per_book`` and recreates it as
  ``ix_processing_jobs_one_active_per_book_step`` over (book_id, step) so AUDIO and
  SUMMARIZE jobs can run concurrently per book (FR-17, D18).

Revision ID: 2026_05_02_audiobook
Revises: 9a67312a27a7
Create Date: 2026-05-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_05_02_audiobook"
down_revision: str | None = "9a67312a27a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CONTENT_TYPES = "'section_content','section_summary','book_summary','annotations_playlist'"
_AF_CT_TYPES = "'section_summary','book_summary','annotations_playlist'"


def upgrade() -> None:
    op.create_table(
        "audio_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("content_id", sa.Integer, nullable=False),
        sa.Column("voice", sa.String(128), nullable=False),
        sa.Column("engine", sa.String(32), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=False),
        sa.Column("sentence_count", sa.Integer, nullable=False),
        sa.Column("sentence_offsets_json", sa.Text, nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("sanitizer_version", sa.String(32), nullable=False),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("processing_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"content_type IN ({_AF_CT_TYPES})", name="ck_audio_files_content_type"),
        sa.UniqueConstraint("book_id", "content_type", "content_id", "voice", name="ux_audio_files_unit"),
    )
    op.create_index("ix_audio_files_book_id", "audio_files", ["book_id"])

    op.create_table(
        "audio_positions",
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("content_id", sa.Integer, nullable=False),
        sa.Column("browser_id", sa.String(128), nullable=False),
        sa.Column("sentence_index", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"content_type IN ({_CONTENT_TYPES})", name="ck_audio_positions_content_type"),
        sa.PrimaryKeyConstraint("content_type", "content_id", "browser_id", name="pk_audio_positions"),
    )
    op.create_index(
        "ix_audio_positions_target", "audio_positions", ["content_type", "content_id"]
    )

    # Index swap on processing_jobs — drop single-column unique, create (book_id, step).
    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_index("ix_processing_jobs_one_active_per_book")
        batch.create_index(
            "ix_processing_jobs_one_active_per_book_step",
            ["book_id", "step"],
            unique=True,
            sqlite_where=sa.text("status IN ('PENDING','RUNNING')"),
        )


def downgrade() -> None:
    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_index("ix_processing_jobs_one_active_per_book_step")
        batch.create_index(
            "ix_processing_jobs_one_active_per_book",
            ["book_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('PENDING','RUNNING')"),
        )

    op.drop_index("ix_audio_positions_target", table_name="audio_positions")
    op.drop_table("audio_positions")
    op.drop_index("ix_audio_files_book_id", table_name="audio_files")
    op.drop_table("audio_files")
