---
phase_number: 2
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
tasks: [7, 8, 9, 10, 11]
verify_status: passed
verified_at: 2026-05-08T17:15:00Z
evidence_dir: "docs/features/2026-05-08-design-crit-followups/verify/2026-05-08-phase-2/"
---

# Phase 2 — Tokens + h1 hierarchy

5 tasks shipped: chip token CSS (T7), first-class chip rewrites for TagChip/EngineChip/Limited-controls (T8), 14-site chip sweep onto tokens (T9), non-text-contrast audit + fixes for 6 of 7 decorative dot sites (T10), TopBar h1 demote + ReaderHeader h1 promote (T11).

Phase verify on 2026-05-08 returned `ok: true`. Frontend unit suite 504/501 passing (+3 new from h1Count.spec.ts), backend regression-clean at 1019/1019, build clean, plan regression grep returns no `rounded-full + bg-*-100|200` chip-shaped Tailwind utilities. ESLint is broken on this repo (pre-existing tooling issue on main, not introduced).

Phase 3 may begin (T12 — Wire firstChapter into BookOverviewView Read CTA).
