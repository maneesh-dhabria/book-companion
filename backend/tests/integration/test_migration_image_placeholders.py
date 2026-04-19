from pathlib import Path

import sqlalchemy as sa
from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = (
    Path(__file__).parent.parent.parent / "app" / "migrations" / "alembic.ini"
)


def _cfg() -> Config:
    return Config(str(ALEMBIC_INI))


def test_migration_rewrites_placeholders(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", db_url)

    cfg = _cfg()
    upgrade(cfg, "head")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    legacy_md = (
        "![a](__IMG_PLACEHOLDER__:foo.jpg__ENDIMG__) "
        "![](__IMG_PLACEHOLDER__:bar.png__ENDIMG__)"
    )
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
            INSERT INTO books (id, title, file_data, file_hash, file_format,
                               file_size_bytes, status)
            VALUES (1, 'Test', x'00', 'hash1', 'epub', 1, 'COMPLETED')
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
            VALUES (10, 1, x'00', 'image/jpeg', 'foo.jpg'),
                   (11, 1, x'00', 'image/png',  'bar.png')
            """
            )
        )

    downgrade(cfg, "e152941ea209")
    upgrade(cfg, "head")

    with engine.begin() as conn:
        row = conn.execute(
            sa.text("SELECT content_md FROM book_sections WHERE id=1")
        ).scalar_one()
    assert "__IMG_PLACEHOLDER__" not in row
    assert "/api/v1/images/10" in row
    assert "/api/v1/images/11" in row

    upgrade(cfg, "head")
    with engine.begin() as conn:
        row2 = conn.execute(
            sa.text("SELECT content_md FROM book_sections WHERE id=1")
        ).scalar_one()
    assert row2 == row


def test_migration_skips_section_without_images(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = _cfg()
    upgrade(cfg, "head")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
            INSERT INTO books (id, title, file_data, file_hash, file_format,
                               file_size_bytes, status)
            VALUES (1, 'Test', x'00', 'hash1', 'epub', 1, 'COMPLETED')
            """
            )
        )
        conn.execute(
            sa.text(
                """
            INSERT INTO book_sections (id, book_id, title, order_index, depth,
                                       section_type, content_md)
            VALUES (1, 1, 'Ch1', 0, 0, 'chapter',
                    '![](__IMG_PLACEHOLDER__:missing.jpg__ENDIMG__)')
            """
            )
        )
    upgrade(cfg, "head")
    with engine.begin() as conn:
        row = conn.execute(
            sa.text("SELECT content_md FROM book_sections WHERE id=1")
        ).scalar_one()
    assert "__IMG_PLACEHOLDER__:missing.jpg__ENDIMG__" in row
