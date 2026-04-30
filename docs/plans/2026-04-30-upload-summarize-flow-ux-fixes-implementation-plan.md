# Upload + Summarize Flow — UX Fixes & Structure Editor — Implementation Plan

**Date:** 2026-04-30
**Spec:** [`docs/specs/2026-04-30-upload-summarize-flow-ux-fixes-spec.md`](../specs/2026-04-30-upload-summarize-flow-ux-fixes-spec.md)
**Requirements:** [`docs/requirements/2026-04-30-upload-summarize-flow-ux-fixes.md`](../requirements/2026-04-30-upload-summarize-flow-ux-fixes.md)

---

## Overview

Bundles a Tier-1 config-shape fix (rip out `LLMConfig.cli_command`, replace with provider-routed `config_dir`) with a Tier-2 enhancement: full Structure Editor (wizard + post-summary), live progress + global queue, persistent processing indicator with cancel, settings preflight, and XHR-driven upload progress.

Approach: **backend-first**, single feature branch, single PR. Backend phases land in dependency order (config → preflight → queue+cancel → section-edit additions), each with passing unit + integration tests before the next starts. Frontend follows in three slices (upload, structure editor, queue/settings UI), each smoke-verified against the running backend.

**Done when:**
- `grep -rn 'cli_command' backend/app/ frontend/src/` returns zero matches.
- Codex provider invokes `codex exec --skip-git-repo-check` with `CODEX_HOME` env, Claude provider injects `CLAUDE_CONFIG_DIR`.
- A fresh book runs end-to-end through Steps 1→4 with visible progress at every phase, no auto-redirect on Step 4.
- Two-book queue serializes globally (one RUNNING at a time), persistent indicator visible across routes, cancel works for both PENDING and RUNNING.
- `/books/:id/edit-structure` reuses the same StructureEditor; post-edit confirms invalidation, marks summaries stale, reverts `Book.status COMPLETED → PARSED`.
- Settings → LLM has provider dropdown with detected/version badges, `config_dir` input, banner + Re-detect button when preflight fails. Step 3 blocks Start when preflight fails.
- `pytest`, `ruff`, `npm run test:unit`, `npm run type-check`, and the 5 Playwright scenarios in §13.4 of the spec all pass.

**Execution order:**

```
Phase A (backend cli_command rip-out + config_dir)
  T1 → T2 → T3 → T4 → T5 → T6
                        │
Phase B (preflight)     ▼
  T7 → T8 → T9
                        │
Phase C (queue + cancel + migration)
  T10 → T11a → T11b → T12 → T13 → T14
                        │
Phase D (section-edit additions)
  T15 → T16 → T17 → T18
                        │
Phase E (frontend upload UX)
  T19
                        │
Phase F (StructureEditor + EditStructureView)
  T20 → T21 → T22 → T23
                        │
Phase G (queue store + JobProgress + persistent indicator)
  T24 → T25a → T25b
                        │
Phase H (LlmSettings rebuild + Step 3 preflight banner)
  T26
                        │
Phase I (final verification)
  T27
```

Within a phase, tasks are sequential — later tasks consume earlier code. Across phases, A→B→C→D are linear (cancel needs config_dir provider stable, etc.); E→H are linear by integration order. Phase D can begin once Phase C migration exists (T13). [P] markers are absent — backend test suites and lint share state, so serial execution avoids spurious failures.

---

## Decision Log

> Inherits all 19 decisions (D1–D19) from the spec. Entries below are implementation-specific.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| P1 | **Spec adjustment: use `Summary.content_id + content_type` instead of `Summary.section_id`** | (a) Add `section_id` denormalized column; (b) Use existing polymorphic FK | (b) `Summary` is polymorphic over `BookSection` and `Book`. Adding a denormalized `section_id` would diverge from `Image`/`Annotation` patterns. Adapt FR-B18 query: `WHERE content_type='section' AND content_id IN (:ids)`. |
| P2 | **Add `Summary.is_stale BOOLEAN NOT NULL DEFAULT 0` in same migration as `cancel_requested`** | (a) Add column; (b) Soft-delete via separate tombstone row; (c) Hard-delete on edit | (a) Spec FR-B19 requires "auto-mark Summary rows as stale" but the column doesn't exist yet (it exists on `EvalTrace`). One-line addition keeps the existing `is_stale` semantic uniform across summary + eval. Hard-delete (c) loses audit trail; tombstone (b) overcomplicated. |
| P3 | **`Book.default_summary_id` is the field; spec said `book_summary_id`** | n/a | Schema reality. References to `book_summary_id` in spec are read as `default_summary_id` everywhere in this plan. |
| P4 | **`BookStatus` transition is `COMPLETED → PARSED`, not `SUMMARIZED → PARSED`** | n/a | Schema reality (no `SUMMARIZED` enum value; `COMPLETED` is the post-summarize state). FR-B19's intent is preserved. |
| P5 | **Use the same Alembic migration for `cancel_requested` AND `summaries.is_stale` AND the new `(status, created_at)` index** | (a) One migration; (b) Three migrations | (a) All three are part of the same feature ship. Single up/down keeps rollback atomic. |
| P6 | **TDD per task, but consolidate "rename `cli_command` → `binary` across N call sites" into a single mechanical task with one passing-test gate** | (a) One task per file; (b) One task for the rename batch | (b) — 14 call sites listed in spec §6.1a. The grep regression gate is the test. Per-file tasks would be busywork. |
| P7 | **`SummarizationProgress.vue` is left as-is, `<JobProgress>` is the new canonical component** | (a) Refactor old component; (b) Extract new + delete old later; (c) Two components forever | (b) Spec FR-F14 explicitly says "do NOT extend the existing `SummarizationProgress.vue`". Keep the old one mounted only on `BookDetailView` for now; deletion is a follow-up. |
| P8 | **Per-job provider re-instantiation lives inside the queue worker's `_run_processing()`, not in the API route** | n/a | Spec FR-B12 mandates per-job re-instantiation. Practical placement: `_run_processing()` at promotion time reads `Settings()` fresh + calls `create_llm_provider()`. The API route never instantiates a provider after this change. |
| P9 | **`useJobQueueStore` replaces `useSummarizationJobStore` rather than extending it** | (a) Extend old store; (b) New store; (c) Both | (b) Old store is per-job, single-job. New store needs `runningJob + pendingJobs[]`. Replacing in the same PR avoids two stores reading the same SSE stream and doubling event handling. Migration: rename file, update all imports in one task. |
| P10 | **Drag-reorder uses HTML5 native API + custom keyboard handler** | (a) HTML5 native; (b) `vuedraggable` dep | (a) per user decision in /plan intake. Spec defaulted to (a); user confirmed. |
| P11 | **Single PR; backend phases land first inside the branch** | (a) Backend-first; (b) Vertical slices | (a) per user decision. Spec §14 also calls for "backend lands first" within a single PR. |
| P12 | **`config_dir` directory auto-create logged once per process via a module-level flag** | (a) Log every time; (b) Once per process | (b) — `mkdir(parents=True, exist_ok=True)` is idempotent but the log line shouldn't spam. Module-level `_config_dir_logged: set[str]` keyed by path string. |
| P13 | **Queue worker is a `BackgroundTasks`-style asyncio task started in FastAPI lifespan, stored on `app.state.job_queue_worker`** | (a) Lifespan task; (b) Separate process; (c) Per-request | (a) — single-process zero-service architecture. Lifespan startup/shutdown gives clean cancel semantics. |
| P14 | **Preflight result Pydantic model lives at `backend/app/services/llm_preflight.py`** | (a) New module; (b) Inside `summarizer/__init__.py` | (a) — separate concern, separate module. Settings UI consumes via API route, queue worker consumes via direct call. Keeps `summarizer/` focused on generation. |

---

## Code Study Notes

### Backend
- **`backend/app/config.py:23-35`** — `LLMConfig` has `extra="forbid"`. Fields to remove: `cli_command` (line 26). Field to add: `config_dir: Path | None = None`. Settings YAML merged in `Settings.model_post_init()` (lines 142–172) — `Path` fields are auto-coerced from strings by pydantic v2.
- **`backend/app/services/summarizer/llm_provider.py:17-36`** — `LLMProvider` ABC has `generate()` and `generate_with_image()`. No constructor signature in ABC.
- **`backend/app/services/summarizer/claude_cli.py:76-239`** — Subprocess env at `:124` already uses `os.environ.copy()`. `cli_command` references at `:24,44,49,79,84,98,103,128,134,145,159,183`. Helpers `_maybe_force_test_failure` (`:48-73`) and `_maybe_log` (`:22-45`) take `cli_command` parameter — rename to `binary` per FR-B07b.
- **`backend/app/services/summarizer/codex_cli.py:22-142`** — Currently `[self.cli_command, "-p", prompt, "--model", model]` at `:60-66`. Change to `[self.BINARY, "exec", "--skip-git-repo-check", "--model", model, "--output-format", "json"]` per spec D3 + FR-B06; prompt to stdin (matches Claude pattern). Schema-in-prompt injection at `:48-58` unchanged.
- **`backend/app/services/summarizer/__init__.py:8-27`** — `detect_llm_provider()` at `:8-14`, `create_llm_provider(provider, **kwargs)` at `:17-27`. Both providers accept `**kwargs` — drop `cli_command`, add `config_dir`.
- **`backend/app/exceptions.py:66-73`** — `SubprocessNotFoundError(cli_command)` constructor; rename param to `binary`.
- **`backend/app/api/routes/processing.py`** — `_run_processing()` at `:138-348`, launched via `asyncio.create_task(_run_processing())` at `:348` from the start route (`:29-36`). Cancel route at `:415-438` — currently flips DB to FAILED with no SIGTERM. `cli_command` at `:163` (provider construction inside `_run_processing`).
- **`backend/app/api/routes/sections.py`** — section-edit routes: `PATCH /{section_id}` (`:114-139`), `DELETE /{section_id}` (`:142-161`), `POST /merge` (`:164-180`), `POST /{section_id}/split` (`:183-203`), `POST /reorder` (`:206-222`). New routes to add: `GET /:book_id/sections/edit-impact`, `GET /:book_id/sections/:section_id/split-preview`.
- **`backend/app/services/section_edit_service.py`** — has DB-backed methods `db_merge`, `db_split_at_char`, `db_delete`, `db_move`. Need a `db_set_type` method (likely already covered by the existing PATCH route's title/type update path).
- **`backend/app/db/models.py:282-309`** — `ProcessingJob` columns: id, book_id, step, status, progress (JSON), error_message, started_at, completed_at, pid. Indexes: `ix_processing_jobs_book_status`, partial UNIQUE `ix_processing_jobs_one_active_per_book`. **Add column `cancel_requested BOOLEAN NOT NULL DEFAULT 0`.**
- **`backend/app/db/models.py:350-383`** — `Summary` columns: `id, content_id, content_type, summary_md, ...`. **No `is_stale` column** — add per P2. **No `section_id` denormalized column** — query via `(content_type='section', content_id IN ids)` per P1.
- **`backend/app/db/models.py:123-171`** — `Book.default_summary_id` (per P3), `Book.status: BookStatus` enum: `UPLOADING, PARSING, PARSED, SUMMARIZING, COMPLETED, PARSE_FAILED`. Transition is `COMPLETED → PARSED` per P4.
- **`backend/app/api/sse.py:9-41`** — `EventBus.publish(job_id, event_type, data)` is the emission API. Existing 8 events listed; new events (`job_queued`, `job_promoted`, `job_cancelling`) follow the same shape.
- **`backend/app/services/settings_service.py:117-141, 143-221`** — `get_safe_settings()` exposes `cli_command` at `:128` (delete that line, add `config_dir`). `update_settings()` validates via pydantic, deep-merges, atomic temp-file write — perfect spot to invalidate preflight cache (FR-B08a) at end of `update_settings()`.
- **Migrations:** `backend/app/migrations/versions/`. Latest: `f6a7b8c9d0e1_v1_5d_tags_schema_revival.py`. New file: `<8hex>_v1_6a_processing_job_cancel_and_summary_stale.py`.

### Frontend
- **`frontend/src/api/client.ts:93-106`** — `upload()` fetch-based; replace with XHR variant `uploadBook(file, onProgress)` per FR-F01.
- **`frontend/src/api/settings.ts:3-24`** — `LlmSettings` interface has `cli_command: string`. Drop it; add `config_dir: string | null`.
- **`frontend/src/api/processing.ts:85-117`** — SSE handler `connectSSE(jobId, handlers)`. New events to wire: `job_queued`, `job_promoted`, `job_cancelling`. Also need a global (no-job-id) SSE listener for queue-store seeding — investigate whether existing endpoint supports `*` or needs a sibling endpoint.
- **`frontend/src/components/upload/UploadWizard.vue:1-119`** — 4-step wizard, `currentStep` ref. Step 4 is a static card; replace with `<JobProgress>`. Step 2 child is `StructureReview`; replace with `<StructureEditor :mode="'wizard'">`.
- **`frontend/src/components/upload/DropZone.vue:1-67`** — emits `'file-selected'`. Wrap in new `<UploadFileCard>` parent that owns the XHR-progress state.
- **`frontend/src/components/upload/StructureReview.vue:1-64`** — read-only table; will be **replaced** by `<StructureEditor>` (rename file or delete and add `StructureEditor.vue`).
- **`frontend/src/components/book/SummarizationProgress.vue:1-169`** — kept as-is per P7. Old store reference `useSummarizationJobStore()` is replaced internally.
- **`frontend/src/components/settings/LlmSettings.vue:1-219`** — Provider dropdown at `:117-127`, `cli_command` input at `:131-143` (delete entire input + computed at `:34-41`), Save payload at `:43-61` (replace `cli_command` key with `config_dir`). Add provider-status badges, banner, Re-detect button.
- **`frontend/src/components/settings/__tests__/LlmSettings.spec.ts:9-25`** — fixture has `cli_command: 'claude'`; replace with `config_dir: null`. Add test asserting `cli_command` input is NOT rendered.
- **Stores:** `summarizationJob.ts:1-260` exists. Replace with `jobQueue.ts` per P9. `settings.ts` exists for app settings — extend with `preflight: PreflightResult | null`.
- **Router `frontend/src/router/index.ts:5-97`** — add `/books/:id/edit-structure` route → `EditStructureView`.
- **`frontend/src/components/app/AppShell.vue:1-51`** — mount `<PersistentProcessingIndicator>` here (after `<ToastContainer>` at `:23`).
- **`frontend/src/views/BookDetailView.vue:1-380`** — add "Edit Structure" button in `<ReaderHeader>`'s `#actions` slot (around `:190-224`). Hide when active job (E5). `bookId` from `route.params.id` (line 59).
- **Toast/dialog primitives:** No composable; use `useUiStore().showToast()`. Confirm dialogs need to be built (no existing primitive). Implement an inline `<ConfirmDialog>` component as part of T29 (cancel confirms) and reuse in T26 (edit-impact).
- **E2E pattern (`frontend/e2e/settings.spec.ts:1-28`):** Standard Playwright with `data-testid` selectors.

---

## Prerequisites

- Working tree clean on `main` (or feature branch). `git status` shows no uncommitted code; the unrelated `?? backlog/`, `?? docs/plans/2026-04-30-reader-settings-popover-consolidation-implementation-plan.md`, `?? reader-settings-*.png` may stay.
- `cd backend && uv sync --dev` succeeds.
- `cd frontend && npm install` succeeds.
- `claude --version` (≥2.1) AND `codex --version` (≥0.118) both on PATH for live E2E (mock for CI).
- A seeded test book in dev library.db: `cd backend && uv run python tests/fixtures/download_fixtures.py && uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub` (answer N to cleanup prompt).
- Port 8765 free (`lsof -ti:8765` returns nothing) for E2E backend; user's :8000 dev server can stay running.

---

## File Map

### Backend — created

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/app/services/llm_preflight.py` | `LLMPreflightService.check(provider) -> PreflightResult` with 60s in-process cache + `invalidate_cache()`. |
| Create | `backend/app/api/routes/llm.py` | `GET /api/v1/llm/status`, `POST /api/v1/llm/recheck`. |
| Create | `backend/app/services/job_queue_worker.py` | `JobQueueWorker` asyncio task: polls every 2s, atomic-promotes oldest PENDING, runs `_run_processing()` inline, observes `cancel_requested`. |
| Create | `backend/app/migrations/versions/<hex>_v1_6a_processing_job_cancel_and_summary_stale.py` | `cancel_requested` on `processing_jobs`; `is_stale` on `summaries`; index `ix_processing_jobs_status_created`. |
| Create | `backend/tests/unit/test_llm_preflight_service.py` | Preflight unit tests. |
| Create | `backend/tests/unit/test_job_queue_worker.py` | Queue worker promotion + atomic-update unit tests. |
| Create | `backend/tests/unit/test_processing_cancel.py` | Cancel-PENDING and Cancel-RUNNING flow tests. |
| Create | `backend/tests/integration/test_summarize_route_preflight.py` | 400 with `llm_provider_unavailable` when binary missing. |
| Create | `backend/tests/integration/test_section_edit_impact.py` | edit-impact endpoint behavior + auto-stale on edit routes. |
| Create | `backend/tests/integration/test_split_preview_route.py` | 3-mode split preview contract. |
| Create | `backend/tests/integration/test_section_edit_blocks_during_job.py` | 409 from edit routes when active job exists. |

### Backend — modified

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/config.py:25-26` | Drop `cli_command`; add `config_dir: Path \| None = None`. |
| Modify | `backend/app/exceptions.py:66-73` | Rename `cli_command` param to `binary`. |
| Modify | `backend/app/services/summarizer/claude_cli.py` | Class const `BINARY="claude"`; drop `cli_command` param; add `config_dir`; inject `CLAUDE_CONFIG_DIR` in env; rename log/test helpers' param. |
| Modify | `backend/app/services/summarizer/codex_cli.py` | Class const `BINARY="codex"`; drop `cli_command`; add `config_dir`; inject `CODEX_HOME`; switch argv to `codex exec --skip-git-repo-check`; pass prompt via stdin. |
| Modify | `backend/app/services/summarizer/__init__.py` | `create_llm_provider()` no longer accepts `cli_command`; passes `config_dir`. |
| Modify | `backend/app/api/deps.py:38-52` | Drop `cli_command=`, add `config_dir=`. |
| Modify | `backend/app/cli/deps.py:138-148` | Same. |
| Modify | `backend/app/api/routes/processing.py` | Remove `_run_processing()` background-task launch from start route; route now just creates `ProcessingJob{status=PENDING}` + emits `job_queued`. Add preflight gate. Replace cancel-route body with atomic DELETE-WHERE-PENDING + branch logic. Add `GET /api/v1/processing/jobs?status=`. |
| Modify | `backend/app/services/settings_service.py:128, 143-221` | `get_safe_settings()` drops `cli_command`, adds `config_dir`. `update_settings()` calls `LLMPreflightService.invalidate_cache()` post-commit. |
| Modify | `backend/app/cli/commands/config_cmd.py:75` | Update docstring example. |
| Modify | `backend/app/db/models.py:282-309` | Add `cancel_requested` column to `ProcessingJob`. |
| Modify | `backend/app/db/models.py:350-383` | Add `is_stale` column to `Summary`. |
| Modify | `backend/app/api/routes/sections.py` | Add `GET /:book_id/sections/edit-impact`, `GET /:book_id/sections/:section_id/split-preview`. Modify merge/split/move/delete/PATCH to (a) reject 409 when active job, (b) auto-mark `Summary.is_stale=True` for affected sections, (c) on book-summary invalidation, set `Book.default_summary_id=None` AND `Book.status=PARSED`. PATCH validates title length. |
| Modify | `backend/app/main.py` (or wherever FastAPI app is constructed) | Lifespan: start `JobQueueWorker` on startup, cancel on shutdown. |

### Frontend — created

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `frontend/src/components/upload/UploadFileCard.vue` | Per-file row, two-phase indicator (XHR-determinate → indeterminate parse), Cancel button. |
| Create | `frontend/src/components/upload/StructureEditor.vue` | Shared editor, `mode: 'wizard' \| 'post-summary'`, multi-select, drag, keyboard reorder. |
| Create | `frontend/src/components/upload/SplitModal.vue` | 3-mode split modal. |
| Create | `frontend/src/components/job/JobProgress.vue` | Renders pending/running/cancelling/completed/failed for a `jobId`. |
| Create | `frontend/src/components/job/PersistentProcessingIndicator.vue` | Bottom-bar indicator. |
| Create | `frontend/src/components/job/QueuePanel.vue` | Expanded queue list with per-row Cancel. |
| Create | `frontend/src/components/common/ConfirmDialog.vue` | Reusable confirm dialog (cancel-running, cancel-pending, edit-impact). |
| Create | `frontend/src/views/EditStructureView.vue` | Wraps `<StructureEditor :mode="'post-summary'">`. |
| Create | `frontend/src/stores/jobQueue.ts` | Pinia store with `runningJob`, `pendingJobs[]`, `connect()` 5-step seed-then-drain, reconnect with backoff. |
| Create | `frontend/src/components/upload/__tests__/UploadFileCard.spec.ts` | XHR progress, cancel disabled in parse phase. |
| Create | `frontend/src/components/upload/__tests__/StructureEditor.spec.ts` | Multi-select merge, bulk-delete-all disabled, rename validation. |
| Create | `frontend/src/components/job/__tests__/JobProgress.spec.ts` | Renders all 5 states, transitions on store change. |
| Create | `frontend/src/components/job/__tests__/PersistentProcessingIndicator.spec.ts` | v-show toggle, queue-list rendering. |
| Create | `frontend/src/stores/__tests__/jobQueue.spec.ts` | 5-step connect sequence, reconciliation by `last_event_at`, reconnect backoff. |

### Frontend — modified

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `frontend/src/api/client.ts:93-106` | Replace fetch upload with XHR `uploadBook(file, onProgress)`. |
| Modify | `frontend/src/api/settings.ts:3-24` | Drop `cli_command`; add `config_dir: string \| null`. |
| Modify | `frontend/src/api/processing.ts:85-117` | Add `job_queued`, `job_promoted`, `job_cancelling` event handlers; expose seed endpoint helper. |
| Modify | `frontend/src/components/upload/UploadWizard.vue` | Step 1 swaps DropZone↔UploadFileCard; Step 2 uses `<StructureEditor :mode="'wizard'">`; Step 3 reads preflight + disables Start; Step 4 uses `<JobProgress>` + new CTAs. |
| Modify | `frontend/src/components/upload/DropZone.vue` | Unchanged behavior; parent (`UploadFileCard`) wraps it on file pick. |
| Delete | `frontend/src/components/upload/StructureReview.vue` | Replaced by `StructureEditor.vue`. |
| Modify | `frontend/src/components/settings/LlmSettings.vue` | Drop `cli_command` input; add `config_dir` input; add provider badges + banner + Re-detect button. |
| Modify | `frontend/src/components/settings/__tests__/LlmSettings.spec.ts:9-25` | Update fixture; add "no `cli_command` rendered" assertion. |
| Delete | `frontend/src/stores/summarizationJob.ts` | Replaced by `jobQueue.ts`; update all imports. |
| Modify | `frontend/src/components/book/SummarizationProgress.vue` | Update import to `useJobQueueStore` if it still consumes job state, OR leave as-is if BookDetailView's reader doesn't need queue awareness — verify in T24. |
| Modify | `frontend/src/router/index.ts:5-97` | Add `/books/:id/edit-structure` route. |
| Modify | `frontend/src/components/app/AppShell.vue:23` | Mount `<PersistentProcessingIndicator>`; call `useJobQueueStore().connect()` in `onMounted`. |
| Modify | `frontend/src/views/BookDetailView.vue:190-224` | Add "Edit Structure" button to `#actions` slot; hide when active job. |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `codex exec --skip-git-repo-check` doesn't accept the same `--model`/stdin pattern as `codex -p` (OQ1). | Medium | T3 first task: smoke `codex exec --skip-git-repo-check --model gpt-5 --output-format json` with a tiny prompt on stdin and confirm JSON output. If it fails, halt and update spec D3 before proceeding. |
| Atomic `UPDATE … WHERE NOT EXISTS` SQL is dialect-fragile under SQLite + WAL. | Medium | T11 unit test asserts double-promotion is impossible by simulating two concurrent ticks (asyncio.gather with two worker instances against the same DB). |
| Pydantic `extra="forbid"` rejects existing dev settings.yaml that still has `cli_command`. | Low | T1 acceptance includes deleting `cli_command:` from the maintainer's local settings.yaml and verifying `bookcompanion serve` boots. Pre-release; no users to migrate. |
| FastAPI lifespan startup ordering: the queue worker depends on Settings being loaded. | Low | P13 puts the worker start AFTER Settings + DB engine init (already pattern). |
| SSE seed endpoint returns stale data between fetch and SSE-subscribe. | Medium | FR-F19b 5-step sequence (subscribe → buffer → fetch → drain → live) covers it; T24 jobQueue.spec.ts tests reconciliation by `last_event_at`. |
| `Summary.is_stale` migration applies to existing summaries and silently marks them all 0 — but the column also needs `selectinload` updates if any repo eager-loads stale-filtered summaries. | Low | T13 migration default is `0` (not stale). T18 grep verifies no existing query filters `is_stale` on Summary; if found, add `WHERE is_stale = 0` per existing EvalTrace pattern. |
| Deleting `summarizationJob.ts` breaks BookDetailView and SummarizationProgress.vue. | Medium | T24 is gated on green type-check. Imports updated atomically in same task. |
| Drag-reorder + 5s undo create a UX edge: user starts dragging while a delete-undo timer is running on another row. | Low | T24 specifies: drag operations on non-pending-delete rows are unaffected; undo timer for the deleted row is independent. Test in StructureEditor.spec.ts. |
| The "auto-mark Summary stale" path in section-edit routes (T18) needs a transaction around UPDATE summaries + UPDATE books; SQLite WAL handles it but the existing route may not wrap in `async with session.begin()`. | Medium | T18 review: ensure each modified route uses a single transaction; if not, wrap. |

---

## Rollback

- T13 migration failure: `cd backend && uv run alembic -c app/migrations/alembic.ini downgrade -1`. The previous head is `f6a7b8c9d0e1`.
- Branch-level rollback: `git revert <merge-commit>`. Spec §14 confirms no other rollback strategy.
- If backend ships and frontend doesn't (interrupted ship): backend is backward-compatible to the dropped `cli_command` *only via pydantic stripping on YAML load* — but the frontend payload would 422 on save. Don't merge backend without frontend.

---

## Tasks

---

### T1: Drop `LLMConfig.cli_command`, add `config_dir` field

**Goal:** Replace the foot-gun field with a provider-routed config-dir path.
**Spec refs:** D1, D2, D4, FR-B01, FR-B02

**Files:**
- Modify: `backend/app/config.py:25-26`
- Modify: `backend/tests/unit/test_config.py` (existing test file)

**Steps:**

- [ ] Step 1: Write failing test — `LLMConfig` accepts `config_dir`, rejects `cli_command`.
  ```python
  # backend/tests/unit/test_config.py — append
  import pytest
  from pathlib import Path
  from pydantic import ValidationError
  from app.config import LLMConfig

  def test_llm_config_accepts_config_dir(tmp_path):
      cfg = LLMConfig(config_dir=tmp_path)
      assert cfg.config_dir == tmp_path

  def test_llm_config_config_dir_default_none():
      cfg = LLMConfig()
      assert cfg.config_dir is None

  def test_llm_config_rejects_cli_command():
      with pytest.raises(ValidationError):
          LLMConfig(cli_command="claude")

  def test_llm_config_expands_user_path():
      cfg = LLMConfig(config_dir="~/.claude-personal")
      # field stores the literal Path; expansion is provider-side per FR-B02
      assert isinstance(cfg.config_dir, Path)
  ```

- [ ] Step 2: Run test → fail (`cli_command` is currently accepted).
  Run: `cd backend && uv run python -m pytest tests/unit/test_config.py::test_llm_config_rejects_cli_command -v`
  Expected: FAIL.

- [ ] Step 3: Edit `backend/app/config.py:25-26` — delete `cli_command: str = "claude"` line; add `config_dir: Path | None = None`. Ensure import for `Path` exists at top.

- [ ] Step 4: Run all 4 new tests → pass.
  Run: `cd backend && uv run python -m pytest tests/unit/test_config.py -v`
  Expected: 4 new passes, no regressions.

- [ ] Step 5: Delete `cli_command:` line from local `~/Library/Application Support/bookcompanion/settings.yaml` if present (pre-release; no users).
  Run: `grep -c cli_command ~/Library/Application\ Support/bookcompanion/settings.yaml || true`
  If >0: edit the file, remove the line.

- [ ] Step 6: Commit.
  ```bash
  git add backend/app/config.py backend/tests/unit/test_config.py
  git commit -m "feat(config): replace LLMConfig.cli_command with config_dir"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/config.py tests/unit/test_config.py` — clean.
- `cd backend && uv run python -c "from app.config import Settings; s = Settings(); print(s.llm.config_dir)"` — prints `None`.

---

### T2: Rename `cli_command` → `binary` across providers + exception + log helpers

**Goal:** Mechanical rename across the provider files; the binary is now a class constant, not a parameter.
**Spec refs:** FR-B01a, FR-B03, FR-B05, FR-B07a, FR-B07b, §6.1a

**Files:**
- Modify: `backend/app/exceptions.py:66-73`
- Modify: `backend/app/services/summarizer/claude_cli.py` (lines per spec §6.1a: 24, 44, 49, 79, 84, 98, 103, 128, 134, 145, 159, 183)
- Modify: `backend/app/services/summarizer/codex_cli.py` (lines 25, 30, 44, 61, 81, 87, 94, 106)
- Modify: `backend/app/services/summarizer/__init__.py:17-27` (drop `cli_command` from kwargs path)
- Modify: `backend/tests/unit/test_llm_provider.py` (existing tests for SubprocessNotFoundError)

**Steps:**

- [ ] Step 1: Write failing test for `SubprocessNotFoundError` accepting `binary`.
  ```python
  # backend/tests/unit/test_llm_provider.py — append
  from app.exceptions import SubprocessNotFoundError

  def test_subprocess_not_found_error_uses_binary_param():
      err = SubprocessNotFoundError(binary="claude")
      assert err.binary == "claude"
      assert "claude" in str(err)
      assert not hasattr(err, "cli_command")
  ```

- [ ] Step 2: Run → fail (`__init__` still expects `cli_command`).
  Run: `cd backend && uv run python -m pytest tests/unit/test_llm_provider.py::test_subprocess_not_found_error_uses_binary_param -v`
  Expected: FAIL.

- [ ] Step 3: Edit `backend/app/exceptions.py:66-73`:
  ```python
  class SubprocessNotFoundError(SummarizationError):
      """CLI binary is not available on PATH."""
      failure_type = "cli_not_found"

      def __init__(self, binary: str):
          self.binary = binary
          super().__init__(f"CLI binary not found on PATH: {binary!r}")
  ```

- [ ] Step 4: Edit `backend/app/services/summarizer/claude_cli.py`:
  - Add class-level `BINARY = "claude"` near top of class (around line 78).
  - Remove `cli_command: str = "claude"` from `__init__` signature; add `config_dir: Path | None = None`.
  - In `__init__` body, set `self.binary = self.BINARY` and `self.config_dir = config_dir`. Drop `self.cli_command = cli_command`.
  - In `generate()` argv (line ~103): `cmd = [self.BINARY, "-p", "-", ...]`.
  - In env construction (line ~124): after `env = os.environ.copy()`, add:
    ```python
    if self.config_dir is not None:
        cfg = self.config_dir.expanduser()
        cfg.mkdir(parents=True, exist_ok=True)
        if str(cfg) not in _LOGGED_CONFIG_DIRS:
            log.info("config_dir_initialized", path=str(cfg), provider="claude")
            _LOGGED_CONFIG_DIRS.add(str(cfg))
        env["CLAUDE_CONFIG_DIR"] = str(cfg)
    ```
  - Add module-level `_LOGGED_CONFIG_DIRS: set[str] = set()` near top of file (per P12).
  - In `SubprocessNotFoundError` raise sites (~line 128): `raise SubprocessNotFoundError(binary=self.BINARY)`.
  - In `SubprocessNonZeroExitError` raise sites (~line 159): replace `cli_command=self.cli_command` with `binary=self.BINARY` (and add `binary` kwarg to that exception class if missing — verify in `exceptions.py`).
  - Rename `_maybe_force_test_failure(cli_command, context)` → `_maybe_force_test_failure(binary, context)` and update call site at line ~98.
  - Rename `_maybe_log(cli_command=...)` → `_maybe_log(binary=...)` and update call site.

- [ ] Step 5: Edit `backend/app/services/summarizer/codex_cli.py`:
  - Class-level `BINARY = "codex"`.
  - Same `__init__` change pattern (drop `cli_command`, add `config_dir`).
  - **Argv switch:** at line ~60, replace `[self.cli_command, "-p", prompt, "--model", model]` with `[self.BINARY, "exec", "--skip-git-repo-check", "--model", model, "--output-format", "json"]`. Pass prompt via stdin (mirror Claude pattern in `claude_cli.py:108-119`):
    ```python
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(input=prompt.encode("utf-8")),
        timeout=...,
    )
    ```
  - Env injection: same shape as Claude but `env["CODEX_HOME"] = str(cfg)`.
  - Update all raise sites and log helper calls.

- [ ] Step 6: Edit `backend/app/services/summarizer/__init__.py:17-27` — `create_llm_provider(provider, **kwargs)` no longer needs special handling; just pass kwargs through. Drop any `cli_command` reference.

- [ ] Step 7: Run unit tests → pass.
  Run: `cd backend && uv run python -m pytest tests/unit/test_llm_provider.py -v`
  Expected: all green.

- [ ] Step 8: Commit.
  ```bash
  git add backend/app/exceptions.py backend/app/services/summarizer/ backend/tests/unit/test_llm_provider.py
  git commit -m "refactor(llm): rename cli_command to binary; class-const BINARY; config_dir env injection"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/summarizer/ app/exceptions.py` — clean.
- `cd backend && uv run python -c "from app.services.summarizer import create_llm_provider; p = create_llm_provider('claude', config_dir=None); print(p.BINARY, p.config_dir)"` — prints `claude None`.

---

### T3: Smoke-test `codex exec` invocation (resolves OQ1)

**Goal:** Confirm `codex exec --skip-git-repo-check --model X --output-format json` accepts stdin prompt + emits JSON before committing the rewrite.
**Spec refs:** D3, OQ1, FR-B06

**Files:**
- Add: scratch script `backend/tests/manual/codex_exec_smoke.py` (gitignored or deleted after).

**Steps:**

- [ ] Step 1: Write smoke script.
  ```python
  # backend/tests/manual/codex_exec_smoke.py
  import asyncio, sys
  async def main():
      proc = await asyncio.create_subprocess_exec(
          "codex", "exec", "--skip-git-repo-check", "--model", "gpt-5",
          "--output-format", "json",
          stdin=asyncio.subprocess.PIPE,
          stdout=asyncio.subprocess.PIPE,
          stderr=asyncio.subprocess.PIPE,
      )
      out, err = await proc.communicate(b"Reply with the literal JSON: {\"ok\": true}")
      print("STDOUT:", out.decode()[:500])
      print("STDERR:", err.decode()[:500])
      print("RC:", proc.returncode)
  asyncio.run(main())
  ```

- [ ] Step 2: Run.
  Run: `cd backend && uv run python tests/manual/codex_exec_smoke.py`
  Expected: rc=0, stdout contains parseable JSON.

- [ ] Step 3: **If smoke succeeds** — proceed to T4. **If smoke fails** — STOP, capture error, update spec D3 with corrective decision before proceeding.

- [ ] Step 4: Delete the scratch script.
  Run: `rm backend/tests/manual/codex_exec_smoke.py`

- [ ] Step 5: No commit (scratch only). Decision recorded inline if smoke failed.

**Inline verification:**
- Decision documented in this plan's Review Log if smoke result alters T2 implementation.

---

### T4: Update factory + deps wiring; full grep gate

**Goal:** Last orphan call sites; verify zero `cli_command` references in source.
**Spec refs:** FR-B07, FR-B01a, §6.1a, §13.5

**Files:**
- Modify: `backend/app/cli/deps.py:138-148`
- Modify: `backend/app/api/deps.py:38-52`
- Modify: `backend/app/api/routes/processing.py:163` (the `_run_processing` provider construction)
- Modify: `backend/app/api/routes/book_summary.py:142`
- Modify: `backend/app/api/routes/ai_threads.py:169`
- Modify: `backend/app/cli/commands/config_cmd.py:75` (docstring)

**Steps:**

- [ ] Step 1: Write failing test — grep gate.
  ```python
  # backend/tests/unit/test_no_cli_command_orphans.py
  import subprocess
  from pathlib import Path

  def test_no_cli_command_references_in_source():
      repo_root = Path(__file__).resolve().parents[3]
      result = subprocess.run(
          ["grep", "-rn", "cli_command",
           str(repo_root / "backend" / "app"),
           str(repo_root / "frontend" / "src")],
          capture_output=True, text=True,
      )
      lines = [l for l in result.stdout.splitlines()
               if "/static/" not in l and ".pyc" not in l]
      assert lines == [], f"Orphan cli_command refs:\n" + "\n".join(lines)
  ```

- [ ] Step 2: Run → fail (frontend still has refs; that's fine — frontend is later phase). For now, scope the grep test to backend only:
  ```python
  result = subprocess.run(
      ["grep", "-rn", "cli_command", str(repo_root / "backend" / "app")],
      ...
  )
  ```
  Expected after backend cleanup in this task: 0 lines. Frontend grep gate is added in T30.

- [ ] Step 3: Edit each call site:
  - `backend/app/cli/deps.py:138-148` — replace `cli_command=settings.llm.cli_command` with `config_dir=settings.llm.config_dir`.
  - `backend/app/api/deps.py:38-52` — same.
  - `backend/app/api/routes/processing.py:163` — same. Note: this construction will be **moved** to the queue worker in T11; for now, just rename.
  - `backend/app/api/routes/book_summary.py:142` — same.
  - `backend/app/api/routes/ai_threads.py:169` — same.
  - `backend/app/cli/commands/config_cmd.py:75` — replace docstring example `llm.cli_command` → `llm.config_dir`.

- [ ] Step 4: Run grep test → pass (backend only).
  Run: `cd backend && uv run python -m pytest tests/unit/test_no_cli_command_orphans.py -v`
  Expected: PASS.

- [ ] Step 5: Manual grep verification.
  Run: `grep -rn 'cli_command' backend/app/ | grep -v '/static/'`
  Expected: empty.

- [ ] Step 6: Run full unit suite — no regressions.
  Run: `cd backend && uv run python -m pytest tests/unit/ -v`
  Expected: all green.

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/cli/deps.py backend/app/api/deps.py backend/app/api/routes/ backend/app/cli/commands/config_cmd.py backend/tests/unit/test_no_cli_command_orphans.py
  git commit -m "refactor(deps): drop cli_command from create_llm_provider call sites"
  ```

**Inline verification:**
- Manual grep returns empty for backend.
- `cd backend && uv run python -m pytest tests/unit/ -v` — all green.

---

### T5: Update `SettingsService.get_safe_settings()` to expose `config_dir`

**Goal:** Settings UI sees the new field; no orphan `cli_command` in safe-settings payload.
**Spec refs:** FR-B01a, §6.1a

**Files:**
- Modify: `backend/app/services/settings_service.py:128`
- Modify: `backend/tests/unit/test_settings_service.py`

**Steps:**

- [ ] Step 1: Write failing test.
  ```python
  # backend/tests/unit/test_settings_service.py — append
  def test_get_safe_settings_includes_config_dir(settings_service):
      safe = settings_service.get_safe_settings()
      assert "config_dir" in safe["llm"]
      assert "cli_command" not in safe["llm"]
  ```

- [ ] Step 2: Run → fail.
  Expected: KeyError or assertion on `cli_command not in`.

- [ ] Step 3: Edit `:128` — replace `"cli_command": self.settings.llm.cli_command` with `"config_dir": str(self.settings.llm.config_dir) if self.settings.llm.config_dir else None`.

- [ ] Step 4: Run → pass.
  Run: `cd backend && uv run python -m pytest tests/unit/test_settings_service.py -v`

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/services/settings_service.py backend/tests/unit/test_settings_service.py
  git commit -m "feat(settings): expose config_dir in safe settings; drop cli_command"
  ```

**Inline verification:** unit test green.

---

### T6: Provider-level integration smoke test

**Goal:** Verify `claude_cli.py` env injection actually puts `CLAUDE_CONFIG_DIR` in subprocess env (and `codex_cli.py` puts `CODEX_HOME`).
**Spec refs:** FR-B04, FR-B05, FR-B22, §13.1

**Files:**
- Modify: `backend/tests/unit/test_claude_cli_provider.py` (create if missing)
- Modify: `backend/tests/unit/test_codex_cli_provider.py` (create if missing)

**Steps:**

- [ ] Step 1: Write failing tests.
  ```python
  # backend/tests/unit/test_claude_cli_provider.py
  from unittest.mock import patch, MagicMock
  import pytest
  from pathlib import Path
  from app.services.summarizer.claude_cli import ClaudeCodeCLIProvider

  @pytest.mark.asyncio
  async def test_claude_provider_injects_config_dir_env(tmp_path):
      provider = ClaudeCodeCLIProvider(config_dir=tmp_path)
      with patch("asyncio.create_subprocess_exec") as mock_exec:
          mock_proc = MagicMock()
          mock_proc.communicate = MagicMock(return_value=...)  # mock out
          mock_exec.return_value = mock_proc
          # ...invoke generate(); inspect env kwarg
          # Assert: kwargs["env"]["CLAUDE_CONFIG_DIR"] == str(tmp_path)
          assert mock_exec.call_args.kwargs["env"]["CLAUDE_CONFIG_DIR"] == str(tmp_path)

  @pytest.mark.asyncio
  async def test_claude_provider_no_config_dir_no_env(tmp_path):
      provider = ClaudeCodeCLIProvider(config_dir=None)
      # ...invoke generate(); assert "CLAUDE_CONFIG_DIR" not in env

  @pytest.mark.asyncio
  async def test_claude_provider_creates_missing_config_dir(tmp_path):
      target = tmp_path / "new_subdir"
      assert not target.exists()
      provider = ClaudeCodeCLIProvider(config_dir=target)
      # ...invoke generate(); assert target.exists()
  ```
  Mirror in `test_codex_cli_provider.py` with `CODEX_HOME` and assert argv = `["codex", "exec", "--skip-git-repo-check", "--model", ...]`.

- [ ] Step 2: Run → fail or pass depending on T2 quality. Fix any gaps in T2 implementation.
  Run: `cd backend && uv run python -m pytest tests/unit/test_claude_cli_provider.py tests/unit/test_codex_cli_provider.py -v`

- [ ] Step 3: Iterate until green.

- [ ] Step 4: Commit.
  ```bash
  git add backend/tests/unit/test_claude_cli_provider.py backend/tests/unit/test_codex_cli_provider.py
  git commit -m "test(llm): assert config_dir env injection + codex exec argv"
  ```

**Inline verification:** all tests green; assert real subprocess env contains `CLAUDE_CONFIG_DIR=<path>` after a mocked invocation.

---

### T7: `LLMPreflightService` with 60s cache + invalidation hook

**Goal:** Single source of truth for "is the LLM CLI usable right now?"
**Spec refs:** FR-B08, FR-B08a, NFR-01, §13.1

**Files:**
- Create: `backend/app/services/llm_preflight.py`
- Create: `backend/tests/unit/test_llm_preflight_service.py`
- Modify: `backend/app/services/settings_service.py` (call `invalidate_cache()` post-commit)

**Steps:**

- [ ] Step 1: Define `PreflightResult` typed dict / Pydantic model.
  ```python
  # backend/app/services/llm_preflight.py
  from pydantic import BaseModel
  class PreflightResult(BaseModel):
      ok: bool
      binary_resolved: bool
      version: str | None
      version_ok: bool
      reason: str | None
  ```

- [ ] Step 2: Write failing tests.
  ```python
  # backend/tests/unit/test_llm_preflight_service.py
  import pytest
  from unittest.mock import patch
  from app.services.llm_preflight import LLMPreflightService

  @pytest.mark.asyncio
  async def test_preflight_binary_not_found(monkeypatch):
      monkeypatch.setattr("shutil.which", lambda b: None)
      svc = LLMPreflightService()
      result = await svc.check("claude")
      assert result.ok is False
      assert result.binary_resolved is False
      assert "PATH" in result.reason

  @pytest.mark.asyncio
  async def test_preflight_old_version_non_blocking(monkeypatch):
      monkeypatch.setattr("shutil.which", lambda b: "/usr/local/bin/claude")
      # mock subprocess version output → "1.5.0"
      svc = LLMPreflightService()
      result = await svc.check("claude")
      assert result.ok is True  # non-blocking
      assert result.binary_resolved is True
      assert result.version_ok is False

  @pytest.mark.asyncio
  async def test_preflight_caches_60s(monkeypatch):
      call_count = 0
      def fake_which(b):
          nonlocal call_count; call_count += 1; return "/usr/bin/claude"
      monkeypatch.setattr("shutil.which", fake_which)
      svc = LLMPreflightService()
      await svc.check("claude")
      await svc.check("claude")
      assert call_count == 1  # cached

  @pytest.mark.asyncio
  async def test_preflight_cache_invalidate(monkeypatch):
      call_count = 0
      def fake_which(b):
          nonlocal call_count; call_count += 1; return "/usr/bin/claude"
      monkeypatch.setattr("shutil.which", fake_which)
      svc = LLMPreflightService()
      await svc.check("claude")
      svc.invalidate_cache()
      await svc.check("claude")
      assert call_count == 2
  ```

- [ ] Step 3: Run → fail.
  Run: `cd backend && uv run python -m pytest tests/unit/test_llm_preflight_service.py -v`

- [ ] Step 4: Implement `LLMPreflightService` in `backend/app/services/llm_preflight.py`:
  - `__init__()` — `self._cache: dict[str, tuple[float, PreflightResult]] = {}; self._ttl = 60.0`
  - `async check(provider) -> PreflightResult` — if `provider == "auto"`, resolve via `detect_llm_provider()`; if None, return `ok=False, binary_resolved=False, reason="No LLM CLI found on PATH (tried claude, codex)"`. Else `shutil.which(binary)`, version probe via `<binary> --version` with 5s timeout, parse `X.Y.Z` regex, compare to floor (`claude>=2.1`, `codex>=0.118`), set `version_ok` accordingly. Return result. Cache by provider key.
  - `invalidate_cache(provider: str | None = None)` — clears one key or all.

- [ ] Step 5: Run → pass.

- [ ] Step 6: Wire into settings_service: at end of `update_settings()` (after temp-file write commits), call `LLMPreflightService.invalidate_cache()`. Use module-level singleton or pass via DI — pick singleton for simplicity:
  ```python
  # backend/app/services/llm_preflight.py — append
  _preflight_singleton: LLMPreflightService | None = None
  def get_preflight_service() -> LLMPreflightService:
      global _preflight_singleton
      if _preflight_singleton is None:
          _preflight_singleton = LLMPreflightService()
      return _preflight_singleton
  ```

- [ ] Step 7: Add test for settings_service invalidation hook.
  ```python
  # backend/tests/unit/test_settings_service.py — append
  def test_update_settings_invalidates_preflight_cache(settings_service, monkeypatch):
      from app.services.llm_preflight import get_preflight_service
      svc = get_preflight_service()
      svc._cache["claude"] = (9999999999.0, ...)  # planted
      settings_service.update_settings({"llm": {"model": "haiku"}})
      assert svc._cache == {}
  ```

- [ ] Step 8: Commit.
  ```bash
  git add backend/app/services/llm_preflight.py backend/app/services/settings_service.py backend/tests/unit/test_llm_preflight_service.py backend/tests/unit/test_settings_service.py
  git commit -m "feat(llm): add LLMPreflightService with 60s cache + settings invalidation"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/test_llm_preflight_service.py tests/unit/test_settings_service.py -v` — green.
- Manual: in a Python REPL, `await get_preflight_service().check("claude")` returns a result.

---

### T8: `GET /api/v1/llm/status` and `POST /api/v1/llm/recheck`

**Goal:** Expose preflight to frontend.
**Spec refs:** FR-B09, FR-B08a, §8.1, §8.1a

**Files:**
- Create: `backend/app/api/routes/llm.py`
- Modify: `backend/app/api/main.py` (or wherever routers are included) — add `llm.router`
- Create: `backend/tests/integration/test_llm_status_route.py`

**Steps:**

- [ ] Step 1: Write failing test.
  ```python
  # backend/tests/integration/test_llm_status_route.py
  @pytest.mark.asyncio
  async def test_llm_status_returns_preflight(async_client, monkeypatch):
      monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/claude")
      r = await async_client.get("/api/v1/llm/status")
      assert r.status_code == 200
      body = r.json()
      assert body["provider"] in ("claude", "codex", "auto")
      assert "preflight" in body
      assert "ok" in body["preflight"]

  @pytest.mark.asyncio
  async def test_llm_status_resolves_auto_to_binary(async_client, monkeypatch, settings_with_auto):
      # provider='auto' in settings; claude on PATH
      monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/claude" if b == "claude" else None)
      r = await async_client.get("/api/v1/llm/status")
      body = r.json()
      assert body["provider"] == "claude"  # resolved, not "auto"

  @pytest.mark.asyncio
  async def test_llm_status_auto_with_no_binary_returns_auto(async_client, monkeypatch, settings_with_auto):
      monkeypatch.setattr("shutil.which", lambda b: None)
      r = await async_client.get("/api/v1/llm/status")
      assert r.json()["provider"] == "auto"  # nothing resolved
      assert r.json()["preflight"]["binary_resolved"] is False

  @pytest.mark.asyncio
  async def test_llm_recheck_bypasses_cache(async_client, monkeypatch):
      from app.services.llm_preflight import get_preflight_service
      svc = get_preflight_service()
      svc._cache["claude"] = (9999999999.0, MagicMock())
      r = await async_client.post("/api/v1/llm/recheck")
      assert r.status_code == 200
      # cache should be empty after recheck (or repopulated with fresh value)
  ```

- [ ] Step 2: Run → fail (route not found).

- [ ] Step 3: Implement `backend/app/api/routes/llm.py`:
  ```python
  from fastapi import APIRouter, Depends
  from app.config import Settings, get_settings
  from app.services.llm_preflight import get_preflight_service, PreflightResult

  router = APIRouter(prefix="/api/v1/llm", tags=["llm"])

  def _resolve_provider(settings: Settings) -> str | None:
      """Returns the binary name actually being used: 'claude'/'codex' or None."""
      if settings.llm.provider == "auto":
          return detect_llm_provider()
      return settings.llm.provider

  @router.get("/status")
  async def llm_status(settings: Settings = Depends(get_settings)):
      svc = get_preflight_service()
      resolved = _resolve_provider(settings)
      result = await svc.check(settings.llm.provider)  # caches by configured value
      # Per spec §8.1, return the resolved binary so frontend can render
      # "auto (→ claude 2.1.123) ✓" — see FR-F22.
      return {"provider": resolved or settings.llm.provider, "preflight": result.model_dump()}

  @router.post("/recheck")
  async def llm_recheck(settings: Settings = Depends(get_settings)):
      svc = get_preflight_service()
      svc.invalidate_cache()
      resolved = _resolve_provider(settings)
      result = await svc.check(settings.llm.provider)
      return {"provider": resolved or settings.llm.provider, "preflight": result.model_dump()}
  ```

- [ ] Step 4: Wire router into `app/api/main.py`. Match existing router-include pattern.

- [ ] Step 5: Run → pass.

- [ ] Step 6: Commit.
  ```bash
  git add backend/app/api/routes/llm.py backend/app/api/main.py backend/tests/integration/test_llm_status_route.py
  git commit -m "feat(api): add GET /llm/status and POST /llm/recheck"
  ```

**Inline verification:**
- `curl -sf http://localhost:8765/api/v1/llm/status | python3 -m json.tool` (when serve is up later) — returns valid JSON.
- Integration tests green.

---

### T9: Preflight gate in `POST /api/v1/books/:id/summarize`

**Goal:** Block job creation when LLM unavailable; return `400 llm_provider_unavailable`.
**Spec refs:** FR-B10, §8.2, §13.2

**Files:**
- Modify: `backend/app/api/routes/processing.py` (start route, ~line 29-36)
- Create: `backend/tests/integration/test_summarize_route_preflight.py`

**Steps:**

- [ ] Step 1: Write failing test.
  ```python
  # backend/tests/integration/test_summarize_route_preflight.py
  @pytest.mark.asyncio
  async def test_summarize_returns_400_when_no_cli(async_client, seeded_book, monkeypatch):
      monkeypatch.setattr("shutil.which", lambda b: None)
      r = await async_client.post(f"/api/v1/books/{seeded_book.id}/summarize",
                                  json={"preset_name": "practitioner_bullets"})
      assert r.status_code == 400
      body = r.json()
      assert body["error_code"] == "llm_provider_unavailable"
      assert body["detail"]["binary_resolved"] is False
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Edit start route in `processing.py`. After preset validation (existing) and before `ProcessingJob` row creation:
  ```python
  preflight = await get_preflight_service().check(settings.llm.provider)
  if not preflight.ok:
      return JSONResponse(status_code=400, content={
          "error_code": "llm_provider_unavailable",
          "detail": preflight.model_dump(),
      })
  ```

- [ ] Step 4: Run → pass.

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/api/routes/processing.py backend/tests/integration/test_summarize_route_preflight.py
  git commit -m "feat(api): preflight gate on POST /summarize"
  ```

**Inline verification:** integration test green; existing summarize tests still pass.

---

### T10: Alembic migration — `cancel_requested`, `summaries.is_stale`, queue index

**Goal:** Schema additions in one migration (per P5).
**Spec refs:** FR-B13, P2, P5, §9.1

**Files:**
- Create: `backend/app/migrations/versions/<8hex>_v1_6a_processing_job_cancel_and_summary_stale.py`
- Modify: `backend/app/db/models.py` (add columns)

**Steps:**

- [ ] Step 1: Generate migration skeleton.
  Run: `cd backend && uv run alembic -c app/migrations/alembic.ini revision -m "v1_6a processing job cancel and summary stale"`
  Note the generated filename.

- [ ] Step 2: Edit migration body:
  ```python
  def upgrade() -> None:
      with op.batch_alter_table("processing_jobs") as batch:
          batch.add_column(sa.Column("cancel_requested", sa.Boolean(),
                                     nullable=False, server_default=sa.false()))
      with op.batch_alter_table("summaries") as batch:
          batch.add_column(sa.Column("is_stale", sa.Boolean(),
                                     nullable=False, server_default=sa.false()))
      op.create_index(
          "ix_processing_jobs_status_created",
          "processing_jobs", ["status", "created_at"],
          if_not_exists=True,
      )

  def downgrade() -> None:
      op.drop_index("ix_processing_jobs_status_created", "processing_jobs")
      with op.batch_alter_table("summaries") as batch:
          batch.drop_column("is_stale")
      with op.batch_alter_table("processing_jobs") as batch:
          batch.drop_column("cancel_requested")
  ```

- [ ] Step 3: Add columns to ORM models.
  - `backend/app/db/models.py:282-309` (ProcessingJob): `cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.false())`.
  - `backend/app/db/models.py:350-383` (Summary): `is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.false(), index=False)`.

- [ ] Step 4: Run migration up, then down, then up.
  Run: `cd backend && uv run alembic -c app/migrations/alembic.ini upgrade head && uv run alembic -c app/migrations/alembic.ini downgrade -1 && uv run alembic -c app/migrations/alembic.ini upgrade head`
  Expected: all three succeed.

- [ ] Step 5: Verify schema.
  Run: `sqlite3 ~/Library/Application\ Support/bookcompanion/library.db ".schema processing_jobs" | grep cancel_requested`
  Expected: column present.
  Run: `sqlite3 ~/Library/Application\ Support/bookcompanion/library.db ".schema summaries" | grep is_stale`
  Expected: column present.

- [ ] Step 6: Run unit suite — model changes shouldn't regress.
  Run: `cd backend && uv run python -m pytest tests/unit/ -v`

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/migrations/versions/ backend/app/db/models.py
  git commit -m "feat(db): add cancel_requested, summaries.is_stale, queue index"
  ```

**Inline verification:**
- Schema grep returns both columns + index.
- `pytest` green.

---

### T11a: `JobQueueWorker` scaffold + lifespan + extract `_run_processing`

**Goal:** Stand up the worker class and its lifespan integration; move `_run_processing()` body out of the API route into the worker (no atomic-promotion logic yet — that's T11b). After this task the worker is mounted but doesn't promote anything; the API route still creates `PENDING` rows.

**Spec refs:** FR-B11a, P13, FR-B23 (logging hooks)

**Files:**
- Create: `backend/app/services/job_queue_worker.py` (skeleton class)
- Create: `backend/tests/unit/test_job_queue_worker.py` (lifespan + scaffold-level tests)
- Modify: `backend/app/api/main.py` (lifespan integration)
- Modify: `backend/app/api/routes/processing.py` (extract `_run_processing` to a method on worker; route now only creates `PENDING` row + emits `job_queued`)

**Steps:**

- [ ] Step 1: Write failing tests for scaffold behavior.
  ```python
  # backend/tests/unit/test_job_queue_worker.py
  @pytest.mark.asyncio
  async def test_worker_starts_and_stops_cleanly(session_factory, event_bus, settings):
      worker = JobQueueWorker(session_factory, event_bus, settings)
      await worker.start()
      assert worker._task is not None and not worker._task.done()
      await worker.stop()
      assert worker._task.done()

  @pytest.mark.asyncio
  async def test_worker_logs_started_and_stopped(caplog, ...):
      worker = JobQueueWorker(...)
      await worker.start()
      await worker.stop()
      assert any("queue_worker_started" in r.message for r in caplog.records)
      assert any("queue_worker_stopped" in r.message for r in caplog.records)

  @pytest.mark.asyncio
  async def test_start_summarize_route_creates_pending_only(async_client, seeded_book):
      r = await async_client.post(f"/api/v1/books/{seeded_book.id}/summarize",
                                  json={"preset_name": "practitioner_bullets"})
      assert r.status_code == 200
      job = await db.execute(select(ProcessingJob).where(book_id=seeded_book.id))
      job = job.scalar_one()
      assert job.status == "PENDING"  # not RUNNING; promotion is worker's job
  ```

- [ ] Step 2: Run → fail (no worker class).

- [ ] Step 3: Implement scaffold:
  ```python
  # backend/app/services/job_queue_worker.py
  class JobQueueWorker:
      def __init__(self, session_factory, event_bus, settings):
          self._session_factory = session_factory
          self._event_bus = event_bus
          self._settings = settings
          self._task: asyncio.Task | None = None
          self._stopping = asyncio.Event()

      async def start(self):
          self._task = asyncio.create_task(self._run_loop())
          log.info("queue_worker_started")

      async def stop(self):
          self._stopping.set()
          if self._task:
              self._task.cancel()
              try: await self._task
              except asyncio.CancelledError: pass
          log.info("queue_worker_stopped")

      async def _run_loop(self):
          while not self._stopping.is_set():
              try: await self._tick()
              except Exception: log.exception("queue_worker_tick_failed")
              await asyncio.sleep(2.0)

      async def _tick(self):
          # Stub for T11a — no promotion yet. T11b adds atomic SQL.
          return

      async def _run_processing(self, job, provider):
          # Body moved verbatim from processing.py:138-348, with `provider` injected.
          ...
  ```

- [ ] Step 4: Modify `app/main.py` lifespan — start/stop worker, store on `app.state.job_queue_worker`.

- [ ] Step 5: Modify `processing.py` start route — replace the `asyncio.create_task(_run_processing())` launch (line ~348) with `ProcessingJob{status=PENDING}` row creation + `event_bus.publish(... "job_queued" ...)`. Move `_run_processing()` body to `JobQueueWorker._run_processing` method. Delete the route-level function.

- [ ] Step 6: Run scaffold tests → pass. Run full suite → pre-existing summarize tests likely fail (they assert immediate RUNNING). Update those to await PENDING and explicitly call `worker._tick()` in test fixtures, OR mark as integration tests covered in T11b.

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/services/job_queue_worker.py backend/app/api/main.py backend/app/api/routes/processing.py backend/tests/unit/test_job_queue_worker.py
  git commit -m "feat(queue): JobQueueWorker scaffold + lifespan + extract _run_processing"
  ```

**Inline verification:**
- Scaffold tests green; lifespan starts/stops worker without errors.
- `POST /summarize` creates a PENDING row but no RUNNING transition (manual: SSE shows only `job_queued`).

---

### T11b: Atomic promotion + per-job provider re-instantiation

**Goal:** Worker promotes oldest PENDING to RUNNING via atomic SQL when no RUNNING exists; re-instantiates `LLMProvider` per promoted job; emits `job_promoted` then proceeds into `_run_processing` in the same coroutine (preserves SSE FIFO between `job_promoted` and `processing_started`).

**Spec refs:** FR-B11, FR-B12, P8, D18, FR-B23 (job_promoted log), §6.4 invariant ordering

**Files:**
- Modify: `backend/app/services/job_queue_worker.py` (replace `_tick` stub with atomic-promotion + provider re-instantiation)
- Modify: `backend/tests/unit/test_job_queue_worker.py` (promotion + concurrency tests)

**Steps:**

- [ ] Step 1: Write failing tests.
  ```python
  # backend/tests/unit/test_job_queue_worker.py — append
  @pytest.mark.asyncio
  async def test_worker_promotes_oldest_pending(seeded_jobs):
      # Seed: 2 PENDING jobs (job_id=1 older), 0 RUNNING
      worker = JobQueueWorker(...)
      await worker._tick()
      job1 = await db.get(ProcessingJob, 1)
      job2 = await db.get(ProcessingJob, 2)
      assert job1.status == "RUNNING"
      assert job2.status == "PENDING"

  @pytest.mark.asyncio
  async def test_worker_does_not_promote_when_running_exists(seeded_jobs_with_running):
      worker = JobQueueWorker(...)
      await worker._tick()
      pending = await db.execute(select(ProcessingJob).where(status="PENDING"))
      assert len(pending.scalars().all()) == 1  # unchanged

  @pytest.mark.asyncio
  async def test_atomic_promotion_no_double_promote(...):
      # Two workers, same DB, gather two _tick() calls
      worker1, worker2 = JobQueueWorker(...), JobQueueWorker(...)
      await asyncio.gather(worker1._tick(), worker2._tick())
      running_count = ...
      assert running_count == 1
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Replace `_tick` stub with full atomic-promotion logic:
  ```python
  # backend/app/services/job_queue_worker.py — replace _tick()
      async def _tick(self):
          async with self._session_factory() as db:
              # Atomic promotion (FR-B11)
              now = datetime.utcnow()
              result = await db.execute(text("""
                  UPDATE processing_jobs SET status='RUNNING', started_at=:now
                  WHERE id = (
                      SELECT id FROM processing_jobs
                      WHERE status='PENDING' AND NOT EXISTS (
                          SELECT 1 FROM processing_jobs WHERE status='RUNNING'
                      )
                      ORDER BY created_at ASC LIMIT 1
                  )
              """), {"now": now})
              await db.commit()
              if result.rowcount != 1:
                  return
              # Re-fetch promoted job; emit job_promoted; call _run_processing inline
              promoted = ...  # SELECT WHERE id matches
              await self._event_bus.publish(promoted.id, "job_promoted",
                  {"job_id": promoted.id, "book_id": promoted.book_id,
                   "last_event_at": now.isoformat()})
              # Re-instantiate provider per-job (FR-B12, P8)
              provider = create_llm_provider(
                  self._settings.llm.provider,
                  config_dir=self._settings.llm.config_dir,
                  default_model=self._settings.llm.model,
                  default_timeout=self._settings.llm.timeout_seconds,
                  max_budget_usd=self._settings.llm.max_budget_usd,
              )
              await self._run_processing(promoted, provider)

      async def _run_processing(self, job, provider):
          # Moved from processing.py — original body, with per-section cancel-watch
          # See T12 for cancel integration.
          ...
  ```

- [ ] Step 4: Run unit + integration suite — must pass.
  Run: `cd backend && uv run python -m pytest tests/ -v`
  Expected: green. Any pre-existing test that asserts "background task starts immediately on POST /summarize" needs updating to assert "PENDING job created → worker promotes within 2s". Update tests accordingly.

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/services/job_queue_worker.py backend/tests/unit/test_job_queue_worker.py
  git commit -m "feat(queue): atomic promotion + per-job provider re-instantiation"
  ```

**Inline verification:**
- Unit tests green.
- Manual: start serve, kick off two summarize requests, observe SSE `job_queued` then `job_promoted` for first, then for second after first completes.

---

### T12: Cancel-RUNNING flow with SIGTERM/SIGKILL + `job_cancelling` SSE

**Goal:** RUNNING jobs cancellable; current section fails, prior sections preserved.
**Spec refs:** FR-B14, FR-B15, FR-B15a, FR-B15b, NFR-03, §6.4, §8.3

**Files:**
- Modify: `backend/app/api/routes/processing.py` (cancel route at `:415-438`)
- Modify: `backend/app/services/job_queue_worker.py` (add cancel watcher to `_run_processing`)
- Create: `backend/tests/unit/test_processing_cancel.py`

**Steps:**

- [ ] Step 1: Write failing tests for both PENDING and RUNNING cancel paths.
  ```python
  # backend/tests/unit/test_processing_cancel.py
  @pytest.mark.asyncio
  async def test_cancel_pending_atomic_delete(seeded_pending_job, async_client):
      r = await async_client.post(f"/api/v1/processing/{seeded_pending_job.id}/cancel")
      assert r.status_code == 200
      assert r.json()["status"] == "PENDING_REMOVED"
      # row is gone
      assert await db.get(ProcessingJob, seeded_pending_job.id) is None

  @pytest.mark.asyncio
  async def test_cancel_running_sets_flag(seeded_running_job, async_client, mock_event_bus):
      r = await async_client.post(f"/api/v1/processing/{seeded_running_job.id}/cancel")
      assert r.status_code == 200
      assert r.json()["status"] == "CANCEL_REQUESTED"
      job = await db.get(ProcessingJob, seeded_running_job.id)
      assert job.cancel_requested is True
      mock_event_bus.publish.assert_any_call(..., "job_cancelling", ...)

  @pytest.mark.asyncio
  async def test_cancel_already_done_returns_status(seeded_completed_job, async_client):
      r = await async_client.post(f"/api/v1/processing/{seeded_completed_job.id}/cancel")
      assert r.status_code == 200
      assert r.json()["status"] == "ALREADY_DONE"

  @pytest.mark.asyncio
  async def test_cancel_missing_returns_404(async_client):
      r = await async_client.post("/api/v1/processing/99999/cancel")
      assert r.status_code == 404

  @pytest.mark.asyncio
  async def test_run_processing_sigterm_on_cancel_event():
      # Mock provider that hangs; set cancel_event mid-flight; assert proc.terminate() called
      ...
      assert mock_proc.terminate.called

  @pytest.mark.asyncio
  async def test_run_processing_sigkill_after_5s_timeout():
      # Mock proc.terminate() that doesn't exit; assert proc.kill() called after 5s
      ...

  @pytest.mark.asyncio
  async def test_fail_fast_on_2_consecutive_cli_disappeared():
      # First two sections raise SubprocessNotFoundError → job FAILED with reason="cli_disappeared"
      ...
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement cancel route per spec §8.3:
  ```python
  @router.post("/{job_id}/cancel")
  async def cancel(job_id: int, db: AsyncSession = Depends(get_db)):
      result = await db.execute(text(
          "DELETE FROM processing_jobs WHERE id=:id AND status='PENDING'"
      ), {"id": job_id})
      await db.commit()
      if result.rowcount == 1:
          return {"job_id": job_id, "status": "PENDING_REMOVED"}
      job = await db.get(ProcessingJob, job_id)
      if job is None:
          raise HTTPException(404)
      if job.status == "RUNNING":
          job.cancel_requested = True
          await db.commit()
          await event_bus.publish(job_id, "job_cancelling",
              {"job_id": job_id, "book_id": job.book_id,
               "last_event_at": datetime.utcnow().isoformat()})
          return {"job_id": job_id, "status": "CANCEL_REQUESTED"}
      return {"job_id": job_id, "status": "ALREADY_DONE"}
  ```

- [ ] Step 4: Implement cancel-watcher in `JobQueueWorker._run_processing` per §6.4 pseudocode (poll task + per-section race + SIGTERM + 5s SIGKILL + reap). Add `_consecutive_cli_disappeared_count` tracker for FR-B15b.

- [ ] Step 5: **Extend `processing_failed` SSE payload with `reason: 'cancelled' | 'cli_disappeared' | 'error'` field** (per spec §8.6).
  - Locate every `event_bus.publish(... "processing_failed" ...)` call site (originally 1 in `_run_processing`, possibly more after T11b moves). For each, set `reason` based on context:
    - cancel finalization branch → `reason="cancelled"`
    - 2-consecutive-CLI-disappeared branch → `reason="cli_disappeared"`
    - generic exception branch → `reason="error"`
  - Add a unit test asserting each branch emits the right `reason`:
    ```python
    @pytest.mark.asyncio
    async def test_processing_failed_reason_cancelled(...):
        # trigger cancel mid-flight
        events = await capture_events(...)
        failed = [e for e in events if e["event"] == "processing_failed"][0]
        assert failed["data"]["reason"] == "cancelled"

    @pytest.mark.asyncio
    async def test_processing_failed_reason_cli_disappeared(...):
        # mock 2 consecutive SubprocessNotFoundError
        ...
        assert failed["data"]["reason"] == "cli_disappeared"

    @pytest.mark.asyncio
    async def test_processing_failed_reason_error(...):
        # generic LLM error
        ...
        assert failed["data"]["reason"] == "error"
    ```
  - Update `backend/tests/integration/test_summarize_sse_events.py` to assert `reason` present on terminal failure events.

- [ ] Step 6: Run → pass.

- [ ] Step 7: Commit.
  ```bash
  git add backend/app/api/routes/processing.py backend/app/services/job_queue_worker.py backend/tests/unit/test_processing_cancel.py
  git commit -m "feat(queue): cancel route + SIGTERM/SIGKILL flow + cli_disappeared abort"
  ```

**Inline verification:**
- All test paths green.
- Manual: kick off summarize, hit cancel route via curl mid-job, observe SIGTERM in dev logs, job ends FAILED with `error_message="cancelled"`.

---

### T13: `GET /api/v1/processing/jobs?status=PENDING,RUNNING` seed endpoint

**Goal:** Frontend store can hydrate before SSE connects.
**Spec refs:** FR-B14a, §8.3a, FR-F19b

**Files:**
- Modify: `backend/app/api/routes/processing.py`
- Create: `backend/tests/integration/test_processing_jobs_list.py`

**Steps:**

- [ ] Step 1: Write failing test.
  ```python
  @pytest.mark.asyncio
  async def test_jobs_list_returns_active_with_queue_position(seeded_running_and_pending, async_client):
      r = await async_client.get("/api/v1/processing/jobs?status=PENDING,RUNNING")
      assert r.status_code == 200
      jobs = r.json()["jobs"]
      assert jobs[0]["status"] == "RUNNING"
      assert jobs[0]["queue_position"] == 0
      assert jobs[1]["status"] == "PENDING"
      assert jobs[1]["queue_position"] == 1
      # Includes book_title joined from books table
      assert jobs[0]["book_title"]
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement route per §8.3a. Order by `created_at ASC`. Compute `queue_position`: 0 for RUNNING, 1..N for PENDING in created_at order. Join `books` for title. Include `progress` blob from `ProcessingJob.progress` JSON column (pre-existing).

- [ ] Step 4: Run → pass.

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/api/routes/processing.py backend/tests/integration/test_processing_jobs_list.py
  git commit -m "feat(api): GET /processing/jobs seed endpoint"
  ```

**Inline verification:**
- `curl -sf "http://localhost:8765/api/v1/processing/jobs?status=PENDING,RUNNING" | python3 -m json.tool` — well-formed.

---

### T14: Add `last_event_at` to all SSE events; emit `job_queued` post-commit

**Goal:** Frontend can reconcile seed vs. live events; events are timestamped.
**Spec refs:** FR-B16, FR-B17, P19, §8.6

**Files:**
- Modify: `backend/app/api/sse.py` (or wherever events are emitted)
- Modify: `backend/app/services/job_queue_worker.py` (emit `job_promoted` from worker; ensure `processing_started` follows in same coroutine)
- Modify: `backend/app/api/routes/processing.py` (emit `job_queued` after commit)
- Modify: `backend/tests/integration/test_summarize_sse_events.py` (existing) — add assertions for new events

**Steps:**

- [ ] Step 1: Write failing test that asserts every event payload contains `last_event_at`.
  ```python
  @pytest.mark.asyncio
  async def test_all_events_include_last_event_at(captured_sse_events):
      for event in captured_sse_events:
          assert "last_event_at" in event["data"]
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Update `EventBus.publish` (or call sites) to inject `last_event_at = datetime.utcnow().isoformat()` if absent. Cleanest: enforce at the publish-helper layer.

- [ ] Step 4: Run → pass.

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/api/sse.py backend/app/services/job_queue_worker.py backend/app/api/routes/processing.py backend/tests/integration/test_summarize_sse_events.py
  git commit -m "feat(sse): emit last_event_at on all events; add job_queued/job_promoted"
  ```

**Inline verification:** integration test green.

---

### T15: `GET /api/v1/books/:id/sections/edit-impact` endpoint

**Goal:** Frontend computes invalidation impact before mutating.
**Spec refs:** FR-B18, P1, P2, P3, §8.4

**Files:**
- Modify: `backend/app/api/routes/sections.py`
- Create: `backend/tests/integration/test_section_edit_impact.py`

**Steps:**

- [ ] Step 1: Write failing test.
  ```python
  @pytest.mark.asyncio
  async def test_edit_impact_with_summarized_sections(seeded_summarized_book, async_client):
      # 5 sections, 2 summarized; book has default_summary_id
      ids = [s.id for s in seeded_summarized_book.sections[:2]]
      r = await async_client.get(f"/api/v1/books/{seeded_summarized_book.id}/sections/edit-impact",
                                 params={"section_ids": ",".join(map(str, ids))})
      body = r.json()
      assert sorted(body["summaries_to_invalidate"]) == sorted([summary.id for summary in summaries_for_those_sections])
      assert body["invalidate_book_summary"] is True
      assert body["summarized_section_count"] == 2

  @pytest.mark.asyncio
  async def test_edit_impact_no_summaries(seeded_unsummarized_book, async_client):
      ids = [s.id for s in seeded_unsummarized_book.sections[:2]]
      r = await async_client.get(...)
      assert r.json()["summarized_section_count"] == 0
      assert r.json()["invalidate_book_summary"] is False
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement route. Query: `SELECT id FROM summaries WHERE content_type='section' AND content_id IN :ids AND is_stale = 0`. `invalidate_book_summary = (count > 0 AND book.default_summary_id IS NOT NULL)`.

- [ ] Step 4: Run → pass.

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/api/routes/sections.py backend/tests/integration/test_section_edit_impact.py
  git commit -m "feat(api): GET sections/edit-impact endpoint"
  ```

**Inline verification:** integration test green.

---

### T16: `GET /split-preview` endpoint (3 modes)

**Goal:** Frontend renders heading/paragraph/char split candidates without mutating.
**Spec refs:** FR-B18a, §8.5

**Files:**
- Modify: `backend/app/api/routes/sections.py`
- Modify: `backend/app/services/section_edit_service.py` (expose preview helpers if not already)
- Create: `backend/tests/integration/test_split_preview_route.py`

**Steps:**

- [ ] Step 1: Write failing tests for all 3 modes.
  ```python
  async def test_split_preview_heading_mode(seeded_section_with_headings, async_client):
      r = await async_client.get(f"/api/v1/books/{book_id}/sections/{section_id}/split-preview",
                                 params={"mode": "heading"})
      candidates = r.json()["candidates"]
      assert len(candidates) >= 2
      assert all("title" in c and "char_count" in c and "first_line" in c for c in candidates)

  async def test_split_preview_paragraph_mode(...):
      ...

  async def test_split_preview_char_mode_validates_position(...):
      r = await async_client.get(..., params={"mode": "char", "position": 100})
      assert len(r.json()["candidates"]) == 2
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement route. Heading mode uses `section_edit_service.detect_headings(section)` (already exists at `:279`); paragraph mode splits on `\n\n` boundaries; char mode validates position is non-whitespace boundary.

- [ ] Step 4: Run → pass.

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/api/routes/sections.py backend/app/services/section_edit_service.py backend/tests/integration/test_split_preview_route.py
  git commit -m "feat(api): GET sections/split-preview with 3 modes"
  ```

**Inline verification:** all 3 mode tests green.

---

### T17: Auto-stale + book-summary-invalidation on section-edit routes

**Goal:** Existing edit routes auto-mark affected summaries stale and revert book status.
**Spec refs:** FR-B19, FR-B20, FR-B21, P2, P3, P4

**Files:**
- Modify: `backend/app/api/routes/sections.py` (merge, split, PATCH, DELETE)
- Create: `backend/tests/integration/test_section_edit_blocks_during_job.py`
- Modify: `backend/tests/integration/test_section_edit_db.py` (existing) — add stale-marking assertions

**Steps:**

- [ ] Step 1: Write failing tests.
  ```python
  async def test_merge_marks_summaries_stale(seeded_summarized_book, async_client):
      ids = [seeded_summarized_book.sections[0].id, seeded_summarized_book.sections[1].id]
      await async_client.post(f"/api/v1/books/{book_id}/sections/merge", json={"section_ids": ids})
      summaries = await db.execute(select(Summary).where(...))
      affected = [s for s in summaries.scalars() if s.content_id in ids]
      assert all(s.is_stale for s in affected)

  async def test_merge_invalidates_book_summary_and_status(seeded_summarized_book, async_client):
      # Book has default_summary_id and status COMPLETED
      await async_client.post(...)
      book = await db.get(Book, book_id)
      assert book.default_summary_id is None
      assert book.status == BookStatus.PARSED

  async def test_edit_routes_409_when_active_job(seeded_book_with_running_job, async_client):
      r = await async_client.post(f"/api/v1/books/{book_id}/sections/merge", json=...)
      assert r.status_code == 409

  async def test_patch_rejects_empty_title(async_client, seeded_section):
      r = await async_client.patch(f"/api/v1/books/{book_id}/sections/{section_id}",
                                   json={"title": "   "})
      assert r.status_code == 400
      assert r.json()["error"] == "title_required"

  async def test_patch_rejects_too_long_title(async_client, seeded_section):
      r = await async_client.patch(..., json={"title": "x" * 501})
      assert r.status_code == 400
      assert r.json()["error"] == "title_too_long"
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Modify each edit route to:
  1. **Pre-check active job** — `SELECT 1 FROM processing_jobs WHERE book_id=:id AND status IN ('PENDING','RUNNING')`. If exists → 409.
  2. **Pre-compute affected sections** (the section_ids about to lose content).
  3. Within the same transaction as the mutation: `UPDATE summaries SET is_stale=1 WHERE content_type='section' AND content_id IN :ids AND is_stale=0`.
  4. If any stale-marked rows AND `book.default_summary_id IS NOT NULL`: `UPDATE books SET default_summary_id=NULL, status='PARSED' WHERE id=:book_id AND status='COMPLETED'`.
  5. PATCH route: validate title length 1–500 after `.strip()`; reject empty/long with 400.

- [ ] Step 4: Run all tests → pass.
  Run: `cd backend && uv run python -m pytest tests/integration/test_section_edit_db.py tests/integration/test_section_edit_blocks_during_job.py tests/integration/test_section_edit_impact.py -v`

- [ ] Step 5: Commit.
  ```bash
  git add backend/app/api/routes/sections.py backend/tests/integration/test_section_edit_blocks_during_job.py backend/tests/integration/test_section_edit_db.py
  git commit -m "feat(sections): auto-stale summaries; revert COMPLETED→PARSED; 409 on active job; title validation"
  ```

**Inline verification:** all 5 test scenarios green; existing section-edit tests still pass.

---

### T18: Backend phase verification gate

**Goal:** All backend phases done; entire backend suite green; lint clean.
**Spec refs:** §13.5

**Files:** none modified — verification only.

**Steps:**

- [ ] Step 1: Run full backend test suite.
  Run: `cd backend && uv run python -m pytest tests/ -v`
  Expected: all green; no skips beyond `integration_llm` markers.

- [ ] Step 2: Run lint + format check.
  Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
  Expected: clean.

- [ ] Step 3: Run grep regression gate (backend only).
  Run: `! grep -rn 'cli_command' backend/app/ | grep -v '/static/' | grep -v '.pyc'`
  Expected: empty output (command exits 0 only when grep finds nothing).

- [ ] Step 4: Manual API smoke.
  - Start: `cd backend && uv run bookcompanion serve --port 8765 &`
  - `curl -sf http://localhost:8765/api/v1/health` → 200
  - `curl -sf http://localhost:8765/api/v1/llm/status | python3 -m json.tool` → valid payload
  - Trigger summarize on a seeded book → observe SSE `job_queued` then `job_promoted` then section events
  - `kill $(lsof -ti:8765)`

- [ ] Step 5: No code commit; tag verification result in this plan's Review Log.

**Inline verification:**
- All backend tests green; ruff clean; grep gate empty; manual smoke passes.

---

### T19: Frontend — XHR upload + `<UploadFileCard>`

**Goal:** Step 1 shows determinate upload bar + indeterminate parse spinner.
**Spec refs:** FR-F01, FR-F02, FR-F03, D12, §6.5

**Files:**
- Modify: `frontend/src/api/client.ts:93-106`
- Create: `frontend/src/components/upload/UploadFileCard.vue`
- Create: `frontend/src/components/upload/__tests__/UploadFileCard.spec.ts`
- Modify: `frontend/src/components/upload/UploadWizard.vue` (Step 1 wires UploadFileCard)

**Steps:**

- [ ] Step 1: Write failing component test.
  ```typescript
  // frontend/src/components/upload/__tests__/UploadFileCard.spec.ts
  import { mount } from '@vue/test-utils'
  import UploadFileCard from '../UploadFileCard.vue'

  describe('UploadFileCard', () => {
    it('renders determinate progress bar driven by uploadProgress prop', async () => {
      const wrapper = mount(UploadFileCard, {
        props: { file: new File(['x'], 'book.epub'), phase: 'uploading', uploadProgress: 42 }
      })
      const bar = wrapper.find('[data-test="upload-progress-bar"]')
      expect(bar.attributes('style')).toContain('42%')
    })

    it('shows indeterminate spinner with parse text in parse phase', () => {
      const wrapper = mount(UploadFileCard, { props: { ..., phase: 'parsing' } })
      expect(wrapper.text()).toContain('Parsing')
      expect(wrapper.find('[data-test="parse-spinner"]').exists()).toBe(true)
    })

    it('Cancel button enabled in upload phase, disabled in parse phase', () => {
      const wrapper = mount(UploadFileCard, { props: { phase: 'uploading' } })
      expect(wrapper.find('[data-test="cancel-btn"]').attributes('disabled')).toBeUndefined()
      const parsing = mount(UploadFileCard, { props: { phase: 'parsing' } })
      expect(parsing.find('[data-test="cancel-btn"]').attributes('disabled')).toBeDefined()
    })

    it('emits cancel on button click during upload', async () => {
      const wrapper = mount(UploadFileCard, { props: { phase: 'uploading' } })
      await wrapper.find('[data-test="cancel-btn"]').trigger('click')
      expect(wrapper.emitted('cancel')).toBeTruthy()
    })

    it('renders error state with Retry button', () => {
      const wrapper = mount(UploadFileCard, { props: { phase: 'error', error: 'Upload failed' } })
      expect(wrapper.text()).toContain('Upload failed')
      expect(wrapper.find('[data-test="retry-btn"]').exists()).toBe(true)
    })
  })
  ```

- [ ] Step 2: Run → fail.
  Run: `cd frontend && npm run test:unit -- UploadFileCard`
  Expected: file not found / fail.

- [ ] Step 3: Implement `UploadFileCard.vue` per §6.5. Two-phase state machine via `phase: 'uploading' | 'parsing' | 'error' | 'success'` prop. Determinate bar uses `uploadProgress` prop (0-100). `data-test` attrs for tests.

- [ ] Step 4: Modify `frontend/src/api/client.ts:93-106` — add `uploadBook(file, onProgress)`:
  ```typescript
  export function uploadBook(file: File, onProgress: (pct: number) => void, signal?: AbortSignal): Promise<BookData> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/v1/books/upload')
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round(100 * e.loaded / e.total))
      }
      xhr.onload = () => xhr.status >= 200 && xhr.status < 300
        ? resolve(JSON.parse(xhr.responseText))
        : reject(new ApiError(xhr.status, xhr.responseText))
      xhr.onerror = () => reject(new ApiError(0, 'Network error'))
      signal?.addEventListener('abort', () => xhr.abort())
      const fd = new FormData(); fd.append('file', file)
      xhr.send(fd)
    })
  }
  ```

- [ ] Step 5: Modify `UploadWizard.vue` Step 1 — replace inline `uploadBook(file)` with `UploadFileCard` driven by `phase` ref + `uploadProgress` ref. On `cancel` event → `controller.abort()`. On `retry` → reset state.

- [ ] Step 6: Run unit tests → pass. Run type-check.
  Run: `cd frontend && npm run test:unit && npm run type-check`

- [ ] Step 7: Commit.
  ```bash
  git add frontend/src/components/upload/UploadFileCard.vue frontend/src/components/upload/__tests__/UploadFileCard.spec.ts frontend/src/api/client.ts frontend/src/components/upload/UploadWizard.vue
  git commit -m "feat(upload): XHR-driven UploadFileCard with determinate + indeterminate phases"
  ```

**Inline verification:**
- `npm run test:unit -- UploadFileCard` — green.
- `npm run type-check` — clean.

---

### T20: `<StructureEditor>` — base table + per-row controls

**Goal:** Replace read-only StructureReview with editable table (rename, set-type, char count, delete with undo).
**Spec refs:** FR-F04, FR-F05, FR-F07, FR-F09, FR-F26, FR-F27

**Files:**
- Create: `frontend/src/components/upload/StructureEditor.vue`
- Create: `frontend/src/components/upload/__tests__/StructureEditor.spec.ts`
- Delete: `frontend/src/components/upload/StructureReview.vue`
- Modify: `frontend/src/components/upload/UploadWizard.vue` Step 2

**Steps:**

- [ ] Step 1: Write failing tests.
  ```typescript
  describe('StructureEditor', () => {
    it('renders one row per section with char_count', () => {...})
    it('inline rename: click title → input → blur saves via PATCH', async () => {...})
    it('rename rejects empty title with inline error', async () => {...})
    it('rename rejects >500 chars', async () => {...})
    it('per-row delete: row fades, undo toast appears', async () => {...})
    it('delete is deferred until undo timeout (5s)', async () => {
      vi.useFakeTimers()
      // click delete; assert no API call yet
      vi.advanceTimersByTime(5000)
      // assert API call fires
    })
    it('disables delete when only 1 section remains', () => {...})
    it('beforeunload guard fires when pending deletes exist', () => {...})
  })
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement `StructureEditor.vue` (table only, no drag yet, no multi-select yet — those land in T21+T22). Props: `bookId`, `mode`, `sections`. Local state: `pendingDeletes: Map<id, timeout>`, `editingTitleId`, `error`. Use `useRouter` `beforeRouteLeave` + `beforeunload` for FR-F27 guard.

- [ ] Step 4: Wire `UploadWizard.vue` Step 2 to use `<StructureEditor :mode="'wizard'" :sections="..." :book-id="...">`.

- [ ] Step 5: Delete `StructureReview.vue` and update any imports.

- [ ] Step 6: Run tests → pass.

- [ ] Step 7: Commit.
  ```bash
  git add frontend/src/components/upload/StructureEditor.vue frontend/src/components/upload/__tests__/StructureEditor.spec.ts frontend/src/components/upload/UploadWizard.vue
  git rm frontend/src/components/upload/StructureReview.vue
  git commit -m "feat(structure): StructureEditor with rename, delete-with-undo, beforeunload guard"
  ```

**Inline verification:** unit tests green; type-check clean.

---

### T21: `<StructureEditor>` — drag-reorder + keyboard alternative + multi-select toolbar

**Goal:** Drag handle reorder; multi-select for merge / bulk delete / bulk set-type.
**Spec refs:** FR-F06, FR-F08, FR-F09, FR-F25, NFR-02, NFR-05

**Files:**
- Modify: `frontend/src/components/upload/StructureEditor.vue`
- Modify: `frontend/src/components/upload/__tests__/StructureEditor.spec.ts`

**Steps:**

- [ ] Step 1: Add tests.
  ```typescript
  it('HTML5 drag swaps order optimistically and POSTs /move', async () => {...})
  it('keyboard: focus drag handle, ArrowDown moves row, Enter commits', async () => {...})
  it('Escape after keyboard reorder reverts', async () => {...})
  it('multi-select: checkbox columns, toolbar appears with ≥1 selected', async () => {...})
  it('bulk delete disabled when all rows selected', () => {...})
  it('merge button disabled when <2 selected; opens dialog with first title prefilled', async () => {...})
  it('drag failure: row snaps back, toast error', async () => {...})
  it('drag re-trigger queues per-row; stale response dropped', async () => {...})
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Add `draggable=true` + `@dragstart/@dragover/@drop` handlers on row. On drop → optimistic swap → `POST /move` with `client_request_id` header. Per-row pending-move queue (FR-F25). On error → snap back + `useUiStore().showToast(err, 'error')`.

- [ ] Step 4: Add keyboard handler on `[data-test="drag-handle"]`: ArrowUp/Down adjust local index, Enter commits, Escape reverts. Use `aria-live="polite"` on list container (NFR-05). `aria-label` on handle.

- [ ] Step 5: Add multi-select: checkbox column + computed `selectedIds: Set<number>`. Toolbar component (inline) with Merge / Bulk delete / Bulk set-type buttons. Merge opens dialog (inline `<dialog>` element or simple modal) with title input, default = `sections.find(s => s.id === sortedSelectedIds[0]).title`.

- [ ] Step 6: Run tests → pass.

- [ ] Step 7: Commit.
  ```bash
  git commit -m "feat(structure): drag-reorder with keyboard a11y + multi-select toolbar"
  ```

**Inline verification:** all StructureEditor.spec.ts cases green.

---

### T22: `<SplitModal>` — 3-mode split with preview

**Goal:** Click split → choose mode → preview candidates → confirm.
**Spec refs:** FR-F10, D10, §8.5

**Files:**
- Create: `frontend/src/components/upload/SplitModal.vue`
- Create: `frontend/src/components/upload/__tests__/SplitModal.spec.ts`
- Modify: `frontend/src/components/upload/StructureEditor.vue` (wire split button → opens SplitModal)

**Steps:**

- [ ] Step 1: Write failing tests.
  ```typescript
  describe('SplitModal', () => {
    it('mounts with 3 tabs: Auto-detect headings, At paragraph, At cursor', () => {...})
    it('Auto-detect tab fetches /split-preview?mode=heading and renders candidates', async () => {...})
    it('At paragraph tab: click on \\n\\n boundary marks split point', async () => {...})
    it('At cursor tab: textarea selection sets char position', async () => {...})
    it('Confirm posts to /split with correct mode + position', async () => {...})
    it('Cancel closes modal, no API call', async () => {...})
  })
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement `SplitModal.vue`. Tabs via `currentTab: 'heading' | 'paragraph' | 'char'`. Heading tab: fetch on mount. Render candidates as cards: title, char_count, first_line. Paragraph tab: rendered content with `\n\n` markers as click targets. Char tab: textarea (read-only with selection enabled) + char-position display.

- [ ] Step 4: Modify `StructureEditor.vue` row split action to open SplitModal. On confirm → close + emit refresh.

- [ ] Step 5: Run → pass.

- [ ] Step 6: Commit.
  ```bash
  git add frontend/src/components/upload/SplitModal.vue frontend/src/components/upload/__tests__/SplitModal.spec.ts frontend/src/components/upload/StructureEditor.vue
  git commit -m "feat(structure): SplitModal with 3-mode preview"
  ```

**Inline verification:** SplitModal.spec.ts green.

---

### T23: `EditStructureView` route + `ConfirmDialog` + edit-impact wiring

**Goal:** `/books/:id/edit-structure` reuses StructureEditor in post-summary mode with invalidation confirmation.
**Spec refs:** FR-F11, FR-F28, D9, D14, D15, §5.2

**Files:**
- Create: `frontend/src/views/EditStructureView.vue`
- Create: `frontend/src/components/common/ConfirmDialog.vue`
- Modify: `frontend/src/router/index.ts` (add route)
- Modify: `frontend/src/views/BookDetailView.vue` (add Edit Structure button)
- Modify: `frontend/src/api/sections.ts` (or wherever) — add `getEditImpact(bookId, sectionIds)`

**Steps:**

- [ ] Step 1: Write failing tests.
  ```typescript
  // EditStructureView.spec.ts
  it('mounts StructureEditor with mode="post-summary"', () => {...})
  it('on save with affected summaries, fetches edit-impact and shows ConfirmDialog', async () => {...})
  it('confirm dialog includes invalidation copy when summaries_to_invalidate not empty', () => {...})
  it('skips edit-impact fetch for rename-only ops', async () => {...})
  it('edit-impact fetch times out at 10s, shows fallback dialog', async () => {...})
  // BookDetailView.spec.ts
  it('renders Edit Structure button when no active job', () => {...})
  it('hides Edit Structure when active job present', () => {...})
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement `ConfirmDialog.vue` (generic). Props: `title`, `body`, `primaryLabel`, `secondaryLabel`, `loading`. Slots optional.

- [ ] Step 4: Implement `EditStructureView.vue`:
  - Fetches sections.
  - Mounts `<StructureEditor :mode="'post-summary'">`.
  - On save: compute `affected_section_ids` (sections about to mutate); skip if op is rename-only; else `getEditImpact()` with `AbortController` + 10s timeout (FR-F28); show ConfirmDialog with copy adapted to impact response.

- [ ] Step 5: Add route `/books/:id/edit-structure` in `router/index.ts`.

- [ ] Step 6: Add Edit Structure button to `BookDetailView.vue` `#actions` slot. Hide via `v-if="!useJobQueueStore().hasActiveJobForBook(bookId)"` (getter to add in T24).

- [ ] Step 7: Run tests → pass.

- [ ] Step 8: Commit.
  ```bash
  git commit -m "feat(structure): EditStructureView route, ConfirmDialog, edit-impact wiring"
  ```

**Inline verification:** view + dialog tests green.

---

### T24: `useJobQueueStore` Pinia store with 5-step seed-then-drain

**Goal:** Single SSE connection per session; race-safe seeding.
**Spec refs:** FR-F19, FR-F19b, FR-F19c, P9, D19

**Files:**
- Create: `frontend/src/stores/jobQueue.ts`
- Create: `frontend/src/stores/__tests__/jobQueue.spec.ts`
- Modify: `frontend/src/api/processing.ts` (extend SSE handler with new events)
- Delete: `frontend/src/stores/summarizationJob.ts`
- Modify: all files importing the old store

**Steps:**

- [ ] Step 1: Write failing tests.
  ```typescript
  describe('useJobQueueStore', () => {
    it('connect(): subscribes SSE, buffers events, then seeds, then drains', async () => {...})
    it('drains: drops buffered events with last_event_at <= seed row', async () => {...})
    it('reconnects with exponential backoff on SSE error', async () => {
      vi.useFakeTimers()
      // simulate disconnect; assert next attempt at 1s, then 2s, ..., capped 30s
    })
    it('queuePositionOf returns 0 for running, 1+ for pending', () => {...})
    it('hasActiveJobForBook returns true when book has running OR pending', () => {...})
    it('connectionState transitions: connecting → connected → reconnecting', () => {...})
  })
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement `jobQueue.ts`:
  ```typescript
  export const useJobQueueStore = defineStore('jobQueue', () => {
    const runningJob = ref<Job | null>(null)
    const pendingJobs = ref<Job[]>([])
    const connectionState = ref<'idle' | 'connecting' | 'connected' | 'reconnecting'>('idle')
    let eventSource: EventSource | null = null
    let buffer: SseEvent[] = []
    let mode: 'buffer' | 'live' = 'buffer'
    let backoffMs = 1000

    async function connect() {
      connectionState.value = 'connecting'
      // 1. open SSE → push to buffer
      eventSource = new EventSource('/api/v1/processing/events')
      eventSource.onmessage = (e) => {
        const evt = JSON.parse(e.data)
        if (mode === 'buffer') buffer.push(evt)
        else apply(evt)
      }
      eventSource.onerror = () => scheduleReconnect()
      // 2. fetch seed
      const seed = await fetch('/api/v1/processing/jobs?status=PENDING,RUNNING').then(r => r.json())
      // 3. apply seed
      applySeed(seed.jobs)
      // 4. drain buffer (drop events ≤ seed last_event_at per job)
      for (const evt of buffer) {
        const seedRow = findSeedRow(evt.data.job_id)
        if (seedRow && evt.data.last_event_at <= seedRow.last_event_at) continue
        apply(evt)
      }
      buffer = []
      mode = 'live'
      connectionState.value = 'connected'
      backoffMs = 1000
    }

    function scheduleReconnect() {
      connectionState.value = 'reconnecting'
      eventSource?.close()
      mode = 'buffer'; buffer = []
      setTimeout(() => connect(), backoffMs)
      backoffMs = Math.min(backoffMs * 2, 30000)
    }
    // ...queuePositionOf, hasActiveJobForBook, apply, applySeed
  })
  ```

- [ ] Step 4: Find all consumers of the old store and migrate.
  Run: `grep -rn 'useSummarizationJobStore\|summarizationJob' frontend/src/ | grep -v __tests__`
  Expected hits: `BookDetailView.vue`, `SummarizationProgress.vue`, possibly others.
  - For each file, replace `useSummarizationJobStore()` with `useJobQueueStore()`. Field renames as needed:
    - `job.isActive` → `store.hasActiveJobForBook(bookId)` (or per-job equivalent)
    - `job.activeJobSectionId` → `store.runningJob?.progress?.section_id` (or remove if unused)
    - `job.completedCount/failedCount/skippedCount` → read from `store.runningJob?.progress`
  - After all imports migrated, re-run the grep — only the test file path should remain (which gets deleted in Step 5).
- [ ] Step 4a: Re-run grep gate.
  Run: `! grep -rn 'useSummarizationJobStore' frontend/src/ | grep -v stores/__tests__`
  Expected: empty.

- [ ] Step 5: Delete `summarizationJob.ts`.

- [ ] Step 6: Run tests + type-check → pass.
  Run: `cd frontend && npm run test:unit && npm run type-check`

- [ ] Step 7: Commit.
  ```bash
  git commit -m "feat(store): useJobQueueStore with seed-then-drain SSE; replace summarizationJob"
  ```

**Inline verification:** jobQueue.spec.ts green; type-check clean.

---

### T25a: `<JobProgress>` component (renders all 5 states)

**Goal:** Single component renders pending / running / cancelling / completed / failed for a `jobId`. Used in UploadWizard Step 4 (this task) and later embedded in PersistentProcessingIndicator (T25b).

**Spec refs:** FR-F14, FR-F15, FR-F16, FR-F17, FR-F19c, P7

**Files:**
- Create: `frontend/src/components/job/JobProgress.vue`
- Create: `frontend/src/components/job/__tests__/JobProgress.spec.ts`
- Modify: `frontend/src/components/upload/UploadWizard.vue` Step 4 (replace static card)

**Steps:**

- [ ] Step 1: Write failing tests.
  ```typescript
  describe('JobProgress', () => {
    it('renders queued state with N-ahead text when status=PENDING', () => {
      const wrapper = mount(JobProgress, { props: { jobId: 42 }, global: { plugins: [pinia(seedStore({ pendingJobs: [{ id: 42, queue_position: 2 }] }))] }})
      expect(wrapper.text()).toContain('1 book ahead')  // queue_position-1
    })
    it('renders running state with progress bar + counters', () => {...})
    it('renders cancelling overlay when status=RUNNING and cancel_requested=true', () => {...})
    it('renders completed success card with View Book CTA, no auto-redirect', async () => {
      // assert no router.push fired
    })
    it('renders failed state with cancel-aware copy when reason="cancelled"', () => {...})
    it('renders failed state with cli-disappeared copy when reason="cli_disappeared"', () => {...})
    it('renders generic failed state when reason="error"', () => {...})
    it('renders Reconnecting badge when store.connectionState=reconnecting', () => {...})
  })
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement `JobProgress.vue` — reads `useJobQueueStore()`, computes state from job status + cancel flag + reason. Use `<template v-if>` per state for clarity.

- [ ] Step 4: Modify `UploadWizard.vue` Step 4 — replace static card with `<JobProgress :job-id="currentJobId" />`. Add Step4 CTAs row: "Open Book Now" (router push to `/books/:id`), "Dismiss → Library" (close wizard, route to `/`). On `processing_completed`, JobProgress already renders the success card with primary "View Book"; no auto-redirect.

- [ ] Step 5: Run tests + type-check → pass.

- [ ] Step 6: Commit.
  ```bash
  git add frontend/src/components/job/JobProgress.vue frontend/src/components/job/__tests__/JobProgress.spec.ts frontend/src/components/upload/UploadWizard.vue
  git commit -m "feat(job): JobProgress component renders all 5 states"
  ```

**Inline verification:**
- JobProgress.spec.ts green.
- Manual: trigger summarize from /upload, observe Step 4 transitions queued → running → completed without page refresh.

---

### T25b: `<PersistentProcessingIndicator>` + `<QueuePanel>` mounted in AppShell

**Goal:** Bottom-bar indicator visible across all routes when any job exists; expand reveals queue with per-row Cancel.

**Spec refs:** FR-F18, FR-F19a, FR-F19c, D11, NFR-05

**Files:**
- Create: `frontend/src/components/job/PersistentProcessingIndicator.vue`
- Create: `frontend/src/components/job/QueuePanel.vue`
- Create: `frontend/src/components/job/__tests__/PersistentProcessingIndicator.spec.ts`
- Create: `frontend/src/components/job/__tests__/QueuePanel.spec.ts`
- Modify: `frontend/src/components/app/AppShell.vue` (mount indicator + call `store.connect()`)

**Steps:**

- [ ] Step 1: Write failing tests.
  ```typescript
  describe('PersistentProcessingIndicator', () => {
    it('hidden via v-show=false when no jobs', () => {
      const wrapper = mount(PersistentProcessingIndicator, { /* empty store */ })
      expect(wrapper.attributes('style')).toContain('display: none')
    })
    it('visible when running OR pending exists', () => {...})
    it('shows running job title + progress + "+N queued" badge', () => {...})
    it('expand toggle reveals QueuePanel', async () => {...})
    it('Reconnecting badge when store.connectionState=reconnecting', () => {...})
  })

  describe('QueuePanel', () => {
    it('renders one row per job in created_at order', () => {...})
    it('Cancel on PENDING row opens "Remove from queue?" confirm', async () => {...})
    it('Cancel on RUNNING row opens "Cancel summarization?" confirm', async () => {...})
    it('Cancel buttons have aria-label="Cancel queued job: {title}"', () => {...})
  })
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Implement `PersistentProcessingIndicator.vue` (fixed bottom bar, `v-show` toggle per D11). Embeds `<JobProgress :job-id="store.runningJob?.id" :compact />` for the current row; queue badge on the right; expand chevron toggles `<QueuePanel>` slide-up.

- [ ] Step 4: Implement `QueuePanel.vue`. Renders `[runningJob, ...pendingJobs]`. Each row: title, status pill, Cancel button. Cancel uses `ConfirmDialog` from T23 with copy from FR-F19a.

- [ ] Step 5: Modify `AppShell.vue:23` — mount `<PersistentProcessingIndicator />` after `<ToastContainer>`; in `onMounted`, call `useJobQueueStore().connect()`.

- [ ] Step 6: Run tests + type-check → pass.

- [ ] Step 7: Commit.
  ```bash
  git add frontend/src/components/job/PersistentProcessingIndicator.vue frontend/src/components/job/QueuePanel.vue frontend/src/components/job/__tests__/PersistentProcessingIndicator.spec.ts frontend/src/components/job/__tests__/QueuePanel.spec.ts frontend/src/components/app/AppShell.vue
  git commit -m "feat(job): PersistentProcessingIndicator + QueuePanel mounted in AppShell"
  ```

**Inline verification:**
- Both component tests green.
- Manual: load app, indicator hidden; trigger summarize on book A, indicator appears with progress; trigger book B, "+1 queued" badge appears; expand panel shows both rows with Cancel buttons.

---

### T26: Step 3 preflight banner + LlmSettings rebuild

**Goal:** Settings → LLM has provider dropdown with detected/version badges, config_dir input, banner + Re-detect; Step 3 disables Start when preflight fails.
**Spec refs:** FR-F12, FR-F13, FR-F20, FR-F21, FR-F22, FR-F23, FR-F23a, FR-F24, §6.7, §6.9, §13.3

**Files:**
- Modify: `frontend/src/api/settings.ts`
- Modify: `frontend/src/components/settings/LlmSettings.vue`
- Modify: `frontend/src/components/settings/__tests__/LlmSettings.spec.ts`
- Modify: `frontend/src/stores/settings.ts` (add `preflight: PreflightResult | null`, `recheck()` action)
- Modify: `frontend/src/components/upload/UploadWizard.vue` Step 3

**Steps:**

- [ ] Step 1: Write failing tests.
  ```typescript
  // LlmSettings.spec.ts
  it('does NOT render cli_command input', () => {
    expect(wrapper.find('[data-test="cli-command-input"]').exists()).toBe(false)
  })
  it('renders config_dir input with provider-specific placeholder', () => {...})
  it('provider dropdown shows ✓ + version badge when detected', () => {...})
  it('provider dropdown shows ✗ when not detected', () => {...})
  it('auto option shows resolved provider in parens (status.provider when settings.provider=auto)', () => {
    // settingsStore.settings.llm.provider = 'auto', preflight.provider = 'claude'
    expect(wrapper.find('[data-test="provider-auto-label"]').text())
      .toContain('auto (→ claude')  // resolved comes from /llm/status response
  })
  it('auto option shows "none detected" when nothing on PATH', () => {
    // preflight.provider = 'auto', binary_resolved = false
    expect(wrapper.find('[data-test="provider-auto-label"]').text())
      .toContain('auto (→ none detected) ✗')
  })
  it('renders banner when preflight.ok=false', () => {...})
  it('banner clears immediately on successful save with new ok=true', async () => {...})
  it('Re-detect button calls POST /llm/recheck and updates store', async () => {...})
  it('How to install link uses claude URL when provider=claude', () => {
    expect(wrapper.find('[data-test="install-link"]').attributes('href'))
      .toBe('https://docs.claude.com/en/docs/claude-code/setup')
  })
  it('How to install link uses codex URL when provider=codex', () => {
    expect(...).toBe('https://github.com/openai/codex')
  })
  // UploadWizard Step 3
  it('Step 3 fetches /llm/status on mount', async () => {...})
  it('Start button disabled when preflight.ok=false', () => {...})
  it('Start button enabled when preflight.ok=true', () => {...})
  it('Start handler renders banner from 400 response (defense-in-depth)', async () => {...})
  ```

- [ ] Step 2: Run → fail.

- [ ] Step 3: Update `frontend/src/api/settings.ts:3-24` — drop `cli_command`, add `config_dir: string | null`. Add `getLlmStatus()` and `recheckLlm()` functions hitting `/api/v1/llm/status` and `/api/v1/llm/recheck`.

- [ ] Step 4: Update `frontend/src/stores/settings.ts` — add `preflight` ref + `recheck()` action.

- [ ] Step 5: Rebuild `LlmSettings.vue`:
  - Remove `cliCommand` computed + input (lines 34-41, 131-143).
  - Add `configDir` computed binding to `settingsStore.settings.llm.config_dir`.
  - Add `<input>` for config_dir with placeholder logic (claude → `~/.claude-personal`, codex → `~/.codex-personal`).
  - Replace provider `<select>` with custom dropdown that shows badges (`✓ <version>` / `✗ not found` / `auto (→ <resolved>)`).
  - Add banner template at top: `v-if="!preflight?.ok"`. Banner contains: reason, "How to install" link (URL by provider), Re-detect button.
  - Save payload: `{ llm: { provider, config_dir: configDir.value, model } }`.

- [ ] Step 6: Modify `UploadWizard.vue` Step 3:
  - On mount: `await settingsStore.refreshPreflight()`.
  - If `!preflight.ok` → render banner (inline) + disable Start button.
  - On Start click: catch 400 with `error_code='llm_provider_unavailable'` → render banner from response payload.

- [ ] Step 7: Update `LlmSettings.spec.ts` fixture: replace `cli_command: 'claude'` with `config_dir: null`.

- [ ] Step 8: Add the **frontend grep regression gate** test:
  ```typescript
  // frontend/src/__tests__/no_cli_command_orphans.spec.ts
  import { execSync } from 'child_process'
  it('no cli_command references in frontend src', () => {
    const out = execSync('grep -rn cli_command src/ || true', { cwd: __dirname + '/..' })
      .toString().split('\n').filter(l => l && !l.includes('/static/'))
    expect(out).toEqual([])
  })
  ```

- [ ] Step 9: Run all frontend tests + type-check + lint.
  Run: `cd frontend && npm run test:unit && npm run type-check && npm run lint`
  Expected: all green.

- [ ] Step 10: Manual grep gate.
  Run: `! grep -rn 'cli_command' frontend/src/`
  Expected: empty.

- [ ] Step 11: Commit.
  ```bash
  git commit -m "feat(settings): rebuild LlmSettings with provider badges, config_dir, banner; Step 3 preflight gate"
  ```

**Inline verification:**
- All LlmSettings + Step 3 tests green.
- Frontend grep clean.

---

### T27: Final Verification

**Goal:** Verify the entire implementation works end-to-end.
**Spec refs:** §13.4, §13.5, "Done when" criteria above

- [ ] **Lint & format (backend):** `cd backend && uv run ruff check . && uv run ruff format --check .` → clean.
- [ ] **Type check (frontend):** `cd frontend && npm run type-check` → clean.
- [ ] **Lint (frontend):** `cd frontend && npm run lint` → clean.
- [ ] **Backend unit tests:** `cd backend && uv run python -m pytest tests/unit/ -v` → all green.
- [ ] **Backend integration tests:** `cd backend && uv run python -m pytest tests/integration/ -v -m "not integration_llm"` → all green.
- [ ] **Frontend unit tests:** `cd frontend && npm run test:unit` → all green.
- [ ] **`cli_command` regression gate (final):**
  ```bash
  ! grep -rn 'cli_command' backend/app/ frontend/src/ | grep -v '/static/' | grep -v '.pyc' | grep -v node_modules
  ```
  Expected: command exits 0 (zero matches).
- [ ] **Migrations:** `cd backend && uv run alembic -c app/migrations/alembic.ini upgrade head && uv run alembic -c app/migrations/alembic.ini downgrade -1 && uv run alembic -c app/migrations/alembic.ini upgrade head` → all 3 succeed.
- [ ] **Build frontend into backend static:**
  ```bash
  cd frontend && npm run build
  rm -rf ../backend/app/static && cp -R dist ../backend/app/static
  ```
- [ ] **Start backend on test port:** `cd backend && uv run bookcompanion serve --port 8765 &`
- [ ] **API smoke:**
  - `curl -sf http://localhost:8765/api/v1/health` → 200
  - `curl -sf http://localhost:8765/api/v1/llm/status | python3 -m json.tool` → valid JSON with `preflight.ok=true` (assuming claude on PATH)
  - `curl -sf "http://localhost:8765/api/v1/processing/jobs?status=PENDING,RUNNING" | python3 -m json.tool` → `{"jobs": []}` initially
- [ ] **Playwright MCP — Scenario 1 (Happy path):**
  1. Authenticate / no-auth as configured.
  2. Navigate `http://localhost:8765/upload`.
  3. Upload `backend/tests/fixtures/sample_epub/art_of_war.epub` via the dropzone.
  4. Verify UploadFileCard shows determinate bar transitioning to indeterminate parse spinner.
  5. Verify Step 2 renders StructureEditor with rows; reorder one row via drag; rename one section; delete one and Undo; multi-select 2 → Merge.
  6. Verify Step 3 shows preflight ✓; click Start.
  7. Verify Step 4 shows JobProgress live with section counters; observe persistent indicator at bottom.
  8. Wait for `processing_completed`; verify success summary with View Book CTA; click → lands on `/books/:id`.
  9. `browser_console_messages(level: 'error')` → empty.
  10. Take screenshot for verification.
- [ ] **Playwright MCP — Scenario 2 (No-CLI path):**
  1. Set `provider=codex` in Settings (codex not installed locally) OR monkeypatch via test hook.
  2. Navigate to /upload, complete Steps 1-2, reach Step 3.
  3. Verify red banner with "[Fix in Settings → LLM]" link; Start button disabled.
  4. Navigate to /settings/llm — verify banner + How to install link.
- [ ] **Playwright MCP — Scenario 3 (Multi-book queue):**
  1. Trigger Book A summarize.
  2. While Book A runs, upload Book B and reach Step 4.
  3. Verify Book B Step 4 shows "Queued — 1 book ahead".
  4. Verify persistent indicator shows Book A current + "+1 queued" badge.
  5. Wait for Book A completion → verify Book B auto-promotes to live progress.
- [ ] **Playwright MCP — Scenario 4 (Cancel running):**
  1. Trigger Book A summarize.
  2. Mid-run, click Cancel in persistent indicator → confirm dialog → confirm.
  3. Verify "Cancelling…" overlay appears.
  4. Verify within 5s, JobProgress transitions to FAILED with cancel-aware copy.
  5. Verify partial summaries preserved (`sqlite3 library.db "SELECT count(*) FROM summaries WHERE content_type='section' AND content_id IN (SELECT id FROM book_sections WHERE book_id=<A>)"` > 0).
- [ ] **Playwright MCP — Scenario 5 (Edit Structure post-summary):**
  1. Navigate to /books/:id (a fully-summarized book).
  2. Click Edit Structure in toolbar → lands on `/books/:id/edit-structure`.
  3. Split a summarized chapter via Auto-detect headings.
  4. Click Save → verify ConfirmDialog mentions "summary will be invalidated".
  5. Confirm → verify BookDetailView shows "Re-summarize" CTA (book.status=PARSED, default_summary_id=None).
  6. `browser_console_messages(level: 'error')` → empty.
- [ ] **Manual spot-check:** Edit `~/Library/Application Support/bookcompanion/settings.yaml` to set `llm.config_dir: ~/.claude-personal`; restart serve; verify `claude` subprocess invoked from a summarize uses `CLAUDE_CONFIG_DIR=~/.claude-personal` (check via stderr log or trace).
- [ ] **Cleanup:**
  - [ ] `kill $(lsof -ti:8765)`.
  - [ ] Remove temp test files / scratch scripts (none expected after T3 cleanup).
  - [ ] Confirm no stray `console.log` or `print()` debugging.
  - [ ] Update `docs/changelog.md` with user-facing changes (run `/changelog` after merge per CLAUDE.md workflow).
  - [ ] Tag spec OQ1, OQ2, OQ3 as resolved in spec doc.

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| (initial) | Plan drafted from spec; spec gaps surfaced (Summary.section_id/is_stale missing, Book.book_summary_id name, BookStatus enum). | Added decisions P1–P14 to Decision Log; integrated schema reality into all impacted tasks (T10, T15, T17). |
| 1 | F1: T23 cross-ref bug — referenced "T28" for jobQueue store but store is T24. F2: T11 was oversized (extract + lifespan + atomic-promotion + per-job provider in one task). F3: T25 had 3 components (JobProgress, PersistentProcessingIndicator, QueuePanel) in one task. F4: T12 didn't explicitly add `processing_failed.reason` SSE field per spec §8.6. | F1 fix-as-proposed: 4 references updated T28→T24 (file map row, two risks rows, T23 step 6). F2 fix-as-proposed: split into T11a (scaffold + lifespan + extract `_run_processing`) and T11b (atomic-promotion SQL + per-job provider). F3 fix-as-proposed: split into T25a (JobProgress alone, used in Step 4) and T25b (PersistentProcessingIndicator + QueuePanel mounted in AppShell). F4 fix-as-proposed: added explicit Step 5 in T12 with three reason-branch unit tests + integration assertion; renumbered subsequent steps. Execution order diagram updated. |
| 2 | L2-F1: T8's `/llm/status` returned `settings.llm.provider` literally, but spec §8.1 example shows the resolved binary so frontend FR-F22 can render `auto (→ claude 2.1.123) ✓`. L2-F2: T24 step 4 said "grep first" without a concrete command. L2-F3: Two follow-ups (`SummarizationProgress.vue` deletion after JobProgress soak; `bookcompanion edit sections` CLI parity). | L2-F1 fix-as-proposed: added `_resolve_provider()` helper to `routes/llm.py`; route returns the resolved binary; added two new unit tests covering auto→resolved and auto→nothing-resolved cases; updated T26 LlmSettings.spec to assert resolved-name rendering. L2-F2 fix-as-proposed: T24 Step 4 now has the exact grep command + Step 4a regression gate. L2-F3 add-to-backlog: invoking /backlog add for both items separately (see post-plan output). |
