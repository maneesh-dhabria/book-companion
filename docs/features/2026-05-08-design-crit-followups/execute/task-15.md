---
task_number: 15
task_name: "T15: OverviewDashboard"
task_goal_hash: 32dac10dc01072bc37cd15080d9328965653c15f0441e78166e9f91de43ac85f
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T17:55:00Z
completed_at: 2026-05-08T18:08:00Z
files_touched:
  - frontend/src/components/book/OverviewDashboard.vue
  - frontend/src/components/book/__tests__/OverviewDashboard.spec.ts
  - frontend/src/views/BookOverviewView.vue
---

# T15: OverviewDashboard component (FR-C01..C05)

## Outcome
- New `OverviewDashboard.vue` renders a 2×2 CSS grid of 4 tiles: `tile-continue`, `tile-summary`, `tile-concepts`, `tile-sections`. Single column on mobile, 2-up on `md+`.
- **Continue tile:** title flips between "Continue reading" / "Start reading" based on whether `/api/v1/reading-state/by-book/{bookId}` returned a non-null `last_section_id`. Subtitle is `§{order_index} · {section.title}` for the chapter resolved by `firstChapter`. When no chapter exists, the tile renders disabled with the empty-state subtitle "Waiting for the first chapter to parse."
- **Book summary tile:** routes to `/books/{id}?tab=summary`. Subtitle includes preset + `formatDate(generated_at)` when populated, else "No book summary — Generate".
- **Top concepts tile:** fetches `/api/v1/concepts?book_id={id}&per_page=200` once on mount, sorts client-side by `created_at ASC` (the API doesn't expose this sort key directly), slices to 5, renders each as a `chip chip--accent` linking to `/concepts?book={id}&concept={term}`. Empty → "No concepts mined yet". While loading (`concepts === null`), 3 skeleton lines.
- **Sections tile:** routes to `?tab=sections`. Subtitle `{count} sections · ≈ {Nh Mm} read · See all` via `formatReadTimeSum`.
- `BookOverviewView.vue` Overview tab body (lines 103–112) replaced with `<OverviewDashboard :book="book" />`.

## Plan deviations
- Step 0 of the plan: confirmed `GET /api/v1/concepts` supports `?book_id=` filter (`backend/app/api/routes/concepts.py:20-22`). The route's `sort` param accepts `term` or `updated_at` only — NOT `created_at_asc`. Fell back to "fetch up to 200 + client-side sort by `created_at`" as the plan's contingency prescribed. Documented this in the commit message.
- Continue tile route uses `firstChapter` even when `last_section_id` exists (per FR-B02 consistency), not the recorded section_id. The label distinction ("Continue" vs "Start") still reflects the existence of the reader_position. The tests assert this behavior.
- Skeleton uses `.skeleton` + `.skeleton-line` + custom width modifiers in scoped CSS instead of Tailwind utility classes. Tailwind's `animate-pulse` ships with Tailwind v4, but using a scoped keyframe keeps the component self-contained for the personal-tool scale and matches the existing component-level scoped CSS convention.

## Verification
- `npm run test:unit -- --run src/components/book/__tests__/OverviewDashboard.spec.ts` — 6/6 pass.
- Full frontend unit suite: 516/516 pass (was 510 after T14; +6 new).
- `npm run type-check` clean.
- BookOverviewView existing tests (9/9) still green — the dashboard's fetches fall through the test mocks to the generic `'{}'` response without breaking the tab-routing tests.

## Runtime evidence
The 6 component tests cover: (1) all 4 tiles present; (2) Continue tile uses firstChapter + "Continue reading" label when reader_position exists; (3) "Start reading" label when no reader_position; (4) Sections tile renders the correct `formatReadTimeSum` value; (5) concepts render in `created_at ASC` order; (6) skeleton lines visible during loading and removed once concepts resolve. Tests run a real `vue-router` instance and assert anchor `href` attributes.
