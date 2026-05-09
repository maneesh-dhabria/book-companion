---
task_number: 26
task_name: "QuizTab.vue root + state machine + copy.ts"
task_goal_hash: b736a957bd1f436be5e521fddd5838f6ba49c654c7b34a18344ddf87dfd8b46b
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T05:20:00Z
completed_at: 2026-05-09T05:30:00Z
files_touched:
  - frontend/src/components/quiz/QuizTab.vue
  - frontend/src/components/quiz/copy.ts
  - frontend/src/components/quiz/ScopePicker.vue
  - frontend/src/components/quiz/ResumeBanner.vue
  - frontend/src/components/quiz/ActiveSession.vue
  - frontend/src/components/quiz/PastQAPanel.vue
  - frontend/src/components/quiz/__tests__/QuizTab.spec.ts
  - frontend/src/views/BookOverviewView.vue
  - frontend/src/stores/quizSessions.ts
---

## Summary

`QuizTab.vue` now drives a 6-state machine via a single `mode` computed:
- `loading` — LLM status fetch + `loadForBook` in flight (rendered via `v-else` fallback to ScopePicker stub)
- `no-llm` — `preflight.ok === false` → renders verbatim `COPY.noLLMBanner`
- `no-summaries` — `hasSummaries` prop is false → renders verbatim `COPY.noSummariesGate`
- `resume` — `activeSession` exists but no `currentQuestion` → renders `<ResumeBanner>`
- `active` — `activeSession` + `currentQuestion` → renders `<ActiveSession>`
- `ready` (default `v-else`) — renders `<ScopePicker>` and, when prior history exists, `<PastQAPanel>` alongside

`copy.ts` carries 14 verbatim strings (NFR-08), including warm-up/loading copy used by Phase 5.

Stub components (`ScopePicker`, `ResumeBanner`, `ActiveSession`, `PastQAPanel`) ship with the right `data-test` attributes so T27 / T28 / T32 can grow them in place without changing wiring.

`hasSummaries` is passed in from `BookOverviewView` (it already computes `hasNoSummaries`) so QuizTab doesn't duplicate the summary-existence query.

## Verification

- `npm run test:unit -- --run src/components/quiz/__tests__/QuizTab.spec.ts` → **5 passed**.
- `npm run test:unit -- --run src/stores/__tests__/quizSessions.spec.ts` → 7 passed (regression).
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|---|---|
| renders no-LLM banner when preflight.ok is false | E1 |
| renders no-summaries gate when hasSummaries is false | E2 |
| renders scope picker (ready mode) when ready and no active session | scope-picker entry |
| renders resume banner when an in_progress session exists for this book | FR-19 entry |
| renders past-Q&A panel alongside scope-picker when prior history exists | history visibility |

## Notes

- DEVIATION (Pinia reactivity): the store originally used `ref<Map<...>>` for `byBook`. Vue 3's `ref()` does NOT proxy Map collection ops the same way `reactive()` does, so `Map.get()` reads were not tracking with the deep mutations done by `loadForBook`. Switched to `byBook = reactive(new Map())` and `state = reactive(emptyState())` — `loaded` was reactive (triggered the recompute that flipped `mode` from `loading` to `ready`) but `sessions` mutations were silently dropping their dep entry on the inner array, so the `pastSessions` computed never re-evaluated. The reactive-Map fix preserves identity (no need to clone-and-reassign on every mutation) and tracks all property writes the consumers care about.
- DEVIATION: kept the state machine to 5 active modes (`no-llm`, `no-summaries`, `resume`, `active`, `ready`) plus a `loading` placeholder; the plan listed 6 (`past-only` separately). Past-only behavior is satisfied by rendering `<PastQAPanel>` alongside the ScopePicker in `ready` mode rather than as a distinct branch — the wireframes show this layout, and a separate "past-only" mode would only repeat the same panel.
- T26's `onResume` / `onStopAndStart` are intentionally minimal; T28 wires the full FR-19 resume flow and T16's atomic stop_session. The current handlers cover the test `data-test="resume-banner"` rendering check.
