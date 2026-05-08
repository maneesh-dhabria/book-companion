"""Integration tests for GET /api/v1/reading-state/resume-banner (FR-B05, §9.1)."""

import pytest


@pytest.mark.asyncio
async def test_resume_banner_empty_db_returns_all_null(client):
    """Empty DB → 200 with all reading + audio fields null. Never 404."""
    resp = await client.get("/api/v1/reading-state/resume-banner")
    assert resp.status_code == 200
    data = resp.json()
    expected_keys = {
        "last_book_id",
        "last_section_id",
        "last_book_title",
        "last_section_title",
        "last_viewed_at",
        "last_audio_content_type",
        "last_audio_content_id",
        "last_audio_book_id",
        "last_audio_book_title",
        "last_audio_section_title",
        "last_audio_at",
        "last_audio_total_sentences",
    }
    assert expected_keys.issubset(data.keys())
    for k in expected_keys:
        assert data[k] is None, f"{k} should be null on empty DB"
