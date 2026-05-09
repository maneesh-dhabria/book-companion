---
task_number: 33
task_name: "SessionEndActions + ExportSessionModal (UI shell)"
task_goal_hash: e18afccce48cd06c96e0b907dba32a0283092fdadf80b88fa758a4fd6ca2dfd3
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T07:03:00Z
completed_at: 2026-05-09T07:14:00Z
files_touched:
  - frontend/src/components/quiz/SessionEndActions.vue
  - frontend/src/components/quiz/ExportSessionModal.vue
  - frontend/src/components/quiz/__tests__/SessionEndActions.spec.ts
---

## Summary

- **SessionEndActions.vue** — bottom action bar with Stop + Export buttons. Stop calls `stopSession(sessionId)` and emits `stopped` with the updated session; double-click guard via local `stopping` ref. Export disabled iff `session.status === 'abandoned'` (E15 / FR-105); when disabled, shows `COPY.abandonedExportError` microcopy as a hint. Click opens the modal.
- **ExportSessionModal.vue** — backdrop + dialog. Confirm button creates a transient `<a download="…">` element pointing at `/api/v1/quiz-sessions/{id}/export?fmt=markdown` (T34 implements server-side), `.click()`s it, removes it, and emits `close`. Filename format: `{book_slug}_quiz_session_{sid}.md`. Cancel emits `close`.

## Verification

- `npx vitest run src/components/quiz/__tests__/SessionEndActions.spec.ts` → **7 passed**.
- Full unit suite → **667 passed** (was 660 after T32; +7).
- `npm run type-check` → 0 errors.

## Test coverage

| Test | Surface |
|------|---------|
| Stop disables on click and calls stopSession | FR-49 + wiring |
| Export disabled when status='abandoned' (E15 / FR-105) | gating |
| Export enabled for in_progress session | gating |
| Click Export opens the modal | UX |
| Shows abandoned-export error microcopy | COPY.abandonedExportError |
| ExportSessionModal triggers download with correct filename | filename format |
| ExportSessionModal emits close on cancel | wiring |

## Notes

- The download path uses a same-origin anchor click rather than `window.open` so the browser's normal download flow handles `Content-Disposition: attachment` from T34's response. This avoids opening a tab to display the Markdown inline.
- The modal stub here is intentionally minimal — no progress indicator, no JSON-format toggle, no toast on failure. Plan only required the UI shell. T34's server-side route returns the file synchronously, and a 4xx/5xx will bubble up as a normal browser download error (no app-level toast yet). If user-feedback testing flags this as too quiet, T34's commit window or a follow-up can lift the click into a `fetch` + Blob URL with toast on failure.
- The Stop button's behavior here only calls `stopSession` and emits `stopped`. The parent `<ActiveSession>` (T28 stub, will be wired more fully in the QuizTab integration) is responsible for calling `store.loadForBook(bookId)` to flip the UI back to the scope-picker mode after `stopped` fires.
- `bookSlug` is plumbed in by the parent. Consumers without a slug can pass the book id stringified — the export filename remains valid (just less human-friendly).
