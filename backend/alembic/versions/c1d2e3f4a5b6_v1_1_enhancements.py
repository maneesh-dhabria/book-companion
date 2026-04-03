"""V1.1 enhancements: Summary model, SummaryContentType enum, schema changes.

Revision ID: c1d2e3f4a5b6
Revises: bb35febd1383
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "bb35febd1383"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create SummaryContentType enum
    summary_content_type = sa.Enum(
        "section", "book", "concept", "annotation",
        name="summarycontenttype",
    )
    summary_content_type.create(op.get_bind(), checkfirst=True)

    # 2. Create summaries table
    op.create_table(
        "summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "content_type",
            sa.Enum("section", "book", "concept", "annotation", name="summarycontenttype", create_type=False),
            nullable=False,
        ),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preset_name", sa.String(200), nullable=True),
        sa.Column("facets_used", sa.JSON(), nullable=False),
        sa.Column("prompt_text_sent", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("input_char_count", sa.Integer(), nullable=False),
        sa.Column("summary_char_count", sa.Integer(), nullable=False),
        sa.Column("summary_md", sa.Text(), nullable=False),
        sa.Column("eval_json", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_summaries_content", "summaries", ["content_type", "content_id"])
    op.create_index("ix_summaries_book_id", "summaries", ["book_id"])
    op.create_index("ix_summaries_created_at", "summaries", ["created_at"])

    # 3. Add default_summary_id to books
    op.add_column("books", sa.Column("default_summary_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_books_default_summary_id",
        "books",
        "summaries",
        ["default_summary_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Add default_summary_id and derived_from to book_sections
    op.add_column("book_sections", sa.Column("default_summary_id", sa.BigInteger(), nullable=True))
    op.add_column("book_sections", sa.Column("derived_from", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_book_sections_default_summary_id",
        "book_sections",
        "summaries",
        ["default_summary_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. Drop ix_book_sections_summary_status index
    op.drop_index("ix_book_sections_summary_status", table_name="book_sections")

    # 6. Drop columns from book_sections
    op.drop_column("book_sections", "summary_md")
    op.drop_column("book_sections", "summary_status")
    op.drop_column("book_sections", "summary_version")
    op.drop_column("book_sections", "summary_model")
    op.drop_column("book_sections", "summary_eval")
    op.drop_column("book_sections", "user_edited")

    # 7. Drop columns from books
    op.drop_column("books", "overall_summary")
    op.drop_column("books", "overall_summary_eval")

    # 8. Drop SummaryStatus enum type
    sa.Enum(name="summarystatus").drop(op.get_bind(), checkfirst=True)

    # 9. Add summary_id to eval_traces
    op.add_column("eval_traces", sa.Column("summary_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_eval_traces_summary_id",
        "eval_traces",
        "summaries",
        ["summary_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 10. Truncate eval_traces (old data references removed columns)
    op.execute("TRUNCATE TABLE eval_traces")


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for V1.1 migration")
