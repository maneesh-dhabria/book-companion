# Upload + Summarize Flow — UX Fixes & Structure Editor — Spec

**Date:** 2026-04-30
**Status:** Draft
**Tier:** 2 — Enhancement (bundled with one Tier-1 config-shape fix)
**Requirements:** [`docs/requirements/2026-04-30-upload-summarize-flow-ux-fixes.md`](../requirements/2026-04-30-upload-summarize-flow-ux-fixes.md)
**Wireframes:** [`docs/wireframes/2026-04-30_upload_summarize_flow_ux_fixes/`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/index.html)

---

## 1. Problem Statement

The "add a new book" wizard has four user-facing gaps that surfaced on first real-world end-to-end run (Playing to Win, 25 sections):

1. Silent dropzone after file pick (no upload/parse feedback).
2. Step 2 Structure Review is read-only despite a fully implemented `SectionEditService` + HTTP routes (merge, split, move, delete, set_type, undo) on the backend.
3. Step 4 is a static "View Progress" card despite `SummarizationProgress.vue` + 7 SSE event types already wired.
4. Settings → LLM exposes a free-form `cli_command` text input that silently breaks summarization when the user enters a shell alias (subprocess doesn't source rc files). The right fix is structural: drop `cli_command` and replace it with `provider` (auto-detected) + `config_dir` (env-var-routed) + `model`.

Additionally, multi-book uploads have no queue UX, and editing structure post-summarization is impossible.

**Primary success metric:** End-to-end first-time book add → summarize flow on a fresh book completes without the user having to ask "is something happening?" or hand-edit settings.yaml.

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|---------------|
| G1 | Step 1 always shows upload + parse progress | Per-file card with determinate bar (HTTP upload) → indeterminate spinner (parse) visible from drop until Step 2 transition |
| G2 | Step 2 supports full structure editing | Per-row char count, rename, delete, split (3 modes), drag-reorder; multi-select toolbar for merge, bulk delete, bulk set-type |
| G3 | Same editor reused on BookDetailView post-summarization | New route `/books/:id/edit-structure` renders the same component; affected summaries marked stale on save |
| G4 | Step 4 shows live progress | `SummarizationProgress` (or successor) bound to SSE; success card on completion with manual "View Book" CTA; no auto-redirect |
| G5 | Multi-book queue is visible and serial | Persistent bottom-bar indicator visible across all routes; expandable queue list with cancel-per-row; at most one RUNNING job globally |
| G6 | Settings → LLM cannot accept a doomed value | `cli_command` field removed; `provider` dropdown lists detected binaries with ✓/✗ status; preflight blocks summarize when binary unresolved |
| G7 | Cancel a RUNNING job mid-summarization | Persistent indicator's expand panel exposes Cancel for the running row; subprocess receives SIGTERM; partial summaries preserved |

---

## 3. Non-Goals

- **Parallel multi-book processing** — serialized queue only. Reason: LLM CLI rate-limit risk at single-user scale.
- **CLI parity for section editing** (`bookcompanion edit sections`) — defer; web-first workflow.
- **Free-form `cli_command` migration toast / sentinel file** — tool is unreleased, no users to migrate. Just drop the field.
- **CLI parity for new `config_dir` field** — Settings UI is the only surface that needs to set it (`bookcompanion config set` will still work via the generic settings handler since it routes through `SettingsService.update_settings()`, but no dedicated CLI flag).
- **Word/page count in editor** — char count only (already on `SectionItem.char_count`).
- **Dropzone visual redesign** — only the loading-state behavior.
- **Restoring wizard state on browser refresh during Step 4** — refresh punts to BookDetailView; persistent indicator covers the gap.

---

## 4. Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Drop `LLMConfig.cli_command`; add `LLMConfig.config_dir: Path \| None` | (a) keep + validate; (b) drop + add config_dir; (c) make cli_command a dropdown of detected binaries | (b) removes the alias/shell-function class of bug at the source. `provider` enum (already present, currently `auto`/`claude`/`codex`) plus per-provider env-var routing covers every legitimate use case. |
| D2 | `config_dir` is a single field, provider-routed | (a) one field; (b) two fields (`claude_config_dir`, `codex_home`) | One field, one UI input. Each provider's `generate()` reads it and injects the appropriate env var (`CLAUDE_CONFIG_DIR` or `CODEX_HOME`) into `subprocess` env. Switching provider re-uses the same path. |
| D3 | Switch `CodexCLIProvider` from `codex -p <prompt>` to `codex exec --skip-git-repo-check` | (a) keep `-p`, drop flag; (b) switch to `exec` + flag | Empirically verified that the env-var-driven workflow runs under `codex exec`; `--skip-git-repo-check` is required because the worker runs from the data dir, not a git repo. Spec implementation must verify `codex exec` accepts the same prompt/model/output-format flags `-p` does and that schema-in-prompt injection still works. |
| D4 | Pre-release: no settings.yaml migration ceremony | (a) load-time strip + toast; (b) hard-fail; (c) silent drop; (d) no migration | (d) tool is unreleased (per maintainer); no users have a non-default `cli_command` in production. New `LLMConfig` simply doesn't have the field. Pydantic `extra="forbid"` will reject any stale YAML, but that's a developer concern, not a user one. Wireframe 07's "migration toast" state is dropped from scope. |
| D5 | Server-side preflight before queueing the job | (a) preflight in API route; (b) frontend-only `/api/v1/llm/status`; (c) lazy fail at subprocess spawn | (a) one source of truth; the API route checks (i) provider binary resolves on PATH, (ii) optionally version floor, returns 400 with structured payload; frontend renders the banner from that payload. Frontend `/status` endpoint is also added (for the persistent banner on Settings page) but the queue-blocking gate is in the summarize route itself. |
| D6 | Version-floor check shipped now | (a) ship version check; (b) defer | Cheap (~30 LoC, one cached-per-session call); avoids confusing-failure class for users on old `claude < 2.1` (no `CLAUDE_CONFIG_DIR` honored) or old `codex` without `CODEX_HOME` support. Non-blocking warning, not a hard gate. Versions: claude ≥ 2.1, codex ≥ 0.118. |
| D7 | Global single-RUNNING queue, not per-book | (a) per-book serial (existing constraint); (b) global serial | (b) avoids LLM CLI rate-limit risk. Existing per-book partial UNIQUE index `(book_id, status IN ('PENDING','RUNNING'))` already prevents same-book double-jobs; the new layer is a queue worker that promotes the oldest PENDING job to RUNNING only when no RUNNING job exists across all books. |
| D8 | Cancel RUNNING job: in scope | (a) in scope; (b) defer | User selected "in scope" during interview. SIGTERM the subprocess; partial summaries preserved (existing per-section commit semantics already isolate work); job marked `FAILED` with `error_message="cancelled"` and a new `cancel_requested` boolean column. |
| D9 | Edit Structure on BookDetailView is a dedicated route `/books/:id/edit-structure` | (a) dedicated route; (b) modal; (c) tab | (a) reuses the wizard's Structure Editor 1:1, gives back-button semantics, no scroll/z-index battles with the reader. Cheapest reuse path. |
| D10 | Auto-detect-headings split preview: count + first line + char count per part | (a) count + first line + chars; (b) full-content rendered preview | (a) cheap, gives enough confidence; matches wireframe 03. Full-content preview rejected as overkill for the typical use case. |
| D11 | Persistent processing indicator: fixed bottom bar in `AppShell` | (a) bottom bar; (b) top bar under nav | (a) consistent with wireframe 06; uses `v-show` (not `v-if`) per project pattern (2026-04-25 D11) so first interaction is reliable. Hidden when no PENDING/RUNNING jobs. |
| D12 | XHR-driven upload progress | (a) XHR for upload + indeterminate parse; (b) indeterminate only | (a) honest two-phase indicator (matches G1). XHR adds <50 LoC and avoids the dishonesty of an "indeterminate spinner" for a 5-30 MB upload that takes seconds. |
| D13 | Browser refresh during Step 4: punt to BookDetailView | (a) restore wizard; (b) punt | Persistent indicator already covers cross-route progress; no value in restoring wizard state. |
| D14 | Structure-editor reuse: single Vue component with two parent contexts | (a) shared component, two parents; (b) two near-identical components | (a) one set of tests, one set of bug fixes. Component takes a `mode: 'wizard' \| 'post-summary'` prop that toggles save semantics (commit immediately vs. confirm-with-invalidation dialog). |
| D15 | Book summary invalidation on post-summary edit: only when affected sections were summarized | (a) always invalidate; (b) only-if-summarized; (c) leave-and-warn | (b) precise: merging never-summarized sections doesn't dirty the book summary because nothing read them. Pre-save dialog text adapts. |
| D16 | Merge ordering: document-order, non-contiguous selections allowed, lowest-index slot | (a) doc-order non-contig; (b) contiguous-only; (c) selection-order | (a) most flexible without surprising the user. Result content reads in document order regardless of selection-order. |
| D17 | Per-row vs. toolbar split | (a) as documented; (b) all in overflow menu; (c) all in toolbar | Per-row: rename, delete, split, drag handle. Toolbar (multi-select): merge, bulk delete, bulk set-type. Matches Calibre/Scrivener norms. |

---

## 5. User Journeys

### 5.1 Fresh book, happy path
Covered in requirements §User Journeys → Primary Journey 1. No new flow logic in spec; this section just confirms component composition (see §11).

### 5.2 Edit structure post-summarization
1. From `/books/:id`, user clicks **Edit Structure** in book toolbar → router pushes `/books/:id/edit-structure`.
2. Same `<StructureEditor :mode="'post-summary'">` component renders.
3. User edits (e.g., split chapter 7 at headings).
4. On save click, frontend computes `affected_section_ids` (every section that will be deleted/replaced/changed) and queries `GET /api/v1/books/:id/sections/edit-impact?ids=...` which returns `{summaries_to_invalidate: [section_ids], invalidate_book_summary: bool}`.
5. Frontend shows confirm dialog with copy adapted to the impact response.
6. On confirm, `POST /api/v1/books/:id/sections/<edit-op>` (existing routes) is called; backend marks affected `Summary` rows as stale via the existing eval-trace stale-marking pattern, and (if applicable) clears `Book.book_summary_id` to invalidate the book summary.

### 5.3 Multi-book queue
1. Book A's Step 3 → "Start Processing" → server-side preflight passes → `ProcessingJob` created with `status=PENDING`.
2. Queue worker (already-running async loop) sees no RUNNING job → promotes Book A to RUNNING. SSE `processing_started` fires.
3. While Book A runs, user uploads Book B and clicks Start. Preflight passes → `ProcessingJob{status=PENDING, book_id=B}` created. Queue worker sees a RUNNING job already → leaves PENDING.
4. Book B's wizard Step 4 binds to Book B's job state from Pinia. Status=PENDING → renders queued-state UI ("Queued — 1 book ahead"). Persistent indicator shows Book A current + "+1 queued".
5. Book A `processing_completed` → queue worker promotes Book B to RUNNING. SSE fires for Book B. Book B's wizard Step 4 (still mounted) auto-updates to live-progress UI; persistent indicator updates.
6. Cancel-PENDING from indicator: user clicks Cancel on Book B's row → `POST /api/v1/books/B/processing/cancel` deletes the PENDING job. Cancel-RUNNING: same endpoint, but RUNNING jobs are SIGTERMed and marked FAILED.

---

## 6. Functional Requirements

### 6.1 Backend — LLM config & providers

| ID | Requirement |
|----|-------------|
| FR-B01 | Remove `LLMConfig.cli_command`. Pydantic `extra="forbid"` will reject stale YAML — acceptable since pre-release. |
| FR-B01a | **Full removal of `cli_command` from the codebase.** Every reference must be deleted, not just the field declaration. Inventory (verified 2026-04-30 via `grep -rn cli_command backend/app/ frontend/src/`): see §6.1a below. After cleanup, `grep -rn 'cli_command' backend/app/ frontend/src/ \| grep -v '/static/'` MUST return zero matches. This is a verification gate (§13.5). |
| FR-B02 | Add `LLMConfig.config_dir: Path \| None = None`. Path is expanded via `Path.expanduser()` on read. |
| FR-B03 | `ClaudeCodeCLIProvider.__init__` removes `cli_command` parameter (binary name is hard-coded `"claude"` in a class constant `BINARY = "claude"`). Adds `config_dir: Path \| None = None`. |
| FR-B04 | `ClaudeCodeCLIProvider.generate()` constructs subprocess env as `os.environ.copy()`, then if `self.config_dir` is set, sets `env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)`. |
| FR-B05 | `CodexCLIProvider` symmetric: hard-coded binary `"codex"` (class constant `BINARY = "codex"`), accepts `config_dir`, injects `CODEX_HOME` env var. |
| FR-B06 | `CodexCLIProvider` switches subprocess invocation from `codex -p <prompt> --model X` to `codex exec --skip-git-repo-check --model X`. Prompt is passed via stdin (existing pattern from `ClaudeCodeCLIProvider`). Schema-in-prompt injection unchanged. |
| FR-B07 | `create_llm_provider()` factory updated to pass `config_dir=settings.llm.config_dir` to both providers. The factory no longer reads or accepts a `cli_command` argument from any caller. |
| FR-B07a | `SubprocessNotFoundError` constructor signature changes from `__init__(self, cli_command: str)` to `__init__(self, binary: str)` — the parameter is renamed since "cli_command" no longer matches what's being passed (it's now always the hard-coded binary name). All raise sites updated. |
| FR-B07b | Logging helpers `_maybe_force_test_failure(cli_command, context)` and `_maybe_log(cli_command=..., ...)` in `claude_cli.py` rename their `cli_command` parameter to `binary`. All call sites in both providers updated. |

### 6.1a Full inventory of `cli_command` removal

Every code path below must be cleaned up as part of this spec; no orphans allowed.

**Backend — config & exceptions:**
- `backend/app/config.py:26` — delete `cli_command: str = "claude"` field; add `config_dir: Path | None = None` in its place.
- `backend/app/exceptions.py:71-73` — `SubprocessNotFoundError(cli_command)` → `SubprocessNotFoundError(binary)`; update message + attribute.

**Backend — provider implementations:**
- `backend/app/services/summarizer/claude_cli.py:24, 44, 49, 79, 84, 98, 103, 128, 134, 145, 159, 183` — every `cli_command` parameter, attribute access, and log key renamed to `binary` (or deleted where it was a parameter, since the binary is now a class constant). The argv list at `:103` uses `self.BINARY` instead of `self.cli_command`.
- `backend/app/services/summarizer/codex_cli.py:25, 30, 44, 61, 81, 87, 94, 106` — same treatment. `:61` argv becomes `[self.BINARY, "exec", "--skip-git-repo-check", "--model", model, ...]`.

**Backend — wiring (deps + routes):**
- `backend/app/cli/deps.py:144` — `create_llm_provider(cli_command=settings.llm.cli_command, ...)` → `create_llm_provider(config_dir=settings.llm.config_dir, ...)`.
- `backend/app/api/deps.py:48` — same.
- `backend/app/api/routes/processing.py:163` — same.
- `backend/app/api/routes/book_summary.py:142` — same.
- `backend/app/api/routes/ai_threads.py:169` — same.

**Backend — settings surface:**
- `backend/app/services/settings_service.py:128` — `get_safe_settings()` drops the `"cli_command": self.settings.llm.cli_command` entry; adds `"config_dir": str(self.settings.llm.config_dir) if self.settings.llm.config_dir else None`.
- `backend/app/cli/commands/config_cmd.py:75` — docstring example referencing `llm.cli_command` updated to `llm.config_dir`.

**Frontend:**
- `frontend/src/api/settings.ts:12` — TypeScript `LlmSettings` interface drops `cli_command: string`; adds `config_dir: string | null`.
- `frontend/src/components/settings/LlmSettings.vue:35-51` — delete the `cliCommand` computed, its `<input>` markup, and its inclusion in the `saveSettings` payload. Add `configDir` computed + input + payload entry.
- `frontend/src/components/settings/__tests__/LlmSettings.spec.ts:14` — drop `cli_command: 'claude'` from fixture; add `config_dir: null`. Add new test: "no `cli_command` input is rendered" (assert `wrapper.find('[data-test="cli-command-input"]').exists() === false`).

**Verification (single command, must return zero):**
```bash
grep -rn 'cli_command' backend/app/ frontend/src/ \
  | grep -v '/static/' \
  | grep -v '.pyc'
# Expected output: empty
```

This grep is added to `/verify` as a hard regression gate.
| FR-B08 | New service method `LLMPreflightService.check(provider: str) -> PreflightResult` where `PreflightResult` is a typed dict `{ok: bool, binary_resolved: bool, version: str | None, version_ok: bool, reason: str | None}`. Implementation: `shutil.which(binary_name)` → if found, run `<binary> --version` with 5s timeout, parse, compare to floor. Result cached for 60s in-process keyed by provider. |
| FR-B09 | New API route `GET /api/v1/llm/status` returns `{provider: str, preflight: PreflightResult}` for the currently configured provider. Used by Settings page banner + provider dropdown badges. |
| FR-B10 | `POST /api/v1/books/:id/summarize` calls `LLMPreflightService.check()` and returns `400 {error_code: "llm_provider_unavailable", detail: PreflightResult}` if `ok=False`. Job is NOT queued. |

### 6.2 Backend — queue & cancellation

| ID | Requirement |
|----|-------------|
| FR-B11 | New `JobQueueWorker` (asyncio task launched at app startup, lifecycle managed by `app.state`) polls every 2s for `ProcessingJob{status=PENDING}` ordered by `created_at ASC` and promotes the oldest to RUNNING only if no other RUNNING job exists. Promotion is atomic via: `UPDATE processing_jobs SET status='RUNNING', started_at=:now WHERE id=:id AND status='PENDING' AND NOT EXISTS (SELECT 1 FROM processing_jobs WHERE status='RUNNING')`. The worker re-checks `rowcount==1` before launching the run; if 0 (another worker tick or app instance promoted first), it loops. |
| FR-B11a | At app shutdown, the queue worker's polling loop is cancelled cleanly. Any subprocess running at that moment is left to its OS-level fate; the existing 24h-orphan-detection (`ProcessingRepository.get_orphaned_jobs()`) recovers stuck RUNNING rows on next startup. No new shutdown logic. |
| FR-B12 | Existing `_run_processing()` function is moved out of the API route's background-task launch and into the queue worker; the API route only creates the `ProcessingJob` row. |
| FR-B13 | New column `ProcessingJob.cancel_requested: bool default false`. Alembic migration adds the column. |
| FR-B14 | **Extend** existing `POST /api/v1/processing/{job_id}/cancel` (currently just marks DB row FAILED with no subprocess termination). New behavior: PENDING → delete row (no side effects, no SSE); RUNNING → set `cancel_requested=true` and immediately emit SSE `job_cancelling`; the queue worker's polling task detects the flag and sends SIGTERM (FR-B15). Returns 200 with `{job_id, status: "PENDING_REMOVED" | "CANCEL_REQUESTED" | "ALREADY_DONE"}`. The existing direct-FAILED behavior is removed. |
| FR-B14a | New API route `GET /api/v1/processing/jobs?status=PENDING,RUNNING` returns array of active jobs `[{job_id, book_id, book_title, status, scope, preset_name, started_at, progress, queue_position}]` ordered by `created_at ASC`. Used by `useJobQueueStore.connect()` to seed state on app mount before subscribing to SSE. Closes the page-refresh + SSE-disconnect gap. `queue_position` is 1-indexed (1 = next up). |
| FR-B15 | Cancel during RUNNING is **immediate**, not graceful: the queue worker's per-loop check on `cancel_requested` (reloaded between sections AND once via a separate asyncio task that polls every 1s during a section) triggers `proc.terminate()` immediately. SIGKILL after 5s if the subprocess hasn't exited (NFR-03). Current section is marked failed; already-completed sections are preserved (existing per-section commit semantics already handle this). Job marked `FAILED` with `error_message="cancelled"`. SSE `processing_failed` fires with `reason="cancelled"`. |
| FR-B15a | New SSE event `job_cancelling` fires the moment SIGTERM is sent: `{job_id, book_id}`. UI uses this to render a "Cancelling…" state in `<JobProgress>` and the persistent indicator across all open tabs. The terminal `processing_failed` event lands when the subprocess has actually exited. |
| FR-B16 | New SSE event `job_queued` emitted on PENDING job creation: `{job_id, book_id, queue_position, scope, preset_name}`. `queue_position` is 1-indexed (1 = next to run; 2 = one job ahead; etc.). Used by frontend to update Pinia queue state. |
| FR-B17 | New SSE event `job_promoted` emitted on PENDING→RUNNING transition: `{job_id, book_id}`. Listeners reuse this to swap their UI from "queued" to "live progress". |

### 6.3 Backend — section edit impact

| ID | Requirement |
|----|-------------|
| FR-B18 | New API route `GET /api/v1/books/:id/sections/edit-impact?section_ids=1,2,3` returns `{summaries_to_invalidate: int[], invalidate_book_summary: bool, summarized_section_count: int}`. Implementation: query `Summary.section_id IN ids` for non-stale; `invalidate_book_summary = (summarized_section_count > 0 AND book.book_summary_id IS NOT NULL)`. The endpoint takes only `section_ids` — no `op` query param; semantics are uniform ("these sections lose their original content"). Frontend skips this endpoint entirely for rename/set_type ops (no content change). |
| FR-B19 | All existing section-edit routes (`POST /merge`, `POST /split`, `PATCH /:id`, `DELETE /:id`) **always auto-mark** affected `Summary` rows as `is_stale=true` (existing pattern from re-import) — no opt-in flag. When the affected sections include any with a non-stale summary AND the book has a `book_summary_id`, the route additionally sets `Book.book_summary_id = None` AND transitions `Book.status` from `SUMMARIZED` back to `PARSED` so existing UI surfaces the "Re-summarize" CTA. In wizard-mode (no summaries exist yet) this is a no-op. |
| FR-B20 | `Book` rows with an active `ProcessingJob{status IN PENDING|RUNNING}` reject section-edit routes with 409. Frontend hides/disables Edit Structure when job in flight (E4). |

### 6.4 Frontend — Step 1 upload

| ID | Requirement |
|----|-------------|
| FR-F01 | Replace `apiClient.upload()` `fetch`-based path with an XHR-based path that exposes `xhr.upload.onprogress`. New `uploadBook(file, onProgress)` signature. |
| FR-F02 | New `<UploadFileCard>` component renders a per-file row with: filename, size, two-phase indicator (determinate bar 0–100% during upload, indeterminate spinner with "Parsing EPUB…" text after upload completes). Cancel button: enabled during upload (calls `xhr.abort()`); disabled with tooltip "Cannot cancel during parse" once parse begins. |
| FR-F03 | `<DropZone>` swaps to `<UploadFileCard>` on file pick; on parse error, card shows red error state + Retry button (returns to dropzone). |

### 6.5 Frontend — Step 2 / Edit Structure (shared component)

| ID | Requirement |
|----|-------------|
| FR-F04 | New `<StructureEditor :bookId :mode :sections>` component with `mode: 'wizard' | 'post-summary'`. |
| FR-F05 | Renders columns: checkbox, drag-handle, `#` (order_index+1), Title (inline-rename via click), Type (badge + click → set-type popover), Chars (`section.char_count.toLocaleString()`), Actions (split, delete). |
| FR-F06 | Drag-handle reorder: HTML5 drag API (no new dep). On drop, call `POST /api/v1/books/:id/sections/move` for the moved id. **Keyboard alternative:** focus a row's drag handle, Up/Down arrow keys move the row one slot at a time within the list (visual reorder is optimistic), `Enter` commits the new position via `POST /move`. `Escape` reverts. Announced via `aria-live` on the list container. |
| FR-F07 | Delete: click → row fades, one-shot Undo toast (5s); on undo → restore via reverse op (creates a new section with same content if backend already deleted, OR uses an undo stack maintained in `<StructureEditor>` that defers the actual `DELETE` call until toast expires). Pick the latter — defer the call. |
| FR-F08 | Multi-select toolbar appears above the list when ≥1 row selected. Buttons: **Merge** (≥2), **Bulk delete**, **Bulk set-type**. Merge button: opens dialog with title input (default = first selected section's title); on confirm, calls `POST /api/v1/books/:id/sections/merge` with the selected ids in document order. |
| FR-F09 | Disable Delete (per-row + bulk) when selection covers all sections (E3); tooltip "At least one section must remain." |
| FR-F10 | Split modal `<SplitModal>`: 3 tabs — **Auto-detect headings** (default; calls `GET /api/v1/books/:id/sections/:section_id/split-preview?mode=heading` returning `{candidates: [{title, char_count, first_line}]}`), **At paragraph** (rendered content with click-to-mark on `\n\n`-snapped points), **At cursor** (textarea selection → char position). Confirm calls existing `POST /split` route with mode + position. |
| FR-F11 | When `mode='post-summary'`, on save click, frontend calls `GET /sections/edit-impact?ids=...` and shows confirm dialog before the actual mutation route, passing `mark_summaries_stale=true`. When `mode='wizard'`, no confirm dialog (sections aren't summarized yet). |

### 6.6 Frontend — Step 3 preset + preflight

| ID | Requirement |
|----|-------------|
| FR-F12 | Step 3 fetches `GET /api/v1/llm/status` on mount. If `preflight.ok=false`, render inline red banner with `preflight.reason` + "[Fix in Settings → LLM]" link. **Disable Start Processing button.** |
| FR-F13 | On Start click, frontend calls `POST /api/v1/books/:id/summarize`. On 400 `llm_provider_unavailable`, render the same banner from response payload (defense-in-depth — handles the rare race where preflight passed but PATH changed). |

### 6.7 Frontend — Step 4 / persistent indicator

| ID | Requirement |
|----|-------------|
| FR-F14 | Extract a new `<JobProgress>` component (do NOT extend the existing `SummarizationProgress.vue`). `<JobProgress>` reads from `useJobQueueStore` and renders all states: `pending` (queued, with queue-position from `useJobQueueStore.queuePositionOf(jobId)`), `running` (live progress bar + counters), `cancelling` ("Cancelling…" overlay state, triggered by `job_cancelling` SSE), `completed` (success summary), `failed` (with `reason` distinguishing `cancelled` vs other errors). Used in Step 4 + persistent indicator + (eventually) BookDetailView. The existing `SummarizationProgress.vue` may be kept as a thin wrapper or deleted in a follow-up; out of scope to refactor now. |
| FR-F15 | Step 4 mid-job CTAs: **Open Book Now** (router push to `/books/:id`; wizard closes), **Dismiss → Library** (wizard closes; user routes themselves). |
| FR-F16 | Step 4 on `processing_completed`: card transforms into success summary (`{completed} sections summarized in {elapsed}, {failed} failures`) with primary "View Book" button. No auto-redirect. |
| FR-F17 | Step 4 when bound job is `status=PENDING`: render queued-state UI ("Queued — N books ahead. Will start when current finishes."). Auto-promotes to live UI on `job_promoted` SSE event. |
| FR-F18 | New `<PersistentProcessingIndicator>` component mounted in `AppShell` (`v-show` toggle). Visible when any `ProcessingJob{status IN PENDING|RUNNING}` exists. Renders current running job (title + progress bar + counters), "+N queued" badge, expand-collapse arrow. Expanded state shows mini queue list with [Cancel] per row. |
| FR-F19 | New Pinia store `useJobQueueStore` (extends or replaces `useSummarizationJobStore`) with `runningJob`, `pendingJobs[]`, derived getter `queuePositionOf(jobId): number | null`, subscribed to all SSE events. Single SSE connection per app session (do not open per-component); `connect()` called once from `AppShell.onMounted`. |
| FR-F19a | Cancel-running confirm dialog copy: title "Cancel summarization?", body "The current section will be lost, but already-summarized sections will be kept. This can't be undone.", primary button "Cancel summarization", secondary "Keep running". Cancel-PENDING confirm: title "Remove from queue?", body "'{book_title}' won't be summarized.", primary "Remove", secondary "Keep in queue". |

### 6.8 Frontend — Settings → LLM

| ID | Requirement |
|----|-------------|
| FR-F20 | `<LlmSettings>` removes the `cli_command` text input entirely. |
| FR-F21 | Adds new `<input type="text">` for `config_dir` with placeholder `~/.claude-personal` (when claude selected) or `~/.codex-personal` (when codex). Per-provider help text below. |
| FR-F22 | Provider dropdown options each show a status badge `✓ detected` / `✗ not found` from `GET /api/v1/llm/status` (called on mount + after every save). Also shows version inline when detected: `claude (2.1.123) ✓`. The `auto` option shows the resolved provider in parens, e.g., `auto (→ claude 2.1.123) ✓`, or `auto (→ none detected) ✗` if neither is on PATH. |
| FR-F23 | Persistent warning banner at top of Settings → LLM when `preflight.ok=false`. Banner clears immediately on successful save when the new config produces `ok=true`. |
| FR-F24 | "How to install" link below the banner, opens external docs URL (use `https://docs.anthropic.com/claude/cli` or equivalent — link is in the spec; final URL TBD by /plan). |

---

## 7. Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-01 | Performance | Preflight check must be cached for 60s within a process to avoid spawning `<binary> --version` on every request. |
| NFR-02 | Performance | `<StructureEditor>` must remain responsive (no input lag) for books with up to 200 sections. Drag-reorder uses native HTML5 drag, not a JS-driven library. |
| NFR-03 | Reliability | SIGTERM-based cancel must complete within 5s on a typical Claude/Codex CLI subprocess; if subprocess doesn't exit, send SIGKILL. |
| NFR-04 | Reliability | Queue worker must survive a single failed-to-promote attempt (DB error, stale data) and retry on next 2s tick. |
| NFR-05 | Accessibility | Persistent indicator's Cancel buttons must be keyboard-reachable and have `aria-label="Cancel queued job: {title}"`. Drag-reorder has keyboard alternative (up/down arrow keys when row focused). |
| NFR-06 | Compatibility | Minimum supported CLI versions: claude ≥ 2.1, codex ≥ 0.118. Below that, preflight returns `version_ok=false` with a non-blocking warning. |

---

## 8. API Contracts

### 8.1 `GET /api/v1/llm/status`

**Response (200):**
```json
{
  "provider": "claude",
  "preflight": {
    "ok": true,
    "binary_resolved": true,
    "version": "2.1.123",
    "version_ok": true,
    "reason": null
  }
}
```

**Errors:** none — always 200, payload encodes the failure modes.

### 8.2 `POST /api/v1/books/:book_id/summarize` (modified)

**Request:** unchanged from current shape (`preset_name`, optional `scope`, etc.).

**Response (200):** unchanged (`{job_id}`).

**New error response (400):**
```json
{
  "error_code": "llm_provider_unavailable",
  "detail": {
    "ok": false,
    "binary_resolved": false,
    "version": null,
    "version_ok": false,
    "reason": "The 'claude' CLI is not on this machine's PATH."
  }
}
```

Other errors unchanged (404 book missing, 409 in-flight job, 400 invalid preset).

### 8.3 `POST /api/v1/processing/{job_id}/cancel` (extended)

**Path:** existing route (currently flips DB to FAILED with no SIGTERM). Behavior is replaced.

**Response (200):**
```json
{ "job_id": 42, "status": "PENDING_REMOVED" }
```
or
```json
{ "job_id": 42, "status": "CANCEL_REQUESTED" }
```
or
```json
{ "job_id": 42, "status": "ALREADY_DONE" }
```

**Errors:** 404 (job not found).

### 8.3a `GET /api/v1/processing/jobs?status=PENDING,RUNNING`

**Response (200):**
```json
{
  "jobs": [
    {
      "job_id": 42,
      "book_id": 7,
      "book_title": "Playing to Win",
      "status": "RUNNING",
      "scope": "all",
      "preset_name": "practitioner_bullets",
      "started_at": "2026-04-30T14:22:01Z",
      "progress": { "completed": 8, "total": 25, "failed": 0, "skipped": 0 },
      "queue_position": 0
    },
    {
      "job_id": 43,
      "book_id": 8,
      "book_title": "Good Strategy Bad Strategy",
      "status": "PENDING",
      "scope": "all",
      "preset_name": "practitioner_bullets",
      "started_at": null,
      "progress": null,
      "queue_position": 1
    }
  ]
}
```

`queue_position`: 0 for the RUNNING job; 1, 2, ... for PENDING jobs in promotion order.

### 8.4 `GET /api/v1/books/:book_id/sections/edit-impact`

**Query params:** `section_ids` (comma-separated int list). No `op` param — semantics are uniform: "these section IDs are about to lose their original content."

**Response (200):**
```json
{
  "summaries_to_invalidate": [12, 13],
  "invalidate_book_summary": true,
  "summarized_section_count": 2
}
```

### 8.5 `GET /api/v1/books/:book_id/sections/:section_id/split-preview`

**Query params:** `mode` (`heading`/`paragraph`/`char`), `position` (only for `char` mode).

**Response (200):**
```json
{
  "mode": "heading",
  "candidates": [
    { "title": "Strategy as Choice", "char_count": 4200, "first_line": "What is strategy, really?" },
    { "title": "Where to Play", "char_count": 6800, "first_line": "Choosing your battlefield..." }
  ]
}
```

### 8.6 SSE event additions

Existing 7 events unchanged. New events on the same `/api/v1/processing/events` stream:

- `job_queued`: `{job_id, book_id, queue_position, scope, preset_name}`
- `job_promoted`: `{job_id, book_id}`
- `job_cancelling`: `{job_id, book_id}` — fired the moment SIGTERM is sent
- `processing_failed` (extended): existing payload + `reason: "cancelled" | "error" | ...`

---

## 9. Database Design

### 9.1 Schema changes

```sql
-- Alembic migration: v1_6a_processing_job_cancel.py
ALTER TABLE processing_jobs ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT 0;

-- Index for queue worker's "find next PENDING" query (idempotent if already present)
CREATE INDEX IF NOT EXISTS ix_processing_jobs_status_created
  ON processing_jobs (status, created_at);
```

### 9.2 No-op schema changes

- `LLMConfig.config_dir` lives in settings.yaml only — not in DB.
- `cli_command` removal from `LLMConfig` is a Python-side change; settings.yaml will silently shed the key on next save (or stay legacy until then; pydantic strips on read).

### 9.3 Indexes

Existing partial UNIQUE on `processing_jobs (book_id) WHERE status IN ('PENDING','RUNNING')` is sufficient. Queue worker's "find next PENDING" query benefits from `CREATE INDEX ix_processing_jobs_status_created ON processing_jobs (status, created_at);` if not already present (verify in /plan).

---

## 10. Frontend Design

### 10.1 Component hierarchy

```
AppShell
├── <RouterView>
│   ├── UploadView
│   │   └── UploadWizard
│   │       ├── DropZone | UploadFileCard       (Step 1)
│   │       ├── StructureEditor (mode='wizard') (Step 2)
│   │       │   └── SplitModal (lazy)
│   │       ├── PresetPicker + LLMPreflightBanner (Step 3)
│   │       └── JobProgress + Step4CTAs          (Step 4)
│   ├── BookDetailView
│   │   └── (existing reader)
│   └── EditStructureView                        ← NEW route /books/:id/edit-structure
│       └── StructureEditor (mode='post-summary')
│           ├── SplitModal (lazy)
│           └── EditImpactConfirmDialog
└── PersistentProcessingIndicator                ← NEW, v-show
    └── QueuePanel (expanded state)
```

### 10.2 State management

| State | Lives in |
|-------|----------|
| Upload progress (per-file) | Local component state in `UploadFileCard` |
| Wizard step + current bookId | `UploadWizard` local state |
| Section list during edit | `StructureEditor` local state, hydrated from API |
| Job queue (running + pending) | `useJobQueueStore` (Pinia) |
| LLM preflight result | `useSettingsStore` cached for 60s, refreshed on save |
| Toast notifications | `useUiStore` (existing) |

### 10.3 SSE wiring

Single SSE connection per session in `useJobQueueStore.connect()`, called from `AppShell.onMounted`. All events route through one handler that fans out to:
- Per-job listeners (Step 4, EditStructure for invalidation, BookDetailView's progress display)
- Global queue state (persistent indicator)

---

## 11. Edge Cases

| # | Scenario | Condition | Expected Behavior |
|---|----------|-----------|-------------------|
| E01 | No LLM provider available | `preflight.binary_resolved=false` | Step 3 shows banner; Start disabled; Settings page shows banner; `POST /summarize` returns 400 (defense in depth). |
| E02 | Provider version below floor | `preflight.version_ok=false` | Non-blocking warning banner ("Your claude version 2.0.5 is below the minimum 2.1; some features may not work"). Start NOT disabled. |
| E03 | Upload fails / parse yields zero sections | HTTP 4xx/5xx, or 200 with empty sections | UploadFileCard red error state + Retry. Existing `upload-error` message preserved. |
| E04 | Bulk delete would leave 0 sections | Selection covers all rows | Delete buttons (per-row + bulk) disabled with tooltip. Backend min-1 guard remains as defense. |
| E05 | Edit Structure during summarization | `ProcessingJob.status IN PENDING|RUNNING` for this book | Edit Structure link hidden/disabled in BookDetail toolbar. Direct nav to `/books/:id/edit-structure` shows "Wait for summarization to finish" empty state. Backend rejects with 409 (FR-B20). |
| E06 | Drop unsupported file type | Validation in DropZone | Existing error path unchanged. |
| E07 | Persistent indicator with zero jobs | `runningJob == null && pendingJobs.length == 0` | Indicator hidden via `v-show=false`. |
| E08 | Queue with > 5 books | 6+ pending | Indicator shows current + "+N queued" badge; expand panel scrolls (no truncation). |
| E09 | User cancels PENDING job | click Cancel on queued row | DELETE-equivalent removes the row; SSE `job_queued` reverse event NOT emitted (SSE is for additions; frontend updates locally). Persistent indicator updates. |
| E10 | User cancels RUNNING job | click Cancel on running row | Confirm dialog ("Cancel summarization? Sections summarized so far will be kept."). On confirm: `cancel_requested=true`; subprocess SIGTERMed within 5s; job FAILED with `reason=cancelled`. Step 4 (if open) transforms to FAILED state with cancel-aware copy. |
| E11 | Provider switched in Settings while job running | User switches claude→codex during an active job | The running job uses the provider it started with (already instantiated). New jobs use the new provider. Settings save succeeds. Banner reflects the new provider. |
| E12 | Browser refresh during Step 4 | active job for current book | Refresh lands user on `/books/:id` (NOT wizard); persistent indicator shows progress. |
| E13 | Browser refresh during PENDING wait | job is queued | Same as E12 — punt to BookDetailView. |
| E14 | Two tabs both open Step 3 of same book | concurrent Start clicks | One wins (existing partial UNIQUE index returns IntegrityError → 409 to second tab). Second tab shows 409 banner with "A job is already running for this book." |
| E15 | Edit-impact returns empty `summaries_to_invalidate` | sections were never summarized | Confirm dialog text omits the invalidation warning, just confirms the structural change. |
| E16 | Drag-reorder fails mid-flight | `POST /move` returns error | Snap row back to original position; toast error. Optimistic UI is allowed; reconcile on response. |
| E17 | Cancel-RUNNING UI lag during SIGTERM→exit window | up to 5s between `job_cancelling` event and final `processing_failed` | All open tabs render "Cancelling…" overlay state on `<JobProgress>` and persistent indicator. Cancel button disabled in this window. On `processing_failed`, transitions to FAILED state with cancel-aware copy. |
| E18 | Two app instances running concurrently (e.g., dev + serve) sharing same library.db | both queue workers polling | Atomic UPDATE-with-NOT-EXISTS query (FR-B11) prevents double-promotion. Worst case: a tick of churn; no data corruption. WAL mode already supports this. |

---

## 12. Configuration & Feature Flags

No new feature flags. Config additions:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLMConfig.config_dir` | `null` | Provider profile directory; injected as `CLAUDE_CONFIG_DIR` or `CODEX_HOME` in subprocess env. |

Removed:

| Variable | Reason |
|----------|--------|
| `LLMConfig.cli_command` | D1 — alias/shell-function foot-gun. Pre-release, no migration needed. |

---

## 13. Testing & Verification Strategy

### 13.1 Backend unit tests

- `test_llm_preflight_service.py`:
  - binary not found → `{ok: false, binary_resolved: false}`
  - binary found, old version → `{ok: true, binary_resolved: true, version_ok: false}` (non-blocking)
  - cache: two calls within 60s spawn `--version` once
- `test_claude_cli_provider.py`:
  - `config_dir` set → `subprocess.create_subprocess_exec` env contains `CLAUDE_CONFIG_DIR=<path>`
  - `config_dir` None → env unmodified
- `test_codex_cli_provider.py`:
  - `config_dir` set → env contains `CODEX_HOME=<path>`
  - subprocess argv includes `["codex", "exec", "--skip-git-repo-check", ...]`
  - schema-in-prompt injection still occurs
- `test_job_queue_worker.py`:
  - Promotes oldest PENDING when no RUNNING exists
  - Does NOT promote when RUNNING exists
  - Atomic UPDATE prevents double-promotion across two concurrent ticks
- `test_processing_cancel.py`:
  - PENDING cancel → row deleted
  - RUNNING cancel → `cancel_requested=true`; loop check exits; SIGTERM sent (assert via mock subprocess); job FAILED with `error_message="cancelled"`

### 13.2 Backend integration tests

- `test_summarize_route_preflight.py`: 400 with `error_code="llm_provider_unavailable"` when `which()` returns None (monkeypatch `shutil.which`).
- `test_section_edit_impact.py`: end-to-end against a seeded book with 5 sections, 2 summarized; merge sections 1+2 → impact shows summary 1 affected, book summary invalidated.
- `test_section_edit_blocks_during_job.py`: with active job, all section-edit routes return 409.

### 13.3 Frontend unit tests (Vitest)

- `StructureEditor.spec.ts`: render with 25 sections, multi-select 4+5, merge → fires correct API call with `[4, 5]`. Bulk delete disabled when all selected.
- `UploadFileCard.spec.ts`: progress prop drives bar; Cancel disabled in parse phase.
- `PersistentProcessingIndicator.spec.ts`: v-show false when no jobs; expanded state renders queue list.
- `LlmSettings.spec.ts`: no `cli_command` input rendered; config_dir input is present; provider badges reflect status payload.

### 13.4 E2E (Playwright MCP)

Verification scenarios (per `CLAUDE.md` Phase 4 instructions: spin up `bookcompanion serve --port 8765`, build frontend into `backend/app/static`):

1. **Happy path:** drop a small EPUB → see UploadFileCard progress → reach Step 2 → reorder + delete + merge → Step 3 (preflight passes) → Step 4 live progress → wait for completion → success card → click View Book.
2. **No-CLI path:** monkeypatch settings to set `provider=codex` with codex not on PATH → Step 3 banner appears → Start disabled → Settings page banner appears.
3. **Multi-book queue:** kick off Book A → upload Book B → Book B Step 4 shows queued state → wait for Book A to finish → Book B auto-promotes to live progress.
4. **Cancel running:** mid-Book-A run, click Cancel in persistent indicator → confirm dialog → job marked failed → success-with-cancel summary visible.
5. **Edit Structure post-summary:** navigate to `/books/:id/edit-structure` → split a summarized chapter → confirm dialog mentions summary invalidation → save → BookDetailView shows "Re-summarize" CTA.

### 13.5 Verification commands

```bash
# Hard regression gate: zero remaining cli_command references in source (FR-B01a, §6.1a)
test -z "$(grep -rn 'cli_command' backend/app/ frontend/src/ | grep -v '/static/' | grep -v '.pyc')" \
  && echo "OK: no cli_command references" \
  || (echo "FAIL: orphan cli_command references"; exit 1)

# Backend
cd backend && uv run python -m pytest tests/ -v
cd backend && uv run ruff check .

# Frontend
cd frontend && npm run test:unit
cd frontend && npm run lint
cd frontend && npm run type-check

# Build + serve for E2E
cd frontend && npm run build && rm -rf ../backend/app/static && cp -R dist ../backend/app/static
cd backend && uv run bookcompanion serve --port 8765 &
curl -sf http://localhost:8765/api/v1/health
# Then drive Playwright MCP through the 5 scenarios above
```

---

## 14. Rollout Strategy

Single-PR ship, no feature flag:
1. Backend changes + Alembic migration land first (migration is one ALTER TABLE — backward-compatible).
2. Frontend changes land in same PR (the dropped `cli_command` field would otherwise show an undefined-rendering bug if backend ships first).
3. Smoke locally per §13.5 before merge.

No rollback strategy beyond `git revert` — pre-release tool, single user.

---

## 15. Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `backend/app/config.py:23-34` | Existing code | LLMConfig has `extra="forbid"`, has `provider` field, has `cli_command` to remove |
| `backend/app/services/summarizer/claude_cli.py:102-124` | Existing code | Already passes `env=os.environ.copy()` — env-var injection is one line |
| `backend/app/services/summarizer/codex_cli.py:60-77` | Existing code | Currently `codex -p`; must switch to `codex exec --skip-git-repo-check` |
| `backend/app/api/routes/processing.py:29-348` | Existing code | Where to insert preflight; where to extract `_run_processing` for queue worker |
| `backend/app/db/models.py:282-309` | Existing code | ProcessingJob already has correct enum + partial UNIQUE; just add `cancel_requested` column |
| `backend/app/services/section_edit_service.py` | Existing code | All edit ops (merge/split×3/move/delete/set_type/undo) already implemented + tested |
| `frontend/src/components/upload/UploadWizard.vue` | Existing code | Step 4 is a static card today; needs SummarizationProgress reuse |
| `frontend/src/components/upload/StructureReview.vue` | Existing code | Read-only today; full rebuild as `StructureEditor` |
| `frontend/src/components/book/SummarizationProgress.vue` | Existing code | Reusable in Step 4 |
| `frontend/src/api/client.ts:101-105` | Existing code | Currently fetch-based; switch to XHR for upload progress |
| `frontend/src/api/processing.ts:85-117` | Existing code | SSE handler — extend with `job_queued`, `job_promoted` |
| Decision history `2026-04-25 (sim) constraint` | Workstream | localStorage rules don't apply (this feature uses settings.yaml + Pinia, not localStorage) |
| Decision history `2026-04-25 (spec) D11` | Workstream | Persistent overlays use `v-show` not `v-if` for first-interaction reliability |
| Decision history `2026-04-25 (spec) settings YAML pattern` | Workstream | `SettingsService.update_settings()` is the single mutation entry point — preserves all-or-nothing pydantic validation for `config_dir` |
| Live test on maintainer's machine 2026-04-30 | External | claude 2.1.123: `CLAUDE_CONFIG_DIR` works; codex 0.118.0: `CODEX_HOME` works + `codex exec` requires `--skip-git-repo-check` |

---

## 16. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| OQ1 | Confirm `codex exec` accepts the same `--model`, `--system-prompt`, stdin-prompt patterns we currently pass to `codex -p`. If not, the schema-in-prompt + stdin pattern may need to change shape. | /plan code-study | first task of Codex provider rework |
| OQ2 | Final URL for "How to install" links in the Settings banner (Anthropic claude CLI install page + OpenAI codex CLI install page). | Maneesh | during /plan |
| OQ3 | Drag-reorder: should we use HTML5 drag (no dep) or pull in `vuedraggable`? Spec defaults to HTML5 to avoid a dep, but `vuedraggable` gives keyboard accessibility for free. | /plan or design review | before implementation |

---

## 17. Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 (self-applied) | User mid-flight directive: "ensure no `cli_command` dependency remains in code." Recon found 14 source files with references. | Added FR-B01a + new §6.1a inventorying every file/line; added grep regression gate to §13.5. Renamed `SubprocessNotFoundError(cli_command)` → `(binary)` (FR-B07a) and logging-helper `cli_command` params → `binary` (FR-B07b). |
| 1 | F1: Cancel-running timing was vague ("checks between sections"). | Disposition: Immediate SIGTERM. Updated FR-B15 to spell out per-loop check + per-second poll task; current section becomes failed. Added NFR-03 SIGKILL-after-5s. |
| 1 | F2: Step 4 component reuse was waffly. | Disposition: Extract new `<JobProgress>`. Updated FR-F14 to enumerate all rendered states (pending/running/cancelling/completed/failed). |
| 1 | F3: No SSE for the SIGTERM→exit window meant cross-tab UI was inconsistent. | Disposition: Emit `job_cancelling`. Added FR-B15a + §8.6 event entry + E17 edge case. |
| 1 | F4: edit-impact `op` query param was unjustified. | Disposition: Drop `op`. Updated FR-B18 + §8.4 to use `section_ids` only. |
| 1 | F5: Book.status transition on book-summary invalidation was implicit. | Disposition: Always revert SUMMARIZED→PARSED. Updated FR-B19. |
| 1 | F6: `mark_summaries_stale` flag on edit routes was redundant. | Disposition: Drop flag, always auto-mark. Updated FR-B19. |
| 1 (self-applied) | F7 batch: keyboard reorder (Up/Down arrows + Enter), at-shutdown queue worker behavior, atomic-promotion SQL, queue position getter, cancel confirm copy. | Updated FR-F06 (keyboard), added FR-B11a (shutdown), expanded FR-B11 with explicit SQL, added FR-F19 `queuePositionOf` getter, added FR-F19a (confirm copy). Added E18 edge case for concurrent-instance polling. Added queue-worker index to §9.1. |
| 2 | F8: existing `POST /api/v1/processing/{job_id}/cancel` route shouldn't be duplicated. | Disposition: Reuse and extend. Updated FR-B14 to extend the existing route; updated §8.3 path. |
| 2 | F9: No way to seed Pinia store on app load — page-refresh leaves persistent indicator empty until next SSE event. | Disposition: Add GET listing endpoint. Added FR-B14a + §8.3a contract. Pinia store calls this in `connect()` before subscribing to SSE. |
| 2 | F10: queue_position numbering convention was implicit. | Disposition: 1-indexed for display, 0 for RUNNING. Updated FR-B16 + §8.3a + FR-B14a. |
| 2 (self-applied) | provider="auto" dropdown copy was undefined — what does the UI show when auto resolves to nothing? | Updated FR-F22 to enumerate `auto (→ claude 2.1.123) ✓` and `auto (→ none detected) ✗` cases. |
