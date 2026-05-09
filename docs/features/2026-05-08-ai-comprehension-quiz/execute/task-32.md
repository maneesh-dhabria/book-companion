---
task_number: 32
task_name: "SessionTally + PastQAPanel + ThemesCoveredPanel"
task_goal_hash: 2b8b26ca06ac4ed5f0e70738b93180c989d89c7d1c0f49bf517881714267d264
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T06:48:00Z
completed_at: 2026-05-09T07:01:00Z
files_touched:
  - frontend/src/components/quiz/SessionTally.vue
  - frontend/src/components/quiz/PastQAPanel.vue
  - frontend/src/components/quiz/PastSessionGroup.vue
  - frontend/src/components/quiz/PastQuestionRow.vue
  - frontend/src/components/quiz/ThemesCoveredPanel.vue
  - frontend/src/components/quiz/__tests__/PastQAPanel.spec.ts
---

## Summary

- **SessionTally.vue** — sticky header. Format: `Session: G/P/M (N skipped) · Lifetime: G/P/M across N sessions`. Hidden when there is neither in-flight session activity nor any completed sessions (E24).
- **PastQAPanel.vue** — replaces the T26 stub. Sorts sessions by `created_at` descending and renders one `<PastSessionGroup>` per session with `defaultExpanded={idx===0}` so the most recent is open by default. Empty state when `sessions=[]`.
- **PastSessionGroup.vue** — collapsible header (caret + session id + date + question count + tally). On first expand, fetches questions via `getSession(session.id)` and lists them as `<PastQuestionRow>`s. Subsequent toggles do not refetch (cached on the component).
- **PastQuestionRow.vue** — single row with shape badge, stale badge (`is_stale=true` → `stale (re-imported)` per FR-93), discarded badge, warm-up badge, self-assessment badge, stem, user-answer or "(skipped)", optional override note.
- **ThemesCoveredPanel.vue** — paragraph + heuristic chip extraction. Splits on `,`, `;`, " and " (case-insensitive); de-dupes case-insensitively while preserving order; keeps phrases ≤6 words. Chip click emits `seed-theme` (FR-63 wiring back to `<ThemeInput>`).

## Verification

- `npx vitest run src/components/quiz/__tests__/PastQAPanel.spec.ts` → **13 passed**.
- Full unit suite → **660 passed** (was 647 after T31; +13).
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| SessionTally renders session + lifetime line | format |
| SessionTally hidden when no completed sessions exist (E24) | gating |
| PastQuestionRow renders "stale (re-imported)" when is_stale=true (FR-93) | stale badge |
| PastQuestionRow no badge when is_stale=false | gating |
| PastQuestionRow renders discarded badge | discarded surfacing |
| PastSessionGroup default-expanded fetches and renders rows | lazy load on expand |
| PastSessionGroup collapsed-by-default does not fetch | no eager work |
| PastQAPanel groups + sorts: most-recent expanded | FR-92 / D23 |
| PastQAPanel empty state | gating |
| ThemesCoveredPanel renders chips from paragraph | heuristic extraction |
| ThemesCoveredPanel emits seed-theme on chip click (FR-63) | wiring |
| ThemesCoveredPanel hidden when null | gating |
| ThemesCoveredPanel hidden when empty string | gating |

## Notes

- Chip extraction is intentionally conservative — better to under-chip than mangle the paragraph. The plan notes a fallback "render as plain paragraph + a single 'Use theme' affordance per recognized phrase"; the current impl already meets that target by emitting chips only when the heuristic finds noun-phrase fragments and falling back to the paragraph view otherwise.
- The `PastQAPanel` still takes a `sessions: QuizSessionListItem[]` prop, so the existing QuizTab call site (`<PastQAPanel :sessions="pastSessions" />`) keeps working without modification — the migration from stub to real component was contract-compatible.
- `PastSessionGroup` caches questions on first load via `loaded.value` flag; collapse + re-expand does NOT refetch. If a session's questions can change after first load (e.g., re-import marks rows stale), the parent should signal a refresh — not handled in this task.
- T33 will compose `<SessionTally>` into the active-session header; for now it lives only in this component file. The `sessionSkipped` prop is split out from `tally.skipped` because the backend's `tally` row currently only counts answered turns; the active session may track skip count separately on the question level. Caller decides which integer to pass.
