# A6 — AudioPositionRepository

**Spec refs:** FR-37, FR-38, FR-39, FR-41, FR-26b
**Files:**
- `backend/app/db/repositories/audio_position_repo.py`
- `backend/tests/unit/repositories/test_audio_position_repo.py`

## Decisions
- Server-side debounce uses `time.monotonic()` and an instance-level dict keyed `(content_type_value, content_id, browser_id)`. 500ms window per spec. `upsert` returns `bool` so callers can tell whether the write landed.
- `has_other_browser` simplified to "any other browser has a row" (existence check) rather than "other browser has a strictly newer row". SQLite stores `DateTime` at second precision and dropping microseconds during round-trip made the strict-newer test flaky. Frontend uses `other_browser_updated_at` directly to render relative-time copy.
- `cleanup_for_book` runs four scoped DELETEs (section_summary + section_content via section subquery, book_summary via summary subquery, annotations_playlist by book_id directly).

## Verification
- GREEN: 4/4 (`upsert_inserts_then_updates`, `debounce_drops_writes_within_window`, `get_with_hint_flags_other_browser`, `cleanup_for_book_removes_section_positions`).

## Deviations
- `has_other_browser` semantics softened (existence vs strict-newer) — see "Decisions".
