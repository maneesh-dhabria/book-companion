---
task_number: 29
task_name: "QuestionTurn + per-shape inputs + LoadingSpinner + CitationChip"
task_goal_hash: 78a56c017f3f003ebbde17e882aa01e7a77e58259026fe4ac11d3fafd6f70663
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T06:05:00Z
completed_at: 2026-05-09T06:18:00Z
files_touched:
  - frontend/src/components/quiz/QuestionTurn.vue
  - frontend/src/components/quiz/McqInput.vue
  - frontend/src/components/quiz/OpenInput.vue
  - frontend/src/components/quiz/SpotErrorInput.vue
  - frontend/src/components/quiz/LoadingSpinner.vue
  - frontend/src/components/quiz/CitationChip.vue
  - frontend/src/components/quiz/__tests__/QuestionTurn.spec.ts
---

## Summary

- **QuestionTurn.vue** — top-level card. Renders the stem, dispatches the per-shape input via `<McqInput>` / `<OpenInput>` / `<SpotErrorInput>`, and a single Submit button gated by FR-48 (per-shape min-input rules) and FR-49 (disable-on-click + 5s fallback re-enable).
- **CitationChip.vue** — pill-style anchor opening the section in a new tab; visibility decided in `QuestionTurn` via the `citationVisible` computed (FR-41: `open` → always; `mcq`/`spot_error` → only after `feedback` is populated).
- **McqInput.vue** — 4 stacked option buttons (`data-test="mcq-option"`); emits `select(idx)`.
- **OpenInput.vue** — autosizing textarea with `v-model`.
- **SpotErrorInput.vue** — `intended_error` callout box + correction textarea (`v-model`).
- **LoadingSpinner.vue** — small ARIA-live spinner taking `:copy` so callers pass `COPY.loadingQuestion` (FR-40 / D16) or `COPY.loadingGrading` (FR-51 / D28).
- **Watcher resets per-question state** on `props.question.id` change so the same component instance can be reused across turns without leaking the prior answer.

## Verification

- `npx vitest run src/components/quiz/__tests__/QuestionTurn.spec.ts` → **14 passed**.
- Full frontend unit suite: `npx vitest run` → **625 passed** (was 611 at Phase 4 close; +14 new).
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| renders MCQ with 4 stacked buttons | shape: mcq |
| renders open-ended autosize textarea | shape: open |
| renders spot-error wrong-restatement callout + correction textarea | shape: spot_error |
| shows citation chip alongside question for open shape (FR-41) | citation visibility |
| hides citation chip until after-answer for mcq (FR-41) | citation visibility |
| hides citation chip until after-answer for spot_error (FR-41) | citation visibility |
| shows citation chip after-answer for mcq when feedback is present | citation visibility post-grade |
| renders LoadingSpinner with verbatim "Reading the book…" | FR-40 / D16 copy |
| Submit disabled until input meets shape rules — open / mcq / spot_error (FR-48) | submit gating × 3 |
| Submit disabled-on-click with 5s fallback re-enable (FR-49) | double-click guard |
| emits submit with shape-specific payload (open / mcq) | output contract for T30 grading |

## Notes

- `CitationChip`'s `href` uses `/books/{bookId}/sections/{section_id}` so the existing reading-state route handles the deep-link. The `:title` attribute on hover surfaces the snippet without expanding the chip; full snippet preview is reserved for the post-feedback citation surface in T30.
- `OpenInput.vue` autosizes via `el.scrollHeight` on every input (covered behaviorally; not unit-asserted because jsdom doesn't lay out heights). The textarea's `resize: vertical` lets users override.
- Submit button payload shape (`{user_answer: string}`) keeps the contract narrow for T30 — the parent will call `store.submitAnswer(...)`, manage the loading state with `LoadingSpinner :copy="COPY.loadingGrading"`, and then re-render this same card with `feedback` populated to surface the citation chip.
- The `submitting` flag is intentionally local — it does NOT call into the store. T30 will lift the long-running guard into the store's submit path so other turn-scoped affordances (Skip/Explain) can also disable themselves while a request is in flight (FR-49 is broader than just Submit).
