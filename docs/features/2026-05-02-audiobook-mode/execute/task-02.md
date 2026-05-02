# A2 — Extend ContentType + ProcessingStep enums

**Spec refs:** D22, FR-16, FR-52
**Files:** `backend/app/db/models.py`, `backend/tests/unit/test_models.py`

## Verification
- RED: `AttributeError: type object 'ContentType' has no attribute 'ANNOTATIONS_PLAYLIST'`.
- GREEN: 2 passed.

## Notes
- `ProcessingStep.AUDIO` = `"audio"`; `ContentType.ANNOTATIONS_PLAYLIST` = `"annotations_playlist"`.
- SQLite stores enum as TEXT; CHECK constraint is reapplied via the upcoming migration in A14.
