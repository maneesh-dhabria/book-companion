---
task_number: 28
task_name: "ResumeBanner + ActiveSession scaffold + WarmUpBanner"
task_goal_hash: 2a2164456b1c63ff90bff435a96fe39833cca8eaac083ea68ce49504c0e58827
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T05:43:00Z
completed_at: 2026-05-09T05:48:00Z
files_touched:
  - frontend/src/components/quiz/ResumeBanner.vue
  - frontend/src/components/quiz/ActiveSession.vue
  - frontend/src/components/quiz/WarmUpBanner.vue
  - frontend/src/components/quiz/__tests__/ResumeBanner.spec.ts
  - frontend/src/components/quiz/__tests__/WarmUpBanner.spec.ts
---

## Summary

- **ResumeBanner**: T26 already shipped a stub matching the spec; T28 added explicit tests. Renders `COPY.resumeBanner` + Resume + Stop & start buttons; emits `resume` and `stop`.
- **ActiveSession**: shell wraps `<WarmUpBanner>` (when `is_warm_up_session`), placeholder for the upcoming `<QuestionTurn>` (T29), and a placeholder Stop button (T33 wires the proper end-of-session pivot). Reads `currentQuestion`/`activeSession` from the Pinia store.
- **WarmUpBanner**: enumerates Missed and Partial concept labels in two paragraph lines; renders `null` when both arrays are empty (FR-74). Includes a `formatList` helper that emits "a, b, and c" with the serial comma.

## Verification

- `npm run test:unit -- --run src/components/quiz/__tests__/ResumeBanner.spec.ts src/components/quiz/__tests__/WarmUpBanner.spec.ts` → **6 passed**.
- All quiz component tests (QuizTab, ScopePicker, ResumeBanner, WarmUpBanner) → 18 passed.
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| renders verbatim "You have a session in progress —" | FR-19 copy |
| emits resume event on Resume click | FR-19 button wiring |
| emits stop event on Stop & start a new one click | FR-19 button wiring |
| enumerates the actual concept labels in the banner copy | FR-72 |
| renders nothing when both arrays empty | FR-74 |
| formats a list of three with serial comma | formatList helper |

## Notes

- ActiveSession surfaces `is_warm_up_session` from the active session as the warm-up trigger. The actual missed/partial concept arrays will be wired in Phase 5 (T32) when `loadForBook` aggregates prior-session concept_labels — for now the arrays are empty so the banner stays hidden.
- The Stop button in ActiveSession is intentionally minimal — T33 (Phase 5) will replace it with the proper SessionEndActions component that calls `stopSession` and offers the export modal.
- ResumeBanner's tests for verbatim copy and emitted events satisfy the plan's wireframe-derived assertions without re-rendering the parent QuizTab.
