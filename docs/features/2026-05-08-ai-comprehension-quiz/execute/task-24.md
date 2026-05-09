---
task_number: 24
task_name: "Pinia store with parallel-fetch + optimistic-rollback"
task_goal_hash: 03caf7d84351c8623dca9d83d952663c56067acd59aff42f7520475fbfe309cd
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T05:10:00Z
completed_at: 2026-05-09T05:14:00Z
files_touched:
  - frontend/src/stores/quizSessions.ts
  - frontend/src/stores/__tests__/quizSessions.spec.ts
---

## Summary

`useQuizSessionsStore` (Pinia setup-store) with per-book `Map<number, BookQuizState>` keyed by `bookId`. Parallel-fetch in `loadForBook` via `Promise.all([listSessions, getLifetimeTally])` (G34). Optimistic-update + rollback in `recordSelfAssessment` with toast routing on `ApiError.status === 409` (warn, "Already recorded as X") vs other errors (generic error toast).

## Verification

- `npm run test:unit -- --run src/stores/__tests__/quizSessions.spec.ts` → **7 passed**.
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| issues §9.1 and §9.9 in parallel | parallel-fetch (uses ordering of resolved microtasks) |
| lifetime tally from §9.9 wins over §9.1 mirror | G34 precedence |
| exposes the newest in_progress session as activeSession | resume-banner data source |
| keeps separate state for different bookIds | per-book map isolation |
| rolls back tally on 409 and shows toast with recorded value | G30 + recordedAs extraction |
| rolls back on 5xx with generic error toast | G30 generic error path |
| keeps the optimistic value on success and reconciles from server | success path stays optimistic + merges server state |

## Notes

- Store is a setup-store rather than options-store to match `aiThreads.ts` convention.
- `applySelfAssessmentDelta()` increments `next` and decrements `prev` in the per-session tally so the optimistic UI math matches what the backend rollup will compute when the session ends.
- `extractRecordedAs()` accepts both `{recordedAs: 'got_it'}` and the literal "Already recorded as got_it" string surface from `ApiError.detail` — backend returns the latter today; the former is forward-compatible.
- DEVIATION (additive): added `loadNextQuestion`, `submitAnswer`, `reloadActiveSession`, `clearToast`, `reset`, `stateFor` to the store surface so T26+T28 can drive the state machine without re-implementing them. Plan only itemized `loadForBook` + `recordSelfAssessment`; the additions are scoped to thin wrappers over the API client.
