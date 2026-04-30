---
id: 0004
title: CLI parity for `bookcompanion edit sections` (merge/split/move/delete/set-type)
type: feature
status: inbox
priority: could
labels: [cli, sections]
created: 2026-04-30
updated: 2026-04-30
source: docs/specs/2026-04-30-upload-summarize-flow-ux-fixes-spec.md
spec_doc:
plan_doc:
pr:
parent:
dependencies: []
---

## Context

The 2026-04-30 upload+summarize UX-fixes spec scoped section editing to the web UI only. Backend `SectionEditService` already supports merge/split/move/delete/set_type/undo, and the new web Structure Editor exercises them via REST routes. CLI parity (`bookcompanion edit sections <book_id>` interactive mode) was explicitly listed as a non-goal for that ship but remains useful for users who prefer the CLI workflow.

## Acceptance Criteria

- `bookcompanion edit sections <book_id>` opens an interactive TUI (Rich-driven) listing sections with hotkeys for merge/split/move/delete/rename/set-type.
- Same backend service as the web UI (`SectionEditService`) — no duplicate logic.
- Auto-marks affected summaries stale + reverts `Book.status COMPLETED → PARSED` (mirrors web semantics).
- Refuses to operate when an active `ProcessingJob` exists for the book (409 equivalent).
- Tests cover at least one merge + one split flow.
