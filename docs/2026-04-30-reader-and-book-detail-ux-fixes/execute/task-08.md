# B8 — Alembic migration for preset typography

**Spec refs:** FR-37, NFR-06.

## Files touched
- `backend/app/migrations/versions/9a67312a27a7_v1_5b_preset_typography.py` (new)
- `backend/tests/integration/test_migration_preset_typography.py` (new)

## Key decisions
- **Schema column names per spec §11.3.** Plan task description named `line_height` and `max_line_chars` but the actual columns (per `a5459240fea0_v1_5_1_collapse_reading_presets.py` and `models.ReadingPreset`) are `line_spacing` and `content_width_px`. Implementation uses the real names and the test seeds + asserts match.
- **Idempotency via WHERE-guard against the original tuple.** Each UPDATE clause includes `WHERE name=? AND font_family='Georgia' AND font_size_px=16 AND line_spacing=1.6 AND content_width_px=720`. After the first run, no row matches → second run is a no-op. Crucially, a user who customized Light to `Inter/14/1.5/720` BEFORE this migration runs is left untouched (verified by `test_migration_preserves_user_customizations`).
- `theme` is also rewritten because the v1.5.1 collapse seeded each preset with its own theme already (e.g., Sepia→sepia), but the spec target tuples include theme for completeness; setting it again is idempotent.
- `downgrade()` is a deliberate `pass` — reverting would silently destroy the new spec values for any user who upgraded but never customized.

## Runtime evidence
- `pytest tests/integration/test_migration_preset_typography.py -v` → 3 passed (spec values, idempotency, user-customization preserved).
- Combined regression on B5-B8 + adjacent tests → 22 passed.
- Fresh DB upgrade against `/tmp/spec-test-b8.db` logs `v1_5b_preset_typography total=6 updated=6` and `sqlite3` confirms all 6 presets match spec §11.3.
- `ruff check` clean on new files.

## Deviations
- Used `line_spacing`/`content_width_px` instead of plan's `line_height`/`max_line_chars` (real schema vs. plan typo). Spec §11.3 table heading also uses `line_spacing` / `content_width_px`, so the schema is the source of truth.
