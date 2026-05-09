"""T14 — /reading-state/by-book/{id} returns all-device rows (FR-17, P1).

Regression tests for the bug-fix: previously the endpoint UA-filtered, so the
Quiz tab's D31 default-scope logic could not see reading activity from other
devices. The fix drops the UA filter and adds `most_recent_section_ids`.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_book_with_sections(app, *, book_id: int = 1, section_ids: list[int]):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (:id, 'T', x'00', :hash, 'epub', 1, 'COMPLETED')
                """
            ),
            {"id": book_id, "hash": f"h{book_id}"},
        )
        for idx, sid in enumerate(section_ids):
            await session.execute(
                text(
                    "INSERT INTO book_sections (id, book_id, title, order_index, depth, "
                    "section_type, content_md) "
                    "VALUES (:sid, :bid, :title, :oi, 0, 'chapter', 'c')"
                ),
                {"sid": sid, "bid": book_id, "title": f"Ch {idx}", "oi": idx},
            )
        await session.commit()


async def _seed_reading_state(
    app,
    *,
    book_id: int,
    section_id: int | None,
    user_agent: str,
    updated_at: datetime | None = None,
):
    """Insert via ORM so the DateTime column gets dialect-correct binding,
    then UPDATE the timestamp (server_default would otherwise clobber it)."""
    from app.db.models import ReadingState

    factory = app.state.session_factory
    async with factory() as session:
        rs = ReadingState(
            user_agent=user_agent,
            book_id=book_id,
            section_id=section_id,
            content_mode="summary",
        )
        session.add(rs)
        await session.flush()
        if updated_at is not None:
            rs.updated_at = updated_at
            await session.flush()
        await session.commit()


@pytest.mark.asyncio
async def test_by_book_returns_all_devices(app, client: AsyncClient):
    """Two devices, two sections — the requesting device sees both."""
    await _seed_book_with_sections(app, book_id=1, section_ids=[10, 12])
    await _seed_reading_state(app, book_id=1, section_id=10, user_agent="DeviceA")
    await _seed_reading_state(app, book_id=1, section_id=12, user_agent="DeviceB")

    # Request from a fresh device — under the OLD code this returned nulls.
    r = await client.get(
        "/api/v1/reading-state/by-book/1",
        headers={"User-Agent": "DeviceC"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert sorted(payload["most_recent_section_ids"]) == [10, 12]
    # last_section_id is the most recent (DeviceB's row, last inserted)
    assert payload["last_book_id"] == 1
    assert payload["last_section_id"] in (10, 12)


@pytest.mark.asyncio
async def test_by_book_48h_window_only(app, client: AsyncClient):
    """Rows older than 48h should not appear in most_recent_section_ids."""
    await _seed_book_with_sections(app, book_id=2, section_ids=[20, 22])
    fresh = datetime.now(UTC) - timedelta(hours=1)
    stale = datetime.now(UTC) - timedelta(hours=50)
    await _seed_reading_state(app, book_id=2, section_id=20, user_agent="DeviceA", updated_at=fresh)
    await _seed_reading_state(app, book_id=2, section_id=22, user_agent="DeviceB", updated_at=stale)

    r = await client.get(
        "/api/v1/reading-state/by-book/2",
        headers={"User-Agent": "DeviceC"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["most_recent_section_ids"] == [20]


@pytest.mark.asyncio
async def test_by_book_empty_when_no_rows(app, client: AsyncClient):
    """Book with no reading-state rows → empty most_recent_section_ids and null fields."""
    await _seed_book_with_sections(app, book_id=3, section_ids=[30])

    r = await client.get(
        "/api/v1/reading-state/by-book/3",
        headers={"User-Agent": "DeviceX"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["most_recent_section_ids"] == []
    assert payload["last_book_id"] is None
    assert payload["last_section_id"] is None


@pytest.mark.asyncio
async def test_continue_endpoint_still_filters_by_device(app, client: AsyncClient):
    """CLAUDE.md gotcha #27: /continue MUST remain UA-filtered. Confirm T14
    did NOT touch the /continue contract."""
    await _seed_book_with_sections(app, book_id=4, section_ids=[40])
    await _seed_reading_state(app, book_id=4, section_id=40, user_agent="DeviceA")

    # From DeviceA's perspective, /continue should NOT see DeviceA's own row.
    r = await client.get(
        "/api/v1/reading-state/continue",
        headers={"User-Agent": "DeviceA"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("last_section_id") != 40
