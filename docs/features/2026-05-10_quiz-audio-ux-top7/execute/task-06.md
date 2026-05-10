---
status: done
started_at: 2026-05-10T12:39:00Z
completed_at: 2026-05-10T12:42:00Z
files_touched:
  - frontend/src/stores/ui.ts
  - frontend/src/stores/__tests__/ui.toast.spec.ts
---

Extended `Toast` interface with `actionable`, `action`, `dedupeKey`, `dismissible`. `showToast` now accepts a third arg as either `number` (legacy) or `ShowToastOptions`. Added `clearByKey` for canonical actionable-clear path. Used `reactive(new Map())` for `dedupeKeys` per CLAUDE.md gotcha #28. All 6 new tests + 5 pre-existing `ToastContainer` tests green.
