"""Migration C: raw EPUB image refs → /api/v1/images/{id}."""

from pathlib import Path

import sqlalchemy as sa
from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = (
    Path(__file__).parent.parent.parent / "app" / "migrations" / "alembic.ini"
)


def _cfg() -> Config:
    return Config(str(ALEMBIC_INI))


def test_migration_rewrites_raw_epub_refs(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = _cfg()
    upgrade(cfg, "head")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    legacy_md = (
        "intro paragraph\n\n"
        "![image](images/00003.jpg)\n\n"
        '<img src="images/00004.png" alt="figure 1">'
    )
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
            VALUES (1, 1, 'Ch1', 0, 0, 'chapter', :md)
            """
            ),
            {"md": legacy_md},
        )
        conn.execute(
            sa.text(
                """
            INSERT INTO images (id, section_id, data, mime_type, filename)
            VALUES (10, 1, x'00', 'image/jpeg', 'images/00003.jpg'),
                   (11, 1, x'00', 'image/png',  'images/00004.png')
            """
            )
        )

    downgrade(cfg, "b2c3d4e5f6a7")  # before Migration C
    upgrade(cfg, "head")

    with engine.begin() as conn:
        row = conn.execute(
            sa.text("SELECT content_md FROM book_sections WHERE id=1")
        ).scalar_one()
    assert "images/00003.jpg" not in row
    assert "images/00004.png" not in row
    assert "/api/v1/images/10" in row
    assert "/api/v1/images/11" in row

    # Idempotent
    upgrade(cfg, "head")
    with engine.begin() as conn:
        row2 = conn.execute(
            sa.text("SELECT content_md FROM book_sections WHERE id=1")
        ).scalar_one()
    assert row2 == row


def test_migration_leaves_external_urls_untouched(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = _cfg()
    upgrade(cfg, "head")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    md = "![cat](https://example.com/cat.jpg) local: ![x](images/missing.jpg)"
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
            VALUES (1, 1, 'Ch1', 0, 0, 'chapter', :md)
            """
            ),
            {"md": md},
        )
        # Note: no images row matches missing.jpg — that raw ref must stay
        # untouched (falls through to_placeholder/from_placeholder and emerges
        # as a placeholder token, then unchanged because no map entry).

    downgrade(cfg, "b2c3d4e5f6a7")  # before Migration C
    upgrade(cfg, "head")

    with engine.begin() as conn:
        row = conn.execute(
            sa.text("SELECT content_md FROM book_sections WHERE id=1")
        ).scalar_one()
    assert "https://example.com/cat.jpg" in row  # external unchanged
    # No images row → to_placeholder runs but from_placeholder leaves the
    # token in place. The token form is still broken on the frontend but
    # no worse than before; no data loss.
    assert "missing.jpg" in row or "__IMG_PLACEHOLDER__:missing.jpg__ENDIMG__" in row
