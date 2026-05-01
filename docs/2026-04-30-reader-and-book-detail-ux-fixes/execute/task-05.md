# B5 — Alembic data migration for legacy image:N refs

**Spec refs:** FR-07, NFR-06.

## Files touched
- `backend/app/migrations/versions/e0c48efb7afe_v1_5b_legacy_image_id_rewrite.py` (new)
- `backend/tests/integration/test_migration_image_id_rewrite.py` (new)

## Key decisions
- Mirrors the v1.5a placeholder-rewrite migration shape (`c9d0e1f2a3b4_v1_5a_summary_image_rewrite.py`): scans `summaries` rows where `summary_md LIKE '%](image:%'`, builds a per-book `filename->image_id` map, delegates to `from_image_id_scheme(..., on_missing="strip")`, UPDATEs only when output differs.
- Idempotent by construction: rewritten output uses absolute `/api/v1/images/N` URLs which the legacy regex no longer matches.
- `downgrade()` is a deliberate `pass` — one-shot data fix.

## Runtime evidence
- `pytest tests/integration/test_migration_image_id_rewrite.py -v` → 3 passed (rewrite, idempotent, orphan-strip).
- Fresh DB upgrade against `/tmp/spec-test-b5.db` completed; logged `candidates=0 skipped=0 updated=0`.
- `ruff check` clean on new files.

## Deviations
- Test seed had to use the actual `summaries` columns (`facets_used`, `prompt_text_sent`, `input_char_count`, `summary_char_count`) — the plan snippet referenced `prompt_version`/`detail_level` which don't exist on the current schema.
- Idempotency test uses `downgrade(... 0a1b2c3d4e5f) + upgrade(head)` pair (since the first upgrade already crossed the new revision). This still validates that the second pass produces identical `summary_md`.
