---
phase: 4
phase_name: "Frontend Core (types / api / store / tab integration / scope picker / resume)"
tasks: [T22, T23, T24, T25, T26, T27, T28]
verify_status: passed
verified_at: 2026-05-09T05:55:00Z
verify_evidence: docs/features/2026-05-08-ai-comprehension-quiz/verify/2026-05-09-phase-4/
---

## Phase 4 boundary verify — green

- **`npm run type-check`**: 0 errors.
- **`npm run test:unit -- --run`**: **611 passed**, 108 test files (up from 571 / 102 at Phase 3 close — 40 new tests across T23–T28).
- **`npm run build`**: clean (the lone warning is a pre-existing `router/index.ts` static-vs-dynamic import note, unchanged from main).
- **`npm run lint`**: skipped — pre-existing tooling failure on the eslint global vs `@typescript-eslint/no-unused-expressions` plugin version mismatch (`TypeError: Cannot read properties of undefined (reading 'allowShortCircuit')`). Reproduces on `main` worktree, so out of scope for Phase 4.
- **Live smoke** (worktree backend on :8765 with a fresh `/tmp/bc-quiz-smoke` data dir):
  - `GET /api/v1/health` → `{"status":"ok","llm_provider":"claude","llm_available":true,...}`
  - `GET /` (SPA index) → 200, includes `<title>Book Companion`
  - `GET /books/1?tab=quiz` → 200 (SPA history fallback)
  - `GET /api/v1/books/1/quiz-sessions` → 404 (correct: bookId=1 doesn't exist in fresh DB; T15's `_book_or_404` fires)
  - `GET /api/v1/books/1/quiz-sessions/lifetime-tally` → 404 (same)
  - `BookOverviewView-*.js` chunk contains the `quiz-tab-root` + `no-llm-banner` + `scope-picker` test ids → all quiz components landed in the production bundle

## Commits this phase

- `feat(T22): add quiz frontend types`
- `feat(T23): typed REST client for 12 quiz routes`
- `feat(T24): Pinia store with parallel-fetch + optimistic-rollback`
- `feat(T25): add Quiz tab to BookOverviewView`
- `feat(T26): QuizTab root + state machine + copy.ts`
- `feat(T27): ScopePicker + BudgetBar + ChapterMultiSelect + ThemeInput`
- `feat(T28): ResumeBanner + ActiveSession scaffold + WarmUpBanner`

## Hand-off notes for Phase 5 (Frontend Question Turn UX + Tally + Past Q&A + Export + Final)

- **Pinia store reactivity (carry-forward)**: `useQuizSessionsStore.byBook` is `reactive(new Map())`, with each per-book state wrapped in `reactive(emptyState())`. T26's debugging caught a silent reactivity bug when this was `ref<Map<...>>` — the Map's collection ops weren't proxied so deep mutations to `state.sessions` didn't invalidate computeds. Phase 5 components should access store state via the store getter directly (`store.byBook.get(bookId)?.…`); avoid re-introducing the ref-Map pattern.
- **State machine modes**: QuizTab's `mode` computed has 5 active branches (`no-llm`, `no-summaries`, `resume`, `active`, `ready`) plus a `loading` placeholder rendered via `v-else`. The plan listed 6 (separate `past-only`); past-only is satisfied by rendering `<PastQAPanel>` alongside the ScopePicker in `ready` mode (T26 deviation, documented in `task-26.md`). Phase 5 (T32) replaces the PastQAPanel stub with the real implementation.
- **`hasSummaries` flow**: BookOverviewView passes `hasSummaries` and `sections` to QuizTab; ScopePicker reads sections directly. No re-fetch in the quiz tree — T29+ should follow the same pattern (lift loads to BookOverviewView, push refs down).
- **D31 default scope**: ScopePicker calls `getReadingStateByBook(bookId)` → uses `most_recent_section_ids` (T14 endpoint). Falls back to `localStorage.getItem('quiz.lastScope.book-{id}')` then to `'all_summaries'`. The localStorage key shape is documented in T27's `task-27.md`.
- **Active-session shell**: ActiveSession.vue's structure is `WarmUpBanner` → placeholder QuestionTurn → placeholder SessionEndActions. T29 fills QuestionTurn (per-shape inputs, citation chip, loading spinner), T33 fills SessionEndActions.
- **Stop button placement**: Live in two places — ResumeBanner emits `stop` (T26 already wired through `onStopAndStart`), and ActiveSession has its own minimal Stop button (T28 placeholder). Phase 5's SessionEndActions will be the canonical single source.
- **Outcome events** (carry-forward from Phase 3): all LLM-bound routes emit `quiz.<step>.outcome` structlog events; the FE store routes 409 via the toast surface. Operators can grep with `jq 'select(.event | startswith("quiz."))'`.
- **Budget constant**: hardcoded to `60_000` in ScopePicker (matches `QuizConfig.specific_chapters_token_budget`). If the user customises this via settings, expose via `/api/v1/settings` and thread through.
- **ESLint tooling debt**: pre-existing `eslint`/`@typescript-eslint/eslint-plugin` version mismatch — surfaces on `npm run lint` only. `npm run type-check` and Vitest are unaffected. Recommend a one-shot `npm install eslint@<compatible-ver>` follow-up outside this feature scope.
