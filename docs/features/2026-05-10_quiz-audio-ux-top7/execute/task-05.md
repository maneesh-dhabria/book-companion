---
task_number: 5
task_name: "FR-03 listen_wpm + reading_wpm config"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T00:14:00Z
completed_at: 2026-05-10T00:18:00Z
files_touched:
  - backend/app/config.py
  - backend/app/services/settings_service.py
  - backend/tests/integration/test_api/test_settings_wpm_split.py
---

DEVIATIONS (logged):
1. Plan test sketch uses `{"audio": {"tts": ...}}` namespace, but the live config has `tts:` at the Settings root (no `audio` wrapper). Spec §9.4 likewise contradicts itself (env var calls out `BOOKCOMPANION_AUDIO__TTS__LISTEN_WPM` while the field-add code goes on root `TTSConfig`). Followed the actual config shape: `tts.listen_wpm` and `reading.reading_wpm` at root.
2. `get_safe_settings()` in `settings_service.py` returned a hand-curated subset that excluded `tts`. Extended it to include the full `tts` block + new `reading` block so the GET round-trip required by tests 1, 4, 5 works (spec §9.4: "Response: updated settings tree, including the new keys").
3. Plan tested invalid-range as 422; existing repo convention (per `test_settings_api.py`) maps `pydantic.ValidationError` → 400. Adjusted to 400.

5 new tests pass; total unit suite 729 passed + 5 skipped (baseline was 723 + 5 — added 6 new unit tests across T1–T4 and 5 new integration tests for T5). Ruff clean on all modified files.
