"""v1.7a — anchor ContentType.ANNOTATION enum extension.

Schema-empty version anchor (FR-21, plan D4): the new
``ContentType.ANNOTATION`` enum value is runtime-only and intentionally NOT
added to the SQLite CHECK constraints on ``audio_files`` /
``audio_positions`` — annotation lookups never persist. This migration
exists solely to advance the version pin so future migrations have a
stable predecessor.

Revision ID: a8b9c0d1e2f3
Revises: 2026_05_02_audiobook
Create Date: 2026-05-04 00:00:00
"""

from collections.abc import Sequence

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "2026_05_02_audiobook"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
