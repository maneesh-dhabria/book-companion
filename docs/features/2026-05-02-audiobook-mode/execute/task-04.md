# A4 — AudioFile + AudioPosition ORM models

**Spec refs:** §10.1, FR-22
**Files:**
- `backend/app/db/models.py` (append)
- `backend/tests/integration/test_audio_models.py`

## Decisions
- Stored `content_type` as `String(64)` rather than `Enum(ContentType)` — the migration's CHECK constraint enforces the union, and consumers handle the Python enum at boundary code (matches the Annotation model's approach to `content_type`).
- AudioPosition has no surrogate id; composite PK is `(content_type, content_id, browser_id)` per spec §10.1.
- `audio_positions.updated_at` uses `onupdate=func.now()` so server-side debounced UPSERT path can rely on the column.

## Verification
- RED: `ImportError: cannot import name 'AudioFile'`.
- GREEN: 2 passed (`test_audio_file_persist_round_trip`, `test_audio_position_pk_composite`).

## Deviations
- Tests live in `tests/integration/test_audio_models.py` (async session needed) instead of `tests/unit/test_models.py` (sync) per the existing pattern.
