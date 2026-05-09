---
task_number: 30
task_name: "FeedbackPanel + SelfAssessmentButtons + OverrideAffordance + FatiguePromptBanner"
task_goal_hash: 5a8a3ea3e19c3f6232da778a736c7e1c36ad374832c5eefe783c0cf876623489
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T06:20:00Z
completed_at: 2026-05-09T06:32:00Z
files_touched:
  - frontend/src/components/quiz/FeedbackPanel.vue
  - frontend/src/components/quiz/SelfAssessmentButtons.vue
  - frontend/src/components/quiz/OverrideAffordance.vue
  - frontend/src/components/quiz/FatiguePromptBanner.vue
  - frontend/src/components/quiz/__tests__/FeedbackAndAssessment.spec.ts
---

## Summary

- **FeedbackPanel.vue** — three labeled fields (correct / missing / actual) with color-coded labels (green/amber/indigo). Hidden when `feedback` is null so the parent can mount it unconditionally.
- **SelfAssessmentButtons.vue** — three left-to-right buttons (Got it / Partial / Missed); `disabled` prop locks the row while a request is in flight; click handler calls `store.recordSelfAssessment(bookId, sa)`. `isFirstSession` prop drives the FR-50/§11 microcopy `"Your click is the source of truth for the tally."`.
- **OverrideAffordance.vue** — collapsed link → expanded textarea with `MAX = 500`-char clamp (E23). The clamp runs on `@input` and writes back to the textarea so paste-of-600-chars also clamps. Counter `data-test="override-counter"` shows `N / 500`. Save calls `overrideQuestion(sessionId, questionId, note)`; emits `saved`. Per FR-54/E13 it does NOT touch `recordSelfAssessment`.
- **FatiguePromptBanner.vue** — pure detector. Renders only when `feedback.actual` contains the verbatim clause `COPY.fatigueClause` ("Want to keep going or wrap up here?"). Hidden otherwise (FR-55).

## Verification

- `npx vitest run src/components/quiz/__tests__/FeedbackAndAssessment.spec.ts` → **13 passed**.
- Full unit suite → **638 passed** (was 625 after T29; +13).
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| FeedbackPanel renders 3 distinct fields | FR-50 contract |
| FeedbackPanel hides when feedback null | gating |
| SelfAssessmentButtons calls store.recordSelfAssessment on click | FR-53 wiring |
| renders microcopy on first session | §11 first-session copy |
| hides microcopy after first session | §11 |
| three buttons in order Got it / Partial / Missed | order |
| disables all when disabled prop | submit-in-flight gate |
| Override clamps at 500 chars (E23) | length cap |
| Override exposes character counter | UX hint |
| Override saved does NOT call recordSelfAssessment (FR-54 / E13) | tally invariance |
| FatigueBanner appears when clause present | FR-55 |
| FatigueBanner hidden when clause absent | FR-55 |
| FatigueBanner hidden when feedback null | FR-55 |

## Notes

- The mock for `@/api/quizSessions` uses `vi.mock` at module top so any import path that touches it (the store via `recordSelfAssessment`, the OverrideAffordance via `overrideQuestion`) gets the same fake. Spec-friendly: each suite calls `setActivePinia(createPinia())` in `beforeEach` so the store is fresh per-test.
- `OverrideAffordance` is wired directly to `overrideQuestion(...)` rather than going through the store because override never affects tally state — there is nothing to optimistically update. The store will surface the persisted note when `reloadActiveSession` runs after save (parent's responsibility, not this component's).
- The textarea `setValue` reflection: jsdom's `setValue` writes the raw string into `.value` first, then we read it in the `@input` handler and clamp + write back. The test's `expect(...value.length).toBeLessThanOrEqual(500)` proves the round-trip.
- T31's per-turn controls (Skip / Explain / AlreadyAsked) will live alongside these in the eventual question-card layout — they are factored separately because their wiring touches different store actions and FR families.
