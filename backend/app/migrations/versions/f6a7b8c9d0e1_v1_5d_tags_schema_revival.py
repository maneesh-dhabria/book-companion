"""v1.5d schema — tags + taggables revival

Re-creates ``tags`` and ``taggables`` with:
* ``tags.name`` NOCASE-collated unique (case-insensitive dedupe)
* ``taggables`` composite PK ``(tag_id, taggable_type, taggable_id)``
  + ``created_at`` + ``ix_taggables_entity (taggable_type, taggable_id)``

The initial migration created simpler versions; they have never carried
production data (tag feature shipped dormant), so we drop-and-recreate to
get the new collation and index in one step — SQLite cannot ALTER COLLATE
in place.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-24 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _has_table("taggables"):
        op.drop_table("taggables")
    if _has_table("tags"):
        op.drop_table("tags")

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=200, collation="NOCASE"),
            nullable=False,
        ),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )

    op.create_table(
        "taggables",
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("taggable_type", sa.String(length=50), nullable=False),
        sa.Column("taggable_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tag_id", "taggable_type", "taggable_id"),
    )
    op.create_index(
        "ix_taggables_entity",
        "taggables",
        ["taggable_type", "taggable_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_taggables_entity", table_name="taggables")
    op.drop_table("taggables")
    op.drop_table("tags")
    # Re-create the pre-v1.5d shape so downgrade leaves a valid schema.
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "taggables",
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("taggable_type", sa.String(length=50), nullable=False),
        sa.Column("taggable_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tag_id", "taggable_type", "taggable_id"),
    )
