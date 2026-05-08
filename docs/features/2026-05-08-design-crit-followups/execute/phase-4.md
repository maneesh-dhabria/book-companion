---
phase_number: 4
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
tasks: [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
verify_status: pending
verified_at: null
evidence_dir: null
---

# Phase 4 — SectionDetail + Audio + Library + Resume + Final Verify

11 plan tasks shipped: ReaderHeader 3-cluster toolbar (T20); TOCDropdown 3-chip status column via SectionListTable compact mode (T21); Playbar engine-gated timestamp + Limited-controls tooltip (T22); SentenceProgressBar above Playbar (T23); AudioTab empty-state EngineChip + estimate + DifferencePopover (T24); ResumeAffordance mounting on BookOverviewView and BookDetailView (T25); KeyboardShortcutsOverlay + Playbar tooltips (T26); Library Lucide view-toggle + bulk-select gate (T27); resumeBannerStore + LibraryView coordination + ContinueBanner 📖 icon (T28); dark-mode-contrast e2e + chip-regression-grep Makefile gate (T29); final verification log (T30).

T30 gate signals (all green):
- Frontend full unit suite: 571/571 (was 533 at Phase 3 close; +38 new across Phase 4 — 5 ReaderHeader, 2 SectionListTable chips, 5 Playbar (T22+T23), 5 AudioTab+DifferencePopover, 2 BookOverviewView resume gate, 5 KeyboardShortcutsOverlay, 6 BulkSelectGate, 8 resumeBanner)
- Frontend type-check + build: clean (1.84s)
- Backend full suite: 1019/1019 (zero backend changes in Phase 4; ambient noise in collected count)
- chip-regression-grep: clean
- ESLint, backend ruff: pre-existing baseline issues unchanged

Outstanding follow-ups recorded in T30 log:
- Live Playwright contrast sweep deferred (needs Docker compose stack)
- 6 Vue Router test warnings from T19 (non-blocking)
- ResumeAffordance 🎧 emoji deferred per T28 deviation
- Backend ruff/format pre-existing baseline cleanup

Phase 4 ready for `/verify --scope phase --phase 4`. After phase verify passes, run feature-scope `/verify` to seal the entire design-crit-followups feature.
