---
task_number: 4
task_name: "T4: /reading-state/resume-banner"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T15:48:00Z
completed_at: 2026-05-08T15:50:00Z
files_touched:
  - backend/app/api/schemas.py
  - backend/app/api/routes/reading_state.py
  - backend/app/db/repositories/reading_state_repo.py
  - backend/app/db/repositories/audio_position_repo.py
  - backend/tests/unit/repositories/test_reading_state_repo.py
  - backend/tests/unit/repositories/test_audio_position_resume_banner.py
  - backend/tests/integration/test_api/test_resume_banner_api.py
---

# T4: /reading-state/resume-banner (FR-B05, D21, §9.1)

## Outcome
- New `ResumeBannerResponse` Pydantic schema with all 11 spec fields plus plan extension `last_audio_total_sentences`.
- New `ReadingStateRepository.get_latest_resume_banner_reading()` — most-recent reading_state across all browsers, FRONT_MATTER filtered.
- New `AudioPositionRepository.get_latest_resume_banner()` — most-recent audio_position excluding `annotations_playlist`, joining `book_sections`/`books` to populate book_id + titles, joining `audio_files` for `total_sentences`.
- New route `GET /api/v1/reading-state/resume-banner` composing both. 200 with all-null fields when nothing seeded; never 404.

## Verification
- `pytest tests/unit/repositories/test_reading_state_repo.py tests/unit/repositories/test_audio_position_resume_banner.py -v` → 11/11 pass.
- `pytest tests/integration/test_api/test_resume_banner_api.py -v` → 1/1 pass.
- `pytest tests/unit/repositories/ tests/integration/test_api/test_reading_state_api.py` → 22 pass, 3 skip (no regressions).
- `ruff check` clean on changed files (one pre-existing TC002 on AsyncSession was already present on main).

## Notes / Deviation
- Plan's "audio_files row with status='ready'" — `AudioFile` model has no `status` column; row presence implies the file is generated. No filter on status is needed.
- The `annotations_playlist` exclusion is enforced at SQL level via `content_type.in_(...)` allow-list, matching spec §9.1 bullet 3.
- `ResumeBannerAudio` dataclass returned by the audio repo decouples query results from ORM relationships (avoids lazy-load issues) and lets the route compose flat fields.
