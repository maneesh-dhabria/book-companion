---
task_number: 1
task_name: "T1: firstChapter helper"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T15:38:00Z
completed_at: 2026-05-08T15:41:00Z
files_touched:
  - frontend/src/stores/reader.ts
  - frontend/src/stores/__tests__/firstChapter.spec.ts
---

# T1: firstChapter helper

## Outcome
Added exported `firstChapter(sections, bookStatus)` to `frontend/src/stores/reader.ts`. Returns the first section in `SUMMARIZABLE_TYPES`; if none and `bookStatus === 'PARSED'`, falls back to `sections[0]`; else `null`. Null/undefined inputs return null.

## Verification
- `npm run test:unit -- src/stores/__tests__/firstChapter.spec.ts --run` → 8/8 passed.
- `npm run type-check` → clean.

## Notes
- Test imports `Section` type and casts a minimal stub; existing `Section` interface has more fields than the helper inspects.
- `glossary` is in neither `SUMMARIZABLE_TYPES` nor `FRONT_MATTER_TYPES`; for a `[copyright, glossary]` PARSED book, the helper falls back to `sections[0]` (copyright). This matches the spec — front-matter fallback is acceptable last resort once parsing is complete.
