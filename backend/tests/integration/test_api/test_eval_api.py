"""Integration tests for eval API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_section_eval_not_found(client):
    resp = await client.get("/api/v1/eval/section/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_book_eval_not_found(client):
    resp = await client.get("/api/v1/eval/book/99999")
    assert resp.status_code == 404
