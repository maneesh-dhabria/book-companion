---
phase_number: 1
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
tasks: [1, 2, 3, 4, 5, 6, "6a"]
verify_status: passed
verified_at: 2026-05-08T16:00:00Z
evidence_dir: "docs/features/2026-05-08-design-crit-followups/verify/2026-05-08-phase-1/"
---

# Phase 1 — Backend foundations + helpers

7 tasks shipped: firstChapter helper (T1), readTime utility (T2), /continue FM filter (T3), /resume-banner endpoint (T4), /audio/sections/by-book (T5), /audio/positions/by-book (T6), /reading-state/by-book (T6a).

Phase verify run on 2026-05-08 returned `ok: true` with zero failures and zero gaps. Backend full suite 1019 passed (+18 new tests from this phase). Live curl smoke confirmed all four new endpoints return spec-shaped payloads.

Phase 2 may begin (T7 — Chip token CSS).
