"""v1_5_1 collapse reading presets

FR-F4.1, FR-F4.5, D14, P3, P5, P13.

* Capture any legacy ``is_active=true`` preset name to a sidecar text file
  in the data directory so the frontend can adopt it on first launch.
* Delete user-created rows (``is_system=0``).
* Drop ``is_system`` and ``is_active`` columns.
* Seed the six v1.5 system presets idempotently (UNIQUE on ``name``).

Revision ID: a5459240fea0
Revises: e1f2a3b4c5d6
Create Date: 2026-04-25 12:29:59.660327
"""

import os
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


revision: str = "a5459240fea0"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SYSTEM_PRESETS: list[tuple[str, str, int, float, int, str]] = [
    ("Light", "Georgia", 16, 1.6, 720, "light"),
    ("Sepia", "Georgia", 16, 1.6, 720, "sepia"),
    ("Dark", "Georgia", 16, 1.6, 720, "dark"),
    ("Night", "Georgia", 16, 1.6, 720, "night"),
    ("Paper", "Georgia", 16, 1.6, 720, "paper"),
    ("High Contrast", "Georgia", 16, 1.6, 720, "contrast"),
]


def _resolve_data_dir(conn) -> Path:
    """Env-var first, DB-path-fallback. Avoids picking up the user's real
    settings.yaml during isolated test runs where only the env vars are set."""
    env_dir = os.environ.get("BOOKCOMPANION_DATA__DIRECTORY")
    if env_dir:
        return Path(env_dir)
    db_path = conn.engine.url.database
    if db_path:
        return Path(db_path).parent
    from app.config import Settings  # last-resort fallback

    return Path(Settings().data.directory)


def upgrade() -> None:
    conn = op.get_bind()

    # Detect whether this DB still has the v1.5 columns — re-runs against
    # an already-collapsed schema must be a no-op (idempotent guard).
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(reading_presets)"))}
    has_legacy_columns = "is_system" in cols and "is_active" in cols

    # 1. Capture the legacy active preset name (if any) to a sidecar file.
    if has_legacy_columns:
        row = conn.execute(
            sa.text("SELECT name FROM reading_presets WHERE is_active = 1 LIMIT 1")
        ).fetchone()
        if row is not None:
            data_dir = _resolve_data_dir(conn)
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "migration_v1_5_1_legacy_active.txt").write_text(row[0])

        # 2. DELETE user-created rows.
        conn.execute(sa.text("DELETE FROM reading_presets WHERE is_system = 0"))

        # 3. Drop the columns (SQLite-safe via batch_alter_table).
        with op.batch_alter_table("reading_presets") as batch_op:
            batch_op.drop_column("is_system")
            batch_op.drop_column("is_active")

    # 4. Seed the 6 system presets idempotently.
    existing = {r[0] for r in conn.execute(sa.text("SELECT name FROM reading_presets"))}
    for name, ff, fs, ls, cw, theme in _SYSTEM_PRESETS:
        if name in existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO reading_presets("
                "name, font_family, font_size_px, line_spacing, "
                "content_width_px, theme) "
                "VALUES (:n, :ff, :fs, :ls, :cw, :theme)"
            ),
            dict(n=name, ff=ff, fs=fs, ls=ls, cw=cw, theme=theme),
        )


def downgrade() -> None:
    """Forward-only (D14). Implemented as a no-op so alembic can step past
    this revision when other tests downgrade further through the chain.
    The upgrade body is fully idempotent on re-runs, so a downgrade-then-
    upgrade still lands in a consistent state."""
    pass
