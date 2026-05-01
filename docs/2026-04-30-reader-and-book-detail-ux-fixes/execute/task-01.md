# B1: Extract is_stale() predicate from orphan_sweep

**Status:** completed
**Spec refs:** FR-04, NFR-03

## Files touched
- `backend/app/services/summarizer/orphan_sweep.py` — added `is_stale()` top-level predicate; refactored `_pid_is_alive` to distinguish ProcessLookupError vs PermissionError vs other OSError.
- `backend/app/config.py` — added `ProcessingConfig` with `stale_job_age_seconds: int = 86400` and wired into `Settings`.
- `backend/tests/unit/test_orphan_sweep_predicate.py` — 5 unit tests including NFR-03 timing.

## Decisions
- Kept legacy `_pid_is_alive` and `_job_is_too_old` private helpers intact (per plan note) so the existing `orphan_sweep()` body stays untouched. They differ slightly from `is_stale()` in error semantics but are not externally imported.

## Runtime evidence
- `pytest tests/unit/test_orphan_sweep_predicate.py` → 5 passed.
- `pytest tests/integration/test_orphan_job_sweep.py` → 4 passed (no regression).
- `python -c "Settings().processing.stale_job_age_seconds"` → `86400`.

## Deviations
None.
