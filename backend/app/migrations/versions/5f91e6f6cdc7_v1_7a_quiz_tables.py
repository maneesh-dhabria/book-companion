"""v1_7a quiz tables

Single migration for the AI Comprehension Quiz feature: 3 new tables
(quiz_sessions, quiz_questions, quiz_dedup_state) + Book.pre_drafted_q1_id
column. Mirrors spec §10.1 DDL.

Notes:
- Autogenerate flagged unrelated drift (FTS5 shadow tables, annotations.content_type
  / processing_jobs.step enum widening). Those are pre-existing and out of scope —
  stripped from this migration.
- Uses ``op.batch_alter_table`` for the books column add (SQLite ALTER TABLE
  limitation per CLAUDE.md gotcha #8).
- Circular FK between books.pre_drafted_q1_id ↔ quiz_questions.id resolved with
  ``use_alter=True``: create books column with no FK first, then add FK after both
  tables exist.

Revision ID: 5f91e6f6cdc7
Revises: a8b9c0d1e2f3
Create Date: 2026-05-09 18:21:06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5f91e6f6cdc7"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quiz_dedup_state",
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("themes_summary", sa.Text(), nullable=True),
        sa.Column("themes_summary_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_rollup_question_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("book_id"),
    )

    op.create_table(
        "quiz_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("scope_mode", sa.String(length=32), nullable=False),
        sa.Column("scope_section_ids", sa.JSON(), nullable=True),
        sa.Column("theme", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scope_mode IN ('all_summaries','specific_chapters')",
            name="ck_quiz_sessions_scope_mode",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress','completed','abandoned')",
            name="ck_quiz_sessions_status",
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("quiz_sessions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_quiz_sessions_book_created", ["book_id", "created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_quiz_sessions_book_id"), ["book_id"], unique=False
        )
        batch_op.create_index(
            "ix_quiz_sessions_book_status", ["book_id", "status"], unique=False
        )

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("shape", sa.String(length=16), nullable=False),
        sa.Column("bloom_level", sa.String(length=16), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("concept_label", sa.String(length=200), nullable=False),
        sa.Column("citation_json", sa.Text(), nullable=False),
        sa.Column("mcq_options_json", sa.Text(), nullable=True),
        sa.Column("intended_error", sa.Text(), nullable=True),
        sa.Column("error_explanation", sa.Text(), nullable=True),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("feedback_json", sa.Text(), nullable=True),
        sa.Column("agent_verdict", sa.String(length=16), nullable=True),
        sa.Column("self_assessment", sa.String(length=16), nullable=True),
        sa.Column("override_note", sa.Text(), nullable=True),
        sa.Column(
            "explain_history_json",
            sa.Text(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("skip_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("discarded", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("warm_up", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_pregen", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_stale", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "shape IN ('mcq','open','spot_error')",
            name="ck_quiz_questions_shape",
        ),
        sa.CheckConstraint(
            "bloom_level IN ('remember','understand','apply','analyze','evaluate','create')",
            name="ck_quiz_questions_bloom",
        ),
        sa.CheckConstraint(
            "agent_verdict IS NULL OR agent_verdict IN ('correct','partial','incorrect')",
            name="ck_quiz_questions_agent_verdict",
        ),
        sa.CheckConstraint(
            "self_assessment IS NULL OR self_assessment IN ('got_it','partial','missed')",
            name="ck_quiz_questions_self_assessment",
        ),
        sa.CheckConstraint(
            "(shape = 'mcq' AND mcq_options_json IS NOT NULL "
            "AND intended_error IS NULL AND error_explanation IS NULL) "
            "OR (shape = 'spot_error' AND intended_error IS NOT NULL "
            "AND error_explanation IS NOT NULL AND mcq_options_json IS NULL) "
            "OR (shape = 'open' AND mcq_options_json IS NULL "
            "AND intended_error IS NULL AND error_explanation IS NULL)",
            name="ck_quiz_questions_shape_payload",
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["quiz_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("quiz_questions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_quiz_questions_book_dedup",
            ["book_id", "is_stale", "discarded", "skip_count", "created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_quiz_questions_concept",
            ["book_id", "concept_label", "is_stale"],
            unique=False,
        )
        batch_op.create_index(
            "ix_quiz_questions_session", ["session_id"], unique=False
        )

    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pre_drafted_q1_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_books_pre_drafted_q1_id",
            "quiz_questions",
            ["pre_drafted_q1_id"],
            ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )

    # Partial index per spec §10.1 (faster pre-gen slot lookup; only populated rows)
    op.execute(
        "CREATE INDEX ix_books_pre_drafted_q1 ON books(pre_drafted_q1_id) "
        "WHERE pre_drafted_q1_id IS NOT NULL"
    )


def downgrade() -> None:
    # Drop the partial index BEFORE dropping the column — batch_alter_table reflects
    # existing indexes and would try to recreate this one against the now-missing column.
    op.execute("DROP INDEX IF EXISTS ix_books_pre_drafted_q1")

    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.drop_constraint("fk_books_pre_drafted_q1_id", type_="foreignkey")
        batch_op.drop_column("pre_drafted_q1_id")

    with op.batch_alter_table("quiz_questions", schema=None) as batch_op:
        batch_op.drop_index("ix_quiz_questions_session")
        batch_op.drop_index("ix_quiz_questions_concept")
        batch_op.drop_index("ix_quiz_questions_book_dedup")
    op.drop_table("quiz_questions")

    with op.batch_alter_table("quiz_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_quiz_sessions_book_status")
        batch_op.drop_index(batch_op.f("ix_quiz_sessions_book_id"))
        batch_op.drop_index("ix_quiz_sessions_book_created")
    op.drop_table("quiz_sessions")

    op.drop_table("quiz_dedup_state")
