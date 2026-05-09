---
task_number: 27
task_name: "ScopePicker + BudgetBar + ChapterMultiSelect + ThemeInput"
task_goal_hash: f9bd19d0f3c406e575c4e7635c0c0cd44060c0a03622260c15d68c0c5d7a796f
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T05:32:00Z
completed_at: 2026-05-09T05:42:00Z
files_touched:
  - frontend/src/components/quiz/ScopePicker.vue
  - frontend/src/components/quiz/BudgetBar.vue
  - frontend/src/components/quiz/ChapterMultiSelect.vue
  - frontend/src/components/quiz/ThemeInput.vue
  - frontend/src/components/quiz/QuizTab.vue
  - frontend/src/components/quiz/__tests__/ScopePicker.spec.ts
  - frontend/src/api/readingState.ts
  - frontend/src/views/BookOverviewView.vue
---

## Summary

- `ScopePicker.vue` — orchestrator with All-Summaries / Specific-Chapters radio, chapter multi-select, BudgetBar, ThemeInput, and Start button. Manages D31 default-scope precedence (recently-read via T14 → localStorage `quiz.lastScope.book-{id}` → All Summaries). Persists last-used scope on every change so future visits replay.
- `BudgetBar.vue` — presentational. Computes color state: `indigo` <80%, `amber` 80–95%, `red` on overflow attempt. `data-state` attribute exposed for tests.
- `ChapterMultiSelect.vue` — checkbox list. Filters to `chapter | part | section` types. Token count rendered per row. The clamp logic moved to ScopePicker so the user can attempt-and-be-blocked rather than seeing a disabled checkbox they can't reason about.
- `ThemeInput.vue` — textarea with character counter and 200-char cap (FR-15).
- New API: `getReadingStateByBook(bookId)` in `frontend/src/api/readingState.ts` consuming the T14 `most_recent_section_ids` field.

## Verification

- `npm run test:unit -- --run src/components/quiz/__tests__/ScopePicker.spec.ts` → **7 passed**.
- All quiz suites: `src/api/__tests__/quizSessions`, `src/stores/__tests__/quizSessions`, `src/components/quiz/__tests__/QuizTab`, `src/components/quiz/__tests__/ScopePicker` → **32 passed** (zero regressions).
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| defaults to recently-read chapters when within 48h | D31 priority 1 |
| falls back to last-used scope from localStorage when no recent read | D31 priority 2 |
| falls back to All Summaries when no signals | D31 priority 3 |
| lists only chapter/part/section section_types | FR-13 type filter |
| blocks chapter add at >100% budget with verbatim copy | FR-14 |
| Start button disabled with helper text when 0 chapters in specific-chapters mode | FR-12 helper text |
| budget bar turns indigo <80%, amber 80-95%, red on overflow attempt | FR-14 visual |

## Notes

- Budget defaults to `60_000` tokens (matches `QuizConfig.specific_chapters_token_budget` in `backend/app/config.py:119`). Hardcoded in the FE for v1; if the user later customises the budget via settings, expose it via `/api/v1/settings` and thread through.
- ChapterMultiSelect's checkbox is NOT disabled on overflow — the parent ScopePicker handles the rejection and shows verbatim copy. This matches the UX intent: the user sees what would happen, gets blocked, learns the constraint.
- ScopePicker exposes `scopeMode` and `selectedSectionIds` via `defineExpose` for the tests' assertions on internal state. The exposed surface is read-only; mutation goes through the radio/checkbox handlers.
- Token estimate per row falls back to `Math.ceil(content_char_count / 4)` when `content_token_count` is null. The plan mentioned an optional server-side `token_estimate` field in the section list; the existing `SectionBrief.content_token_count` field already serves that purpose.
- DEVIATION (additive): `QuizTab` now accepts a `sections` prop forwarded from `BookOverviewView` so ScopePicker can drive the chapter list without re-fetching. The plan's wording suggested ScopePicker would fetch sections itself; threading via props avoids a redundant network call (BookOverviewView already loaded the book with sections).
