"""B6 — GET /api/v1/processing/{job_id} endpoint (FR-10, FR-11)."""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text


async def _seed_book(app, book_id: int = 1, title: str = "T"):
    factory = app.state.session_factory
    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO books (id, title, file_data, file_hash, file_format,
                                   file_size_bytes, status)
                VALUES (:id, :title, x'00', :hash, 'epub', 1, 'COMPLETED')
                """
            ),
            {"id": book_id, "title": title, "hash": f"h{book_id}"},
        )
        await session.commit()


async def _seed_job(
    app,
    *,
    book_id: int,
    status: str,
    started: bool = False,
    completed: bool = False,
    error: str | None = None,
    request_params: dict | None = None,
    progress: dict | None = None,
) -> int:
    factory = app.state.session_factory
    async with factory() as session:
        cols = ["book_id", "status", "step", "pid"]
        vals = [str(book_id), f"'{status}'", "'SUMMARIZE'", str(os.getpid())]
        if started:
            cols.append("started_at")
            vals.append("CURRENT_TIMESTAMP")
        if completed:
            cols.append("completed_at")
            vals.append("CURRENT_TIMESTAMP")
        sql = (
            f"INSERT INTO processing_jobs ({', '.join(cols)}) "
            f"VALUES ({', '.join(vals)}) RETURNING id"
        )
        row = (await session.execute(text(sql))).scalar_one()
        # Update the JSON / error_message columns separately for clarity.
        if request_params is not None or progress is not None or error is not None:
            import json as _json

            await session.execute(
                text(
                    "UPDATE processing_jobs SET "
                    "request_params = :rp, progress = :pg, error_message = :em "
                    "WHERE id = :id"
                ),
                {
                    "rp": _json.dumps(request_params) if request_params else None,
                    "pg": _json.dumps(progress) if progress else None,
                    "em": error,
                    "id": row,
                },
            )
        await session.commit()
        return row


@pytest.mark.parametrize(
    "status,started,completed,err",
    [
        ("PENDING", False, False, None),
        ("RUNNING", True, False, None),
        ("COMPLETED", True, True, None),
        ("FAILED", True, True, "boom"),
    ],
)
@pytest.mark.asyncio
async def test_get_job_returns_correct_shape(
    app, client: AsyncClient, status, started, completed, err
):
    await _seed_book(app, book_id=1)
    job_id = await _seed_job(
        app,
        book_id=1,
        status=status,
        started=started,
        completed=completed,
        error=err,
        request_params={"scope": "all"},
        progress={"current": 5, "total": 10, "current_section_title": "X"},
    )

    r = await client.get(f"/api/v1/processing/{job_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_id"] == job_id
    assert body["book_id"] == 1
    assert body["status"] == status.lower()
    assert body["scope"] == "all"
    assert body["progress"]["current"] == 5
    assert body["progress"]["total"] == 10
    assert body["progress"]["current_section_title"] == "X"
    assert "started_at" in body
    if completed:
        assert body["completed_at"] is not None
    else:
        assert body["completed_at"] is None
    if err:
        assert body["error_message"] == err
    assert "request_params" in body


@pytest.mark.asyncio
async def test_get_job_404_for_missing_id(app, client: AsyncClient):
    r = await client.get("/api/v1/processing/9999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_job_handles_null_progress_and_params(app, client: AsyncClient):
    """Null progress / null request_params should still produce a valid 200."""
    await _seed_book(app, book_id=2)
    job_id = await _seed_job(app, book_id=2, status="PENDING")

    r = await client.get(f"/api/v1/processing/{job_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_id"] == job_id
    assert body["status"] == "pending"
    # Either None or empty defaults are acceptable per the spec; assert
    # the keys exist.
    assert "scope" in body
    assert "progress" in body
