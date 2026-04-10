"""Tests for API Pydantic schemas."""

from datetime import datetime

from app.api.schemas import (
    BookResponse,
    ErrorResponse,
    LibraryViewCreateRequest,
    PaginatedResponse,
    ProcessingStartRequest,
    SectionResponse,
    SummaryResponse,
)


def test_book_response_schema():
    data = BookResponse(
        id=1,
        title="Test Book",
        status="parsed",
        file_format="epub",
        file_size_bytes=4200000,
        file_hash="sha256:abc",
        authors=[{"id": 1, "name": "Author", "role": "author"}],
        sections=[],
        section_count=0,
        cover_url=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert data.id == 1
    assert data.title == "Test Book"


def test_paginated_response():
    data = PaginatedResponse(items=[], total=0, page=1, per_page=20, pages=0)
    assert data.pages == 0
    assert data.items == []


def test_error_response():
    err = ErrorResponse(detail="Not found", code="NOT_FOUND")
    assert err.code == "NOT_FOUND"


def test_processing_start_request():
    req = ProcessingStartRequest(preset_name="balanced", run_eval=True, auto_retry=True)
    assert req.run_eval is True
    assert req.preset_name == "balanced"


def test_section_response_has_summary_fields():
    s = SectionResponse(
        id=1,
        book_id=1,
        title="Ch 1",
        order_index=0,
        section_type="chapter",
        content_token_count=100,
        content_md="# Ch 1",
        default_summary=None,
        summary_count=0,
        annotation_count=0,
        has_summary=False,
    )
    assert s.has_summary is False
    assert s.default_summary is None


def test_summary_response():
    s = SummaryResponse(
        id=1,
        content_type="section",
        content_id=1,
        book_id=1,
        preset_name="balanced",
        facets_used={},
        model_used="sonnet",
        input_char_count=1000,
        summary_char_count=200,
        summary_md="# Summary",
        created_at=datetime.now(),
    )
    assert s.summary_md == "# Summary"


def test_library_view_create_request():
    req = LibraryViewCreateRequest(
        name="Test View",
        display_mode="list",
        sort_field="title",
        sort_direction="asc",
        filters={"status": ["completed"]},
    )
    assert req.name == "Test View"
    assert req.display_mode == "list"
