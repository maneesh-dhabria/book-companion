# A3 — Alembic migration: audio_files + audio_positions + processing_jobs index swap

**Spec refs:** FR-17, §10.1, §10.2, D18
**Files:**
- `backend/app/migrations/versions/2026_05_02_audiobook_mode.py`
- `backend/app/db/models.py` (ProcessingJob index rename)
- `backend/tests/integration/test_audio_migration.py`

## Decisions
- Filename uses date-prefix style (`2026_05_02_audiobook_mode.py`) since the existing chain mixes hash and v-tag formats; revision id is `2026_05_02_audiobook` chained off head `9a67312a27a7`.
- Folded the model `__table_args__` index rename (single-column → `(book_id, step)`) into A3 since model-vs-DB drift would break autogenerate from this point forward.
- `audio_files.content_type` constrained to `('section_summary','book_summary','annotations_playlist')` (no `section_content` — sections aren't summarized into MP3). `audio_positions.content_type` covers all 4 ContentType values for cross-surface resume.
- `audio_positions` PK is `(content_type, content_id, browser_id)` — composite, no surrogate id.

## Verification
- RED: 2 fail (table missing) + 4 errors before migration applied.
- GREEN after impl: 6/6 passed (`uv run pytest tests/integration/test_audio_migration.py`).
- Round-trip downgrade → upgrade verified inside `test_downgrade_round_trip`.
- Full unit suite still green: `582 passed, 5 skipped`.

## Deviations
- Plan test referenced fictional fixtures (`migrated_db`, `seeded_db`, `run_alembic`). Adapted to existing pattern in `tests/integration/test_migration_v1_4.py` — direct `alembic.command.{upgrade,downgrade}` + sync `sa.inspect`/`sa.create_engine`.
- `books` requires `file_data, file_hash, file_size_bytes, file_format` NOT NULL — the in-test seed had to be expanded.
