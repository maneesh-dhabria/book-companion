"""B5 — v1_5b legacy image:N rewrite migration."""

from pathlib import Path

import sqlalchemy as sa
from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = (
    Path(__file__).parent.parent.parent / "app" / "migrations" / "alembic.ini"
)


def _cfg() -> Config:
    return Config(str(ALEMBIC_INI))


def _seed(engine):
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
            INSERT INTO books (id, title, file_data, file_hash, file_format,
                               file_size_bytes, status)
            VALUES (1, 'T', x'00', 'h1', 'epub', 1, 'COMPLETED')
            """
            )
        )
        conn.execute(
            sa.text(
                """
            INSERT INTO book_sections (id, book_id, title, order_index, depth,
                                       section_type, content_md)
            VALUES (1, 1, 'Ch1', 0, 0, 'chapter', 'c')
            """
            )
        )
        conn.execute(
            sa.text(
                """
            INSERT INTO images (id, section_id, data, mime_type, filename)
            VALUES (5, 1, x'00', 'image/jpeg', 'img.jpg')
            """
            )
        )
        conn.execute(
            sa.text(
                """
            INSERT INTO summaries (id, content_type, content_id, book_id,
                                   facets_used, prompt_text_sent, model_used,
                                   input_char_count, summary_char_count,
                                   summary_md)
            VALUES (1, 'section_content', 1, 1,
                    '{}', 'p', 'claude', 10, 10,
                    'before ![x](image:5) after')
            """
            )
        )


def test_migration_rewrites_legacy_image_refs(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = _cfg()
    # Step to the revision before B5 (current head is e0c48efb7afe).
    upgrade(cfg, "0a1b2c3d4e5f")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    _seed(engine)

    upgrade(cfg, "head")

    with engine.begin() as conn:
        md = conn.execute(
            sa.text("SELECT summary_md FROM summaries WHERE id=1")
        ).scalar_one()
    assert "image:5" not in md
    assert "/api/v1/images/5" in md


def test_migration_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = _cfg()
    upgrade(cfg, "0a1b2c3d4e5f")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    _seed(engine)
    upgrade(cfg, "head")
    with engine.begin() as conn:
        first = conn.execute(
            sa.text("SELECT summary_md FROM summaries WHERE id=1")
        ).scalar_one()
    # Re-running upgrade should be a no-op (already at head; downgrade then upgrade).
    downgrade(cfg, "0a1b2c3d4e5f")
    upgrade(cfg, "head")
    with engine.begin() as conn:
        second = conn.execute(
            sa.text("SELECT summary_md FROM summaries WHERE id=1")
        ).scalar_one()
    assert first == second
    assert "/api/v1/images/5" in second


def test_migration_strips_orphan_legacy_refs(tmp_path, monkeypatch):
    """Refs to image_ids not in the book's images table are stripped to [alt](#)."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = _cfg()
    upgrade(cfg, "0a1b2c3d4e5f")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
            INSERT INTO books (id, title, file_data, file_hash, file_format,
                               file_size_bytes, status)
            VALUES (1, 'T', x'00', 'h1', 'epub', 1, 'COMPLETED')
            """
            )
        )
        conn.execute(
            sa.text(
                """
            INSERT INTO book_sections (id, book_id, title, order_index, depth,
                                       section_type, content_md)
            VALUES (1, 1, 'Ch1', 0, 0, 'chapter', 'c')
            """
            )
        )
        conn.execute(
            sa.text(
                """
            INSERT INTO summaries (id, content_type, content_id, book_id,
                                   facets_used, prompt_text_sent, model_used,
                                   input_char_count, summary_char_count,
                                   summary_md)
            VALUES (1, 'section_content', 1, 1,
                    '{}', 'p', 'claude', 10, 10,
                    '![fig](image:99) tail')
            """
            )
        )
    upgrade(cfg, "head")
    with engine.begin() as conn:
        md = conn.execute(
            sa.text("SELECT summary_md FROM summaries WHERE id=1")
        ).scalar_one()
    assert "image:99" not in md
    assert "[fig](#)" in md
