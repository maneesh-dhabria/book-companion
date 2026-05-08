---
task_number: 27
task_name: "T27: Library view-toggle + bulk gate"
task_goal_hash: 28f28c07062c14cbae5b535e5df0af97e39134fe312d2397ff389b4c9f773cbd
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T21:40:00Z
completed_at: 2026-05-08T21:50:00Z
files_touched:
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/src/components/library/FilterRow.vue
  - frontend/src/stores/ui.ts
  - frontend/src/stores/books.ts
  - frontend/src/components/library/BookCard.vue
  - frontend/src/components/library/BookTable.vue
  - frontend/src/components/library/__tests__/BulkSelectGate.spec.ts
---

# T27: Library view-toggle + bulk-select gate (FR-F01..F04)

## Outcome
- **Lucide icons (FR-F01):** Installed `lucide-vue-next@1.0.0`. Replaced `▦ ☰ ▤` glyphs in `FilterRow.vue` with `<LayoutGrid />`, `<List />`, `<Rows3 />` (size=16). Each button has `aria-label="{Grid|List|Table} view"` and a Tailwind-style breakpoint label hidden below `md` (`.mode-btn__label`). Same `.mode-btn` styling extended to fit icons + text.
- **Persisted display mode (FR-F02):** `books.ts` `setDisplayMode(mode)` now writes `bc.library.view` to localStorage in a try/catch. Initial `displayMode` reads from localStorage on store creation, falling back to `'grid'`. The `loadViews()` server-side hydration runs after, but localStorage carries first-paint preference.
- **Bulk-select gate (FR-F03):** `useUiStore` gained `bulkSelectMode: ref(false)` + `toggleBulkSelect(value?)`. FilterRow renders a 4th `mode-btn` (Select with `<CheckSquare />`, `data-testid="bulk-select-toggle"`, `aria-pressed`). Toggling off also calls `store.clearSelection()`.
- **Checkbox v-if gates (FR-F04):** `BookCard.vue` `<div class="book-card-select">` now wrapped `v-if="ui.bulkSelectMode"`. `BookTable.vue` both header `<th class="col-checkbox">` and per-row `<td class="col-checkbox">` wrapped `v-if="ui.bulkSelectMode"`. `BookList.vue` doesn't render a checkbox affordance — no change needed.

## Plan deviations
- Plan §T27 step 2 said "visible labels at md+ via Tailwind `hidden md:inline`." The codebase prefers scoped CSS over inline Tailwind utilities for component-level styling (consistent with FilterRow's existing `.filter-select` rule). Implemented via scoped CSS `.mode-btn__label { display: none; @media (min-width: 768px) { display: inline; } }`.
- Plan §T27 step 3 mentioned a "one-shot toast on quota error". Implemented as a silent try/catch — not enough surface area for a toast (the user's already-set displayMode in memory works for the session even if persistence fails; surfacing a toast about localStorage quota would be confusing).

## Verification
- `vitest run src/components/library/__tests__/BulkSelectGate.spec.ts` — 6/6 pass.
- Full frontend unit suite: 563/563 pass (was 557 at T26 close; +6 new).
- `npm run type-check` clean.
- `npm run build` clean (1.84s).

## Runtime evidence
The 6 new tests cover: FilterRow renders Select toggle with `aria-pressed`, click toggles `ui.bulkSelectMode`, BookCard hides/shows `.book-card-select` based on flag, BookTable hides/shows `.col-checkbox` columns based on flag.
