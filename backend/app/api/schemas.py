"""Pydantic v2 request/response models for all API endpoints."""

from __future__ import annotations

import enum
from datetime import datetime  # noqa: TC003
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


# --- Generic ---


class ErrorResponse(BaseModel):
    detail: str
    code: str


class PaginatedResponse(BaseModel, Generic[T]):  # noqa: UP046
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int


# --- Authors ---


class AuthorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str = "author"


# --- Books ---


class BookListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    file_format: str
    file_size_bytes: int
    authors: list[AuthorResponse] = []
    section_count: int = 0
    cover_url: str | None = None
    has_summary: bool = False
    eval_passed: int | None = None
    eval_total: int | None = None
    created_at: datetime
    updated_at: datetime


class SectionBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order_index: int
    section_type: str
    content_token_count: int | None = None
    has_summary: bool = False


class SummaryBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    preset_name: str | None = None
    model_used: str
    summary_char_count: int
    created_at: datetime
    summary_md: str | None = None


class BookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    file_format: str
    file_size_bytes: int
    file_hash: str
    authors: list[AuthorResponse] = []
    sections: list[SectionBriefResponse] = []
    section_count: int = 0
    cover_url: str | None = None
    created_at: datetime
    updated_at: datetime
    summary_progress: dict[str, int] | None = None
    # T15 / T16 — book-level summary state for BookSummaryView.
    default_summary: SummaryBriefResponse | None = None
    last_used_preset: str | None = None
    # v1.5 — AI-suggested tags + book-level failure diagnostics.
    suggested_tags: list[str] = []
    last_summary_failure: dict | None = None


class BookUpdateRequest(BaseModel):
    title: str | None = None


class DuplicateCheckRequest(BaseModel):
    file_hash: str


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    existing_book_id: int | None = None


# --- Sections ---


class SectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    title: str
    order_index: int
    section_type: str
    content_token_count: int | None = None
    content_md: str | None = None
    default_summary: SummaryBriefResponse | None = None
    summary_count: int = 0
    annotation_count: int = 0
    has_summary: bool = False
    is_summarizable: bool = True


class SectionMergeRequest(BaseModel):
    section_ids: list[int]
    title: str


class SectionSplitRequest(BaseModel):
    mode: str = "heading"
    positions: list[int] | None = None


class SectionReorderRequest(BaseModel):
    section_ids: list[int]


# --- Summaries ---


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_type: str
    content_id: int
    book_id: int
    preset_name: str | None = None
    facets_used: dict[str, Any] = {}
    model_used: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    input_char_count: int
    summary_char_count: int
    summary_md: str
    eval_json: dict[str, Any] | None = None
    quality_warnings: dict[str, Any] | None = None
    latency_ms: int | None = None
    created_at: datetime


class SummaryCompareResponse(BaseModel):
    summary_a: SummaryResponse
    summary_b: SummaryResponse
    concept_diff: dict[str, Any] | None = None


# --- Processing ---


class ProcessingStartRequest(BaseModel):
    preset_name: str = "practitioner_bullets"
    run_eval: bool = True
    auto_retry: bool = True
    skip_eval: bool = False
    scope: Literal["all", "pending", "section", "failed"] = "all"
    section_id: int | None = None
    force: bool = False


class ProcessingStartResponse(BaseModel):
    job_id: int


class ProcessingStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: int
    book_id: int
    step: str
    status: str
    progress: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProcessingCancelResponse(BaseModel):
    job_id: int
    status: str
    message: str


class ProcessingJobDetailResponse(BaseModel):
    """Spec §7.4 — full job state for the JobProgressView deep-link."""

    model_config = ConfigDict(from_attributes=True)

    job_id: int
    book_id: int
    book_title: str | None = None
    status: str
    scope: str | None = None
    section_id: int | None = None
    progress: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_event_at: datetime | None = None
    error_message: str | None = None
    request_params: dict[str, Any] | None = None


# --- Eval ---


class AssertionResultResponse(BaseModel):
    name: str
    category: str
    passed: bool
    reasoning: str | None = None
    likely_cause: str | None = None
    suggestion: str | None = None


class EvalResultResponse(BaseModel):
    section_id: int | None = None
    summary_id: int | None = None
    passed: int
    total: int
    eval_run_id: str | None = None
    assertions: list[AssertionResultResponse] = []


class BookEvalResponse(BaseModel):
    book_id: int
    total_sections: int
    evaluated_sections: int
    overall_passed: int
    overall_total: int
    sections: list[EvalResultResponse] = []


# --- Library Views ---


class LibraryViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_mode: str
    sort_field: str
    sort_direction: str
    filters: dict[str, Any] | None = None
    table_columns: dict[str, Any] | None = None
    position: int
    is_default: bool
    created_at: datetime
    updated_at: datetime


class LibraryViewCreateRequest(BaseModel):
    name: str
    display_mode: str = "grid"
    sort_field: str = "updated_at"
    sort_direction: str = "desc"
    filters: dict[str, Any] | None = None
    table_columns: dict[str, Any] | None = None


class LibraryViewUpdateRequest(BaseModel):
    name: str | None = None
    display_mode: str | None = None
    sort_field: str | None = None
    sort_direction: str | None = None
    filters: dict[str, Any] | None = None
    table_columns: dict[str, Any] | None = None


# --- Annotations ---


class AnnotationTypeEnum(enum.StrEnum):
    HIGHLIGHT = "highlight"
    NOTE = "note"
    FREEFORM = "freeform"


class AnnotationCreateRequest(BaseModel):
    content_type: str
    content_id: int
    type: AnnotationTypeEnum = AnnotationTypeEnum.HIGHLIGHT
    selected_text: str | None = None
    text_start: int | None = None
    text_end: int | None = None
    note: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    tags: list[str] | None = None


class AnnotationUpdateRequest(BaseModel):
    note: str | None = None
    type: AnnotationTypeEnum | None = None


class AnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_type: str
    content_id: int
    text_start: int | None = None
    text_end: int | None = None
    selected_text: str | None = None
    note: str | None = None
    type: str
    linked_annotation_id: int | None = None
    prefix: str | None = None
    suffix: str | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    # T18 — joined book + section context for /annotations UI. Null when the
    # annotation targets a deleted section or a non-section content type.
    book_id: int | None = None
    book_title: str | None = None
    section_id: int | None = None
    section_title: str | None = None


class AnnotationLinkRequest(BaseModel):
    target_annotation_id: int


AnnotationExportFormat = Literal["markdown", "json", "csv"]


# --- Search ---


class SearchHitBase(BaseModel):
    id: int
    book_id: int
    book_title: str
    snippet: str
    score: float


class BookSearchHit(SearchHitBase):
    title: str


class SectionSearchHit(SearchHitBase):
    title: str
    section_title: str | None = None


class ConceptSearchHit(SearchHitBase):
    term: str


class AnnotationSearchHit(SearchHitBase):
    note_snippet: str | None = None
    selected_text: str | None = None


class QuickSearchResults(BaseModel):
    books: list[BookSearchHit] = []
    sections: list[SectionSearchHit] = []
    concepts: list[ConceptSearchHit] = []
    annotations: list[AnnotationSearchHit] = []


class QuickSearchResponse(BaseModel):
    query: str
    results: QuickSearchResults


class SearchResultItem(BaseModel):
    source_type: str
    source_id: int
    book_id: int
    book_title: str
    section_title: str | None = None
    snippet: str
    score: float
    highlight: str


class FullSearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
    page: int
    per_page: int


class RecentSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    query: str
    result_count: int | None = None
    created_at: datetime


# --- Concepts ---


class ConceptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    term: str
    definition: str
    user_edited: bool = False
    created_at: datetime
    updated_at: datetime


class ConceptDetailResponse(ConceptResponse):
    section_appearances: list[SectionBriefResponse] = []
    related_concepts: list[ConceptResponse] = []
    book_title: str = ""


class ConceptUpdateRequest(BaseModel):
    term: str | None = None
    definition: str | None = None


# --- Reading Presets ---


class ReadingPresetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    font_family: str
    font_size_px: int
    line_spacing: float
    content_width_px: int
    theme: str
    created_at: datetime


class ReadingPresetListResponse(BaseModel):
    items: list[ReadingPresetResponse]


# --- AI Threads ---


class AIThreadCreateRequest(BaseModel):
    title: str = "New Thread"


class AIThreadUpdateRequest(BaseModel):
    title: str


class AIMessageCreateRequest(BaseModel):
    content: str
    context_section_id: int | None = None
    selected_text: str | None = None


class AIMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    role: str
    content: str
    created_at: datetime


class AIThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    title: str
    messages: list[AIMessageResponse] = []
    created_at: datetime
    updated_at: datetime


class AIThreadListItem(BaseModel):
    id: int
    book_id: int
    title: str
    message_count: int = 0
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Export / Backup / Settings / Reading State ────────────────────────


class ExportQueryParams(BaseModel):
    format: str = "json"
    include_summaries: bool = True
    include_annotations: bool = True
    include_concepts: bool = True
    include_eval: bool = False


class BackupResponse(BaseModel):
    backup_id: str
    filename: str
    size_bytes: int
    created_at: str | None = None


class BackupListItem(BaseModel):
    backup_id: str
    filename: str
    size_bytes: int
    size_mb: float
    created_at: str | None = None


class BackupScheduleRequest(BaseModel):
    enabled: bool
    interval_hours: int = 24


class ReadingStateUpsert(BaseModel):
    book_id: int
    section_id: int | None = None
    scroll_position: float | None = None
    content_mode: str = "summary"


class ReadingStateResponse(BaseModel):
    last_book_id: int | None = None
    last_section_id: int | None = None
    last_viewed_at: str | None = None
    book_title: str | None = None
    section_title: str | None = None
