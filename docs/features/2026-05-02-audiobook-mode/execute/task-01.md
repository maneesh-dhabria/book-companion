# A1 — Add TTSConfig to app/config.py

**Spec refs:** FR-42, NFR-11, D7
**Files:** `backend/app/config.py`, `backend/tests/unit/test_config.py`

## Decisions
- Used `Literal["web-speech","kokoro"]` for engine, `Literal["span"]` for annotation_context (per spec).
- `default_speed` bounded `Field(1.0, ge=0.5, le=2.0)`.

## Verification
- RED: `uv run pytest tests/unit/test_config.py -k tts` → `ImportError: cannot import name 'TTSConfig'`.
- GREEN: 4 passed (defaults, env override, invalid engine rejected, speed bounds).

## Deviations
None.
