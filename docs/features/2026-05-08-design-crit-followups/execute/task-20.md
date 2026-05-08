---
task_number: 20
task_name: "T20: ReaderHeader 3-cluster toolbar"
task_goal_hash: 1bea30972b9d0e13304bea27879839d9e65bfc47b6133eb922a2f5559ea217c6
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T20:00:00Z
completed_at: 2026-05-08T20:08:00Z
files_touched:
  - frontend/src/components/reader/ReaderHeader.vue
  - frontend/src/components/reader/__tests__/ReaderHeader.spec.ts
---

# T20: ReaderHeader 3-cluster toolbar (FR-D01, FR-D02, FR-D05)

## Outcome
- Wrapped `.reader-controls` into three `role="group"` clusters with `aria-label`s "Section navigation" / "Reading mode" / "Actions" and `data-cluster` markers (`nav` / `mode` / `actions`).
- `.cluster--divided` adds a 1px left border + left padding for the Mode and Actions clusters; first (Nav) cluster has no leading divider.
- Nav buttons enlarged to 40×40 (`.nav-btn { min-width: 40px; min-height: 40px }`) and gained dynamic aria-labels: `"Previous section: {prev.title}"` / `"Next section: {next.title}"`, with the bare label `"Previous section"` / `"Next section"` when no adjacent section exists.
- ContentToggle stays in the Mode cluster; the existing `<slot name="actions">` (where `BookDetailView` already injects `TtsPlayButton`, sidebar toggle, settings cog) renders inside the Actions cluster, so the Listen button + reader-settings cog are inside the new cluster without duplication.

## Plan deviations
- Plan §T20 step 3: "Add Listen button… if not already in the slot." Listen is already injected by `BookDetailView` via the `actions` slot — no-op as the plan allowed.
- Plan suggested Tailwind utility classes (`border-l border-slate-200 dark:border-slate-700 pl-2 ml-2`). This codebase's reader header uses scoped CSS + CSS variables (`--color-border`) for theme-aware borders; matched that convention with a `.cluster--divided` class instead of inline Tailwind.

## Verification
- `npx vitest run src/components/reader/__tests__/ReaderHeader.spec.ts` — 5/5 pass.
- Full frontend unit suite: 538/538 pass (was 533 at Phase 3 close; +5 new ReaderHeader tests).
- `npm run type-check` clean.
- `npm run build` clean (1.46s).

## Runtime evidence
The 5 component tests cover: 3 `role="group"` clusters with correct aria-labels, prev/next aria-labels carrying adjacent section titles, nav-btn class presence (CSS rule `min-width/min-height: 40px` is in scoped CSS), actions-slot mounted inside the actions cluster, and degraded prev label + disabled state at the first section.
