"""v1.5e schema — annotations prefix + suffix columns

Nullable TEXT columns used by the hybrid annotation anchor algorithm
(FR-C5.5). 32-char context snippets saved at annotation-create time and
consulted when text_start/end offsets fail to match post-migration content.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-24 09:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    with op.batch_alter_table("annotations", schema=None) as batch_op:
        if not _has_column("annotations", "prefix"):
            batch_op.add_column(sa.Column("prefix", sa.Text(), nullable=True))
        if not _has_column("annotations", "suffix"):
            batch_op.add_column(sa.Column("suffix", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("annotations", schema=None) as batch_op:
        if _has_column("annotations", "suffix"):
            batch_op.drop_column("suffix")
        if _has_column("annotations", "prefix"):
            batch_op.drop_column("prefix")
