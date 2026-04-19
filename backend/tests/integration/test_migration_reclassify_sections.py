from datetime import datetime, timedelta
from pathlib import Path

import sqlalchemy as sa
from alembic.command import downgrade, upgrade
from alembic.config import Config

ALEMBIC_INI = (
    Path(__file__).parent.parent.parent / "app" / "migrations" / "alembic.ini"
)


def _seed(conn):
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
        VALUES
          (1, 1, 'Copyright', 0, 0, 'chapter', '\u00a9 2024 ...'),
          (2, 1, 'Acknowledgments', 1, 0, 'chapter', 'Thanks to ...'),
          (3, 1, 'Part One', 2, 0, 'chapter', 'short'),
          (4, 1, 'Chapter 1: Right Mindset', 3, 0, 'chapter', 'real chapter body...'),
          (5, 1, 'Glossary', 4, 0, 'chapter', 'terms and defs ...')
        """
        )
    )
    now = datetime.utcnow()
    for sid, offset in [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4)]:
        conn.execute(
            sa.text(
                """
            INSERT INTO summaries (id, content_type, content_id, book_id,
                                   facets_used, prompt_text_sent, model_used,
                                   input_char_count, summary_char_count, summary_md,
                                   created_at)
            VALUES (:id, 'section', :cid, 1, '{}', 'p', 'm',
                    10, 5, 's', :ts)
            """
            ),
            {
                "id": 100 + sid,
                "cid": sid,
                "ts": now + timedelta(seconds=offset),
            },
        )
    conn.execute(
        sa.text(
            """
        INSERT INTO summaries (id, content_type, content_id, book_id,
                               facets_used, prompt_text_sent, model_used,
                               input_char_count, summary_char_count, summary_md,
                               created_at)
        VALUES (999, 'section', 2, 1, '{}', 'p', 'm',
                10, 5, 's', :ts)
        """
        ),
        {"ts": now - timedelta(minutes=2)},
    )
    for sid, did in [(1, 101), (2, 102), (3, 103), (4, 104), (5, 105)]:
        conn.execute(
            sa.text(
                "UPDATE book_sections SET default_summary_id = :d WHERE id = :s"
            ),
            {"d": did, "s": sid},
        )


def test_migration_reclassifies_and_prunes(tmp_path, monkeypatch):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = Config(str(ALEMBIC_INI))
    upgrade(cfg, "head")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _seed(conn)

    downgrade(cfg, "a1b2c3d4e5f6")  # before Migration B
    upgrade(cfg, "head")

    with engine.begin() as conn:
        types = {
            r.id: r.section_type
            for r in conn.execute(
                sa.text("SELECT id, section_type FROM book_sections ORDER BY id")
            )
        }
        defaults = {
            r.id: r.default_summary_id
            for r in conn.execute(
                sa.text(
                    "SELECT id, default_summary_id FROM book_sections ORDER BY id"
                )
            )
        }
        by_section = {
            r.content_id: r.c
            for r in conn.execute(
                sa.text(
                    "SELECT content_id, count(*) c FROM summaries "
                    "WHERE content_type='section' GROUP BY content_id"
                )
            ).fetchall()
        }

    assert types == {
        1: "copyright",
        2: "acknowledgments",
        3: "part_header",
        4: "chapter",
        5: "glossary",
    }
    assert by_section.get(1, 0) == 0
    assert defaults[1] is None
    assert by_section.get(2, 0) == 2
    assert defaults[2] == 999
    assert by_section.get(3, 0) == 0
    assert defaults[3] is None
    assert types[4] == "chapter"
    assert defaults[4] == 104
    assert by_section.get(5, 0) == 1
    assert defaults[5] == 105

    upgrade(cfg, "head")
    with engine.begin() as conn:
        types2 = {
            r.id: r.section_type
            for r in conn.execute(
                sa.text("SELECT id, section_type FROM book_sections ORDER BY id")
            )
        }
    assert types2 == types


def test_migration_prunes_multi_batch_frontmatter_with_no_user_curated(
    tmp_path, monkeypatch
):
    """Regression (B1): when a section has multiple auto-summaries all within the
    60s batch window and no older user-curated summary, reclassifying it as
    front-matter must still prune and clear the default. Without the fix, the
    section retained its auto-generated default pointing at a batch-window row.
    """
    db_path = tmp_path / "library.db"
    monkeypatch.setenv(
        "BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}"
    )
    cfg = Config(str(ALEMBIC_INI))
    upgrade(cfg, "head")

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
            VALUES (1, 1, 'Copyright', 0, 0, 'chapter', '\u00a9 2024')
            """
            )
        )
        now = datetime.utcnow()
        # Two auto summaries, both within the 60-second batch window.
        for sid, offset in [(100, 0), (101, 10)]:
            conn.execute(
                sa.text(
                    """
                INSERT INTO summaries (
                  id, content_type, content_id, book_id, facets_used,
                  prompt_text_sent, model_used, input_char_count,
                  summary_char_count, summary_md, created_at
                ) VALUES (:id, 'section', 1, 1, '{}', 'p', 'm',
                          10, 5, 's', :ts)
                """
                ),
                {"id": sid, "ts": now + timedelta(seconds=offset)},
            )
        conn.execute(
            sa.text(
                "UPDATE book_sections SET default_summary_id = 100 WHERE id = 1"
            )
        )

    downgrade(cfg, "a1b2c3d4e5f6")  # before Migration B
    upgrade(cfg, "head")

    with engine.begin() as conn:
        t = conn.execute(
            sa.text("SELECT section_type, default_summary_id FROM book_sections WHERE id = 1")
        ).one()
        remaining = conn.execute(
            sa.text(
                "SELECT count(*) FROM summaries "
                "WHERE content_type='section' AND content_id = 1"
            )
        ).scalar()

    assert t.section_type == "copyright"
    assert t.default_summary_id is None
    assert remaining == 0
