"""Integration tests for v1.5 Alembic migrations.

Uses the conftest ``db_session`` fixture which applies ``Base.metadata.create_all``
with the v1.5 ORM shape. These tests verify the schema expectations that the
migrations are responsible for producing — they serve as both a spec check and
a regression guard for the ORM definitions that must stay in sync with the
migration SQL.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


# --- v1_5d: tags + taggables revival ---


@pytest.mark.asyncio
async def test_v1_5d_creates_tags_and_taggables_tables(db_session):
    result = await db_session.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name IN ('tags','taggables')"
        )
    )
    tables = {row[0] for row in result.fetchall()}
    assert tables == {"tags", "taggables"}


@pytest.mark.asyncio
async def test_v1_5d_tags_name_is_nocase_unique(db_session):
    await db_session.execute(text("INSERT INTO tags (name) VALUES ('strategy')"))
    await db_session.commit()
    with pytest.raises(IntegrityError):
        await db_session.execute(text("INSERT INTO tags (name) VALUES ('Strategy')"))
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_v1_5d_taggables_composite_pk(db_session):
    await db_session.execute(text("INSERT INTO tags (name) VALUES ('strategy')"))
    await db_session.execute(
        text(
            "INSERT INTO taggables (tag_id, taggable_type, taggable_id) "
            "SELECT id, 'book', 1 FROM tags WHERE name='strategy'"
        )
    )
    await db_session.commit()
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO taggables (tag_id, taggable_type, taggable_id) "
                "SELECT id, 'book', 1 FROM tags WHERE name='strategy'"
            )
        )
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_v1_5d_taggables_entity_index_exists(db_session):
    result = await db_session.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND tbl_name='taggables'"
        )
    )
    indexes = {row[0] for row in result.fetchall()}
    assert "ix_taggables_entity" in indexes


# --- v1_5e: annotation prefix + suffix ---


@pytest.mark.asyncio
async def test_v1_5e_annotations_has_prefix_suffix(db_session):
    result = await db_session.execute(text("PRAGMA table_info(annotations)"))
    columns = {row[1] for row in result.fetchall()}
    assert "prefix" in columns
    assert "suffix" in columns


@pytest.mark.asyncio
async def test_v1_5e_prefix_suffix_nullable(db_session):
    from app.db.models import Annotation, AnnotationType, ContentType

    ann = Annotation(
        content_type=ContentType.SECTION_CONTENT,
        content_id=1,
        type=AnnotationType.HIGHLIGHT,
        selected_text="test",
        text_start=0,
        text_end=4,
    )
    db_session.add(ann)
    await db_session.commit()
    await db_session.refresh(ann)
    assert ann.prefix is None
    assert ann.suffix is None
