"""B8 — v1.5b preset typography migration (FR-37, NFR-06)."""

from pathlib import Path

import sqlalchemy as sa
from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = Path(__file__).parent.parent.parent / "app" / "migrations" / "alembic.ini"


# Spec §11.3 target values per system preset name.
EXPECTED: dict[str, tuple[str, int, float, int, str]] = {
    "Light": ("Georgia", 16, 1.6, 720, "light"),
    "Sepia": ("Georgia", 17, 1.7, 680, "sepia"),
    "Dark": ("Inter", 16, 1.6, 720, "dark"),
    "Night": ("Inter", 18, 1.7, 680, "night"),
    "Paper": ("Lora", 17, 1.8, 640, "paper"),
    "High Contrast": ("Inter", 18, 1.7, 700, "contrast"),
}


def _cfg() -> Config:
    return Config(str(ALEMBIC_INI))


def _read_presets(engine) -> dict[str, tuple]:
    with engine.begin() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT name, font_family, font_size_px, line_spacing, "
                "content_width_px, theme FROM reading_presets"
            )
        ).fetchall()
    return {r[0]: tuple(r[1:]) for r in rows}


def test_migration_updates_presets_to_spec_values(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    cfg = _cfg()
    upgrade(cfg, "head")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    by_name = _read_presets(engine)
    for name, expected in EXPECTED.items():
        assert by_name[name] == expected, f"{name}: {by_name[name]} != {expected}"


def test_migration_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    cfg = _cfg()
    upgrade(cfg, "head")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    first = _read_presets(engine)

    # Re-run by stepping back one revision then forward.
    downgrade(cfg, "0a1b2c3d4e5f")  # before B5/B8
    upgrade(cfg, "head")
    second = _read_presets(engine)
    assert first == second


def test_migration_preserves_user_customizations(tmp_path, monkeypatch):
    """If a user already changed Light away from the legacy tuple, leave it alone."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
    cfg = _cfg()
    # Stop just before B8 lands.
    upgrade(cfg, "e0c48efb7afe")  # B5 head, B8 not yet applied

    engine = sa.create_engine(f"sqlite:///{db_path}")
    # User changed Light to Inter/14/1.5/720.
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE reading_presets SET font_family='Inter', "
                "font_size_px=14, line_spacing=1.5 WHERE name='Light'"
            )
        )

    upgrade(cfg, "head")

    by_name = _read_presets(engine)
    # Light row preserved (NOT updated to spec).
    assert by_name["Light"][0] == "Inter"
    assert by_name["Light"][1] == 14
    assert by_name["Light"][2] == 1.5
    # Sepia (still legacy) was migrated to spec values.
    assert by_name["Sepia"] == EXPECTED["Sepia"]
