---
task_number: 29
task_name: "T29: Dark-mode contrast e2e"
task_goal_hash: 7074199a7b71b37416fe4b3eb81a99add4d4190993607357131c8ab73a3847d3
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T22:15:00Z
completed_at: 2026-05-08T22:23:00Z
files_touched:
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/e2e/dark-mode-contrast.spec.ts
  - Makefile
---

# T29: Dark-mode contrast e2e + chip regression grep (FR-A06, FR-A07, NFR-01, G3)

## Outcome
- **`@axe-core/playwright@4.11.3`** added as a devDependency.
- **`frontend/e2e/dark-mode-contrast.spec.ts`** — sweeps 5 routes (`/`, `/books/1`, `/books/1/sections/1`, `/concepts`, `/annotations`) × 2 themes (`light`, `dark`). Toggles the theme by writing `localStorage.theme` AND adding/removing the `dark` class on `<html>`, then `page.reload()` to ensure boot-time theme branches apply. Runs `AxeBuilder({ page }).withTags(['wcag2aa']).analyze()` per page; asserts the `color-contrast` violation list is empty. Logs offending nodes (target + summary) to console on failure for actionable triage.
- **`make test-e2e-contrast`** — Makefile target runs the spec via `npx playwright test e2e/dark-mode-contrast.spec.ts` from `frontend/`.
- **`make chip-regression-grep`** — secondary CI gate (G3). Two greps:
  1. Fail if `▦`, `☰</`, or `▤` reappear under `frontend/src` (the pre-Lucide view-toggle glyphs).
  2. Fail if Tailwind colour pairs like `bg-blue-100 text-blue-800` reappear (ad-hoc chip colours bypassing the chip tokens).

## Plan deviations
- Plan §T29 step 4 said "Run `make test-e2e-contrast` against a running dev server". The contrast spec runs against the e2e webServer block in `playwright.config.ts` (which starts `docker compose up`). Could not actually run the sweep here — Docker compose isn't started in this environment, and the worktree's purpose is the unit gate. The spec is structurally complete; running it requires the developer's local stack and a seeded book at id=1 (per the existing CLAUDE.md "Interactive verification" runbook). Documented as a deferred post-merge action.
- Plan §T29 didn't explicitly call for a regression grep target — the goal text mentioned it. Added it as a separate `make chip-regression-grep` target so it can run independently in CI without spinning up Playwright.

## Verification
- `make chip-regression-grep` — exits 0 with `✓ chip-regression-grep: clean.`
- Full frontend unit suite: 571/571 pass (was 571 at T28 close; net 0 — T29 doesn't touch unit-tested code).
- `npm run type-check` clean.
- `npm run build` clean (1.85s).
- `make test-e2e-contrast` — not run in this environment (no Docker compose stack running). Deferred to local verification after merge.

## Runtime evidence
The spec compiles cleanly (it's TypeScript + Playwright; Vite ignores the e2e dir). The `make chip-regression-grep` target ran and printed `✓ chip-regression-grep: clean.` against the current source tree, confirming both regression patterns are absent post-T27.
