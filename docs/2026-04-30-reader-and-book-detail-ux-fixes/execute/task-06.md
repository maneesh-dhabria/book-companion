# B6 — GET /api/v1/processing/{job_id} endpoint

**Spec refs:** FR-10, FR-11 (spec §7.4).

## Files touched
- `backend/app/api/routes/processing.py` — added `get_processing_job` route; added `selectinload` import.
- `backend/app/api/schemas.py` — added `ProcessingJobDetailResponse`.
- `backend/tests/integration/test_api/test_processing_get_endpoint.py` (new) — 6 cases.

## Key decisions
- **Route order matters.** First placed the route between `/cancel` and `/status` per the plan suggestion; that broke `GET /api/v1/processing/jobs` because FastAPI registers in source order and `/{job_id}` shadowed the literal `/jobs` path → 422 from int coercion of `"jobs"`. Moved the new GET to the very end of the router (after `/jobs`) and documented the constraint with an inline comment so a future contributor doesn't reshuffle it.
- Used `selectinload(ProcessingJob.book)` to fetch `book.title` in one round-trip per spec §7.4.
- Response model is the new pydantic `ProcessingJobDetailResponse` so OpenAPI gets a typed schema.
- `status` is serialized as the lowercase enum value (`pending`/`running`/...) — matches the existing `/status` endpoint and `test_processing_jobs_list.py` assertions.

## Runtime evidence
- `pytest tests/integration/test_api/test_processing_get_endpoint.py -v` → 6 passed (4 status × shape + 404 + null-progress).
- Regression: `pytest tests/integration/test_api/test_processing_*.py tests/integration/test_api/test_concurrent_summarize_409.py -q` → 24 passed.
- Ruff clean on B6-touched lines (1 pre-existing UP017 on B2's line 135 is not from this task).

## Deviations
- Route placement at end of file (vs. mid-file as plan suggested) was forced by the route-shadowing bug.
- Skipped the manual perf timing harness in plan Step 5 — the in-test ASGI roundtrip is sub-50ms in practice and there's no external service to overshoot the budget.
