---
task_number: 23
task_name: "T23: SentenceProgressBar"
task_goal_hash: 140582c7b8d46744971bef79e3c523e3c75ed92a8e2086b5540d187a30a54f62
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T20:35:00Z
completed_at: 2026-05-08T20:42:00Z
files_touched:
  - frontend/src/components/audio/SentenceProgressBar.vue
  - frontend/src/components/audio/Playbar.vue
  - frontend/src/components/audio/__tests__/Playbar.spec.ts
---

# T23: SentenceProgressBar (FR-E02)

## Outcome
- New `SentenceProgressBar.vue`: renders `totalSentences` segments in a flex strip. Each segment carries `data-segment` and `data-state="done|current|upcoming"` for testability + styling. Done segments fill `rgb(99 102 241)` (indigo); current is transparent with a 1px indigo border; upcoming is `rgb(226 232 240)` (slate). Dark-mode variants tuned (lighter indigo for done, slate-700 for upcoming). `role="progressbar"` with `aria-valuemin/max/now` + `aria-label="Sentence progress"`.
- Mounted inside `Playbar.vue` above the controls row. Restructured the playbar from a single-row flex to a two-row flex-col (progress strip + control row inside `.bc-playbar-row`). The bar renders on **both** engines (FR-E02) when `store.totalSentences > 0` and `store.status !== 'error'`.
- The bar self-hides when there are no sentences (e.g., during the `starting` state before sentence-offset metadata loads), so an empty zero-segment strip never appears.

## Plan deviations
- Plan §T23 step 2 prescribed Tailwind utility classes (`bg-indigo-500`, `border-indigo-500`, etc.). The codebase prefers explicit RGB colors with dark-mode handling done via `.dark` selectors (matches the `.chip--*` tokens added in T7). Implemented via scoped CSS with the same indigo palette.
- Plan §T23 step 1 said tests should assert by class name (`bg-indigo-500`, `border-indigo-500`). Switched to `data-state` attributes which are decoupled from styling — tests stay green if we ever theme-swap the colors.

## Verification
- `vitest run src/components/audio/__tests__/Playbar.spec.ts` — 13/13 pass (was 11; +2 new for FR-E02 segments + cross-engine).
- Full frontend unit suite: 545/545 pass (was 543 at T22 close; +2 new).
- `npm run type-check` clean.
- `npm run build` clean (1.41s).

## Runtime evidence
The 2 new tests cover:
1. mp3 engine, total=5, current=2: `[data-testid="sentence-progress-bar"]` exists with 5 `[data-segment]` children; states are `done, done, current, upcoming, upcoming`.
2. web-speech engine, total=3: bar still renders (cross-engine compatibility per FR-E02).
