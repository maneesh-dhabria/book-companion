# B3: from_image_id_scheme() helper

**Status:** completed
**Spec refs:** FR-05, FR-09

## Files
- `backend/app/services/parser/image_url_rewrite.py` — added `_LEGACY_IMAGE_RE` + `from_image_id_scheme()`.
- `backend/tests/unit/test_image_url_rewrite_id_scheme.py` — 7 unit tests.

## Runtime evidence
- 7/7 tests green.

## Deviations
- Default `on_missing="strip"` per plan §B3 (matches the call-site pattern in summarizer_service for B4).
