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


# --- v1_5f: books suggested_tags + failure columns ---


@pytest.mark.asyncio
async def test_v1_5f_books_has_suggested_tags_and_failure_columns(db_session):
    result = await db_session.execute(text("PRAGMA table_info(books)"))
    columns = {row[1] for row in result.fetchall()}
    for col in (
        "suggested_tags_json",
        "last_summary_failure_code",
        "last_summary_failure_stderr",
        "last_summary_failure_at",
    ):
        assert col in columns, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_v1_5f_suggested_tags_stores_list(db_session):
    from app.db.models import Book, BookStatus

    book = Book(
        title="Test",
        file_data=b"",
        file_hash="h" * 64,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
        suggested_tags_json=["strategy", "value-chain"],
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    assert book.suggested_tags_json == ["strategy", "value-chain"]


# --- v1_5a data migration: summary image rewrite ---


@pytest.mark.asyncio
async def test_v1_5a_rewrites_existing_summary_placeholders(db_session):
    from app.db.models import (
        Book,
        BookSection,
        BookStatus,
        Image,
        Summary,
        SummaryContentType,
    )
    from app.services.parser.image_url_rewrite import from_placeholder

    book = Book(
        title="T",
        file_data=b"",
        file_hash="mig1" * 16,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    section = BookSection(
        book_id=book.id, title="c", order_index=0, depth=0, content_md="x"
    )
    db_session.add(section)
    await db_session.flush()
    img = Image(
        section_id=section.id, data=b"", mime_type="image/png", filename="pic.png"
    )
    db_session.add(img)
    await db_session.flush()
    await db_session.refresh(img)
    summary = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=section.id,
        book_id=book.id,
        facets_used={},
        prompt_text_sent="",
        model_used="x",
        input_char_count=1,
        summary_char_count=1,
        summary_md="pre __IMG_PLACEHOLDER__:pic.png__ENDIMG__ post",
    )
    db_session.add(summary)
    await db_session.commit()

    # Simulate the migration body inline.
    imgs_rows = {"pic.png": img.id}
    new_md = from_placeholder(summary.summary_md, imgs_rows, on_missing="strip")
    assert f"/api/v1/images/{img.id}" in new_md
    assert "__IMG_PLACEHOLDER__" not in new_md


# --- v1_5b data migration: blockquote normalize ---


@pytest.mark.asyncio
async def test_v1_5b_normalizes_nested_blockquotes(db_session):
    from app.db.models import Book, BookSection, BookStatus
    from app.services.parser.blockquote_normalizer import normalize_blockquotes

    book = Book(
        title="T",
        file_data=b"",
        file_hash="mig2" * 16,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    section = BookSection(
        book_id=book.id,
        title="c",
        order_index=0,
        depth=0,
        content_md="> > nested quote",
    )
    db_session.add(section)
    await db_session.commit()
    new_md = normalize_blockquotes(section.content_md)
    assert "> >" not in new_md
    # Idempotent
    assert normalize_blockquotes(new_md) == new_md


# --- v1_5c data migration: annotation prefix + suffix ---


@pytest.mark.asyncio
async def test_v1_5c_backfills_prefix_suffix(db_session):
    from app.db.models import (
        Annotation,
        AnnotationType,
        Book,
        BookSection,
        BookStatus,
        ContentType,
    )

    book = Book(
        title="T",
        file_data=b"",
        file_hash="mig3" * 16,
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    content = "start-of-content " + ("x" * 50) + "TARGET" + ("y" * 50) + "end"
    section = BookSection(
        book_id=book.id,
        title="c",
        order_index=0,
        depth=0,
        content_md=content,
    )
    db_session.add(section)
    await db_session.flush()
    start = content.index("TARGET")
    end = start + len("TARGET")
    ann = Annotation(
        content_type=ContentType.SECTION_CONTENT,
        content_id=section.id,
        type=AnnotationType.HIGHLIGHT,
        selected_text="TARGET",
        text_start=start,
        text_end=end,
    )
    db_session.add(ann)
    await db_session.commit()
    # Apply the migration body inline.
    CONTEXT = 32
    ann.prefix = content[max(0, start - CONTEXT) : start]
    ann.suffix = content[end : end + CONTEXT]
    await db_session.commit()
    await db_session.refresh(ann)
    assert len(ann.prefix) == CONTEXT
    assert len(ann.suffix) == CONTEXT
    assert ann.prefix.endswith("x" * 32)  # chars before TARGET
