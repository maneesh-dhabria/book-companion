---
task_number: 31
task_name: "SkipButton + ExplainAffordance + AlreadyAskedLink"
task_goal_hash: cca9c27287f118ba20958cbdd089914af75ac02be4a60eab55aee7ae4b70975b
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T06:34:00Z
completed_at: 2026-05-09T06:46:00Z
files_touched:
  - frontend/src/components/quiz/SkipButton.vue
  - frontend/src/components/quiz/ExplainAffordance.vue
  - frontend/src/components/quiz/AlreadyAskedLink.vue
  - frontend/src/components/quiz/constants.ts
  - frontend/src/components/quiz/__tests__/QControls.spec.ts
---

## Summary

- **constants.ts** — new module mirroring backend `QuizConfig` defaults (explain soft cap, override max chars, token budget, fallback re-enable ms). Centralises magic numbers used across the quiz tree; future settings-route work can replace these with reactive values.
- **SkipButton.vue** — single button with `busy` ref; disables on click, calls `skipQuestion(sessionId, questionId)`, emits `skipped` (or `error`).
- **ExplainAffordance.vue** — stacks `question.explain_history` above the button (FR-46a) with each entry prefixed `Clarification:`. When `history.length >= QUIZ_EXPLAIN_SOFT_CAP` (=2), the button is replaced with `COPY.explainSoftCap` ("Try answering or Skip"). Click calls `explainQuestion(...)` and emits `explained`.
- **AlreadyAskedLink.vue** — link with first-time tooltip. The `quiz.alreadyAsked.tooltipSeen` sessionStorage flag silences the tooltip after the first hover-or-click. Click calls `discardQuestion(...)`, emits `discarded` with the `{question, replacement}` response.

## Verification

- `npx vitest run src/components/quiz/__tests__/QControls.spec.ts` → **9 passed**.
- Full unit suite → **647 passed** (was 638 after T30; +9).
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| Skip disables on click and re-enables after response (FR-49) | per-button guard |
| Skip emits skipped on success | output contract |
| Explain stacks all explanations (FR-46a) | history rendering |
| Explain prefixes each entry with "Clarification:" | FR-46a copy |
| Explain replaces button with "Try answering or Skip" after 2 hits (FR-46) | soft cap |
| Explain calls explainQuestion on click and emits explained | wiring |
| AlreadyAsked tooltip on first hover only | first-time UX |
| AlreadyAsked tooltip suppressed when sessionStorage flag set | persistence |
| AlreadyAsked click calls discardQuestion + emits replacement | wiring (FR-47) |

## Notes

- The "first session" tooltip uses `sessionStorage` (per-tab) rather than `localStorage` (cross-tab persistent). The user gets the hint once per session, which matches the spec's intent of a teaching moment without being noisy across reopens.
- `SkipButton` does NOT prompt for self-assessment — FR-43 explicitly says skips skip self-assessment. The parent (T28's ActiveSession, expanded in T33) handles `next_question` after `@skipped`.
- `ExplainAffordance` does not modify the in-store question — the parent should call `store.reloadActiveSession(bookId)` (or update locally) on `@explained` to refresh `explain_history`. Keeping this component pure simplifies testing.
- `AlreadyAskedLink` returns the `{question, replacement}` shape directly; the parent updates the store's `currentQuestion` to the replacement. The discarded row stays in past Q&A for T32's PastQAPanel.
