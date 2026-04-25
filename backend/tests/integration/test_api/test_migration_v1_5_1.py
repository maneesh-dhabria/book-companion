"""Migration v1_5_1 — collapse reading_presets (FR-F4.1, FR-F4.5)."""

import sqlite3
import subprocess
from pathlib import Path

import pytest

REPO_BACKEND = Path(__file__).parents[3]
ALEMBIC_INI = "app/migrations/alembic.ini"


def _alembic_upgrade(target: str, db_path: Path, data_dir: Path) -> None:
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": __import__("os").environ.get("HOME", ""),
        "BOOKCOMPANION_DATABASE__URL": f"sqlite+aiosqlite:///{db_path}",
        "BOOKCOMPANION_DATA__DIRECTORY": str(data_dir),
    }
    subprocess.check_call(
        ["uv", "run", "alembic", "-c", ALEMBIC_INI, "upgrade", target],
        cwd=REPO_BACKEND,
        env=env,
    )


@pytest.mark.asyncio
async def test_migration_drops_user_rows_columns_and_writes_hint(tmp_path):
    db_path = tmp_path / "library.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # 1. Build a baseline DB at the prior head with one user preset (active).
    _alembic_upgrade("e1f2a3b4c5d6", db_path, data_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO reading_presets("
            "name, font_family, font_size_px, line_spacing, content_width_px, "
            "theme, is_system, is_active) "
            "VALUES('LegacyUserPreset', 'Inter', 14, 1.4, 700, 'sepia', 0, 1)"
        )
        conn.commit()

    # 2. Run the new migration to head.
    _alembic_upgrade("head", db_path, data_dir)

    # 3. Assert: user row gone, columns gone, sidecar written, 6 system presets seeded.
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM reading_presets").fetchall()
        names = sorted(r[0] for r in rows)
        assert "LegacyUserPreset" not in names
        assert {"Light", "Sepia", "Dark", "Night", "Paper", "High Contrast"}.issubset(
            set(names)
        )
        cols = [r[1] for r in conn.execute("PRAGMA table_info(reading_presets)").fetchall()]
        assert "is_system" not in cols
        assert "is_active" not in cols

    hint_path = data_dir / "migration_v1_5_1_legacy_active.txt"
    assert hint_path.exists()
    assert hint_path.read_text().strip() == "LegacyUserPreset"


@pytest.mark.asyncio
async def test_migration_no_active_no_hint_file(tmp_path):
    db_path = tmp_path / "library.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _alembic_upgrade("head", db_path, data_dir)
    hint_path = data_dir / "migration_v1_5_1_legacy_active.txt"
    assert not hint_path.exists()


@pytest.mark.asyncio
async def test_migration_idempotent_on_rerun(tmp_path):
    db_path = tmp_path / "library.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _alembic_upgrade("head", db_path, data_dir)
    # Snapshot the seeded rows.
    with sqlite3.connect(db_path) as conn:
        before = sorted(r[0] for r in conn.execute("SELECT name FROM reading_presets").fetchall())
    # Re-run head — alembic emits no-op.
    _alembic_upgrade("head", db_path, data_dir)
    with sqlite3.connect(db_path) as conn:
        after = sorted(r[0] for r in conn.execute("SELECT name FROM reading_presets").fetchall())
    assert before == after
