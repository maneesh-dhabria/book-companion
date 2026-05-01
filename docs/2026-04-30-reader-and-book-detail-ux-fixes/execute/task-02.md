# B2: On-demand stale-job sweep in POST /summarize

**Status:** completed
**Spec refs:** FR-01, FR-02, FR-03, NFR-03

## Files touched
- `backend/app/api/routes/processing.py` — wrapped active-job guard in `BEGIN IMMEDIATE`; on stale → FAIL in-place + fall through to INSERT; on live → 409 with structured `active_job` payload.
- `backend/tests/integration/test_api/test_processing_stale_guard.py` — new (2 tests).
- `backend/tests/integration/test_api/test_concurrent_summarize_409.py` — updated to expect new dict-shaped 409 body and rewrote `test_orphan_sweep_unblocks_new_job` since on-demand sweep now subsumes its premise.

## Decisions
- 409 body shape: `{"detail": {"detail": "...", "active_job": {...}}}` (FastAPI's `HTTPException(detail=<dict>)` wraps the dict at top-level `detail`).
- Default success status is 200 (the existing route does not set 202 — kept as-is to avoid scope creep).
- Did not introduce DELETE endpoint (per plan decision P1 — reuse existing POST `/cancel`).

## Runtime evidence
- 19/19 tests green: `test_processing_stale_guard.py` (2), `test_concurrent_summarize_409.py` (4), `test_processing_api.py` (5), `test_processing_cancel.py` (4), `test_orphan_job_sweep.py` (4).
- No frontend consumers of the old detail-string format (grep clean).

## Deviations
- Plan said expected 202 on success; actual route returns 200. Test updated to match reality.
