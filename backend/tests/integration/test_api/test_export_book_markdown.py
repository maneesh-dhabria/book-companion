"""Integration tests for the new GET /api/v1/export/book/{id}?format=markdown shape."""

from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.main import create_app

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(engine, test_settings):
    """Override parent conftest client so it shares the test engine."""
    app = create_app()
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.settings = test_settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def _seed_book_with_summary(db_session):
    """Insert a Book + Author + BookSection + Summary. Returns (book_id, section_id)."""
    from app.db.models import (
        Author,
        Book,
        BookAuthor,
        BookSection,
        BookStatus,
        Summary,
        SummaryContentType,
    )

    book = Book(
        title="Test Export Book",
        file_data=b"",
        file_hash="hash-export-test",
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    author = Author(name="Test Author")
    db_session.add(author)
    await db_session.flush()
    db_session.add(BookAuthor(book_id=book.id, author_id=author.id))
    section = BookSection(
        book_id=book.id,
        title="Chapter 1",
        order_index=0,
        depth=0,
        content_md="content",
        section_type="chapter",
    )
    db_session.add(section)
    await db_session.flush()
    sec_summary = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=section.id,
        book_id=book.id,
        preset_name="test",
        facets_used={},
        prompt_text_sent="",
        model_used="test",
        input_char_count=0,
        summary_char_count=0,
        summary_md="Section 1 summary content.",
    )
    db_session.add(sec_summary)
    await db_session.flush()
    section.default_summary_id = sec_summary.id
    await db_session.commit()
    return book.id, section.id


async def test_filename_uses_slug(client, db_session):
    bid, _ = await _seed_book_with_summary(db_session)
    resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown")
    assert resp.status_code == 200
    cd = resp.headers["content-disposition"]
    today = date.today().strftime("%Y%m%d")
    assert f"test-export-book-summary-{today}.md" in cd


async def test_cache_control_set(client, db_session):
    bid, _ = await _seed_book_with_summary(db_session)
    resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown")
    assert resp.headers.get("cache-control") == "private, max-age=0"


async def test_x_empty_export_false_when_content(client, db_session):
    bid, _ = await _seed_book_with_summary(db_session)
    resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown")
    assert resp.headers.get("x-empty-export", "false") == "false"


async def test_x_empty_export_true_when_all_excluded(client, db_session):
    bid, sid = await _seed_book_with_summary(db_session)
    resp = await client.get(
        f"/api/v1/export/book/{bid}"
        f"?format=markdown"
        f"&include_book_summary=false"
        f"&include_toc=false"
        f"&include_annotations=false"
        f"&exclude_section={sid}"
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-empty-export") == "true"


async def test_invalid_exclude_section_returns_400(client, db_session):
    bid, _ = await _seed_book_with_summary(db_session)
    resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown&exclude_section=99999")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "99999" in detail
    assert "does not belong to" in detail


async def test_selection_querystring_filters_output(client, db_session):
    bid, _ = await _seed_book_with_summary(db_session)
    resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown&include_toc=false")
    assert resp.status_code == 200
    assert "## Table of Contents" not in resp.text


async def test_json_format_unchanged_byte_equal(client, db_session):
    """G6: existing JSON export shape unaffected by selection params.

    `exported_at` is wall-clock and naturally differs per call; compare the
    rest of the payload to assert selection params don't leak into the JSON.
    """
    bid, _ = await _seed_book_with_summary(db_session)
    resp_a = await client.get(f"/api/v1/export/book/{bid}?format=json")
    resp_b = await client.get(
        f"/api/v1/export/book/{bid}?format=json&include_toc=false&exclude_section=99999"
    )
    assert resp_a.status_code == 200 and resp_b.status_code == 200
    a, b = resp_a.json(), resp_b.json()
    a.pop("exported_at", None)
    b.pop("exported_at", None)
    assert a == b


async def test_slug_falls_back_for_cjk_only_title(client, db_session):
    from app.db.models import Book, BookStatus

    book = Book(
        title="北京概要",
        file_data=b"",
        file_hash="hash-cjk-export",
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.commit()
    resp = await client.get(f"/api/v1/export/book/{book.id}?format=markdown")
    cd = resp.headers["content-disposition"]
    today = date.today().strftime("%Y%m%d")
    assert f"book-{book.id}-summary-{today}.md" in cd


async def test_image_urls_never_survive(client, db_session):
    """G4: zero `/api/v1/images/` substrings in any exported markdown."""
    from app.db.models import (
        Book,
        BookSection,
        BookStatus,
        Summary,
        SummaryContentType,
    )

    book = Book(
        title="Imagey",
        file_data=b"",
        file_hash="hash-img",
        file_format="epub",
        file_size_bytes=0,
        status=BookStatus.COMPLETED,
    )
    db_session.add(book)
    await db_session.flush()
    sec = BookSection(
        book_id=book.id,
        title="C",
        order_index=0,
        depth=0,
        content_md="x",
        section_type="chapter",
    )
    db_session.add(sec)
    await db_session.flush()
    summ = Summary(
        content_type=SummaryContentType.SECTION,
        content_id=sec.id,
        book_id=book.id,
        preset_name="t",
        facets_used={},
        prompt_text_sent="",
        model_used="test",
        input_char_count=0,
        summary_char_count=0,
        summary_md='See ![figure](/api/v1/images/3) and <img src="/api/v1/images/4" />.',
    )
    db_session.add(summ)
    await db_session.flush()
    sec.default_summary_id = summ.id
    await db_session.commit()
    resp = await client.get(f"/api/v1/export/book/{book.id}?format=markdown")
    assert resp.status_code == 200
    assert "/api/v1/images/" not in resp.text
    assert "[Image: figure]" in resp.text


async def test_export_library_markdown_returns_410(client):
    resp = await client.get("/api/v1/export/library?format=markdown")
    assert resp.status_code == 410
    detail = resp.json()["detail"]
    assert "removed in v1.6" in detail
    assert "format=json" in detail
