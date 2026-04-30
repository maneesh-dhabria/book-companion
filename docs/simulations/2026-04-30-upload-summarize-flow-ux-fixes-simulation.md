# Upload + Summarize Flow — UX Fixes — Simulation

**Date:** 2026-04-30
**Status:** Final
**Spec:** [`docs/specs/2026-04-30-upload-summarize-flow-ux-fixes-spec.md`](../specs/2026-04-30-upload-summarize-flow-ux-fixes-spec.md)

---

## 1. Scope

**In scope (mirrors spec):**
- Backend: `LLMConfig` (drop `cli_command`, add `config_dir`); `ClaudeCodeCLIProvider` + `CodexCLIProvider` env-var injection + `codex exec --skip-git-repo-check`; `LLMPreflightService` + GET/POST status routes; `JobQueueWorker` + global single-RUNNING serialization; cancel-running with SIGTERM/SIGKILL; section-edit-impact + split-preview routes; alembic ALTER + INDEX
- Frontend: XHR upload progress; full StructureEditor (per-row + multi-select toolbar); SplitModal (3 modes); `<JobProgress>` extracted; `<PersistentProcessingIndicator>`; new `EditStructureView` route; Settings → LLM rewrite (no `cli_command`, add `config_dir` + Re-detect)
- Pinia: `useJobQueueStore` with single SSE connection + 5-step seed sequence

**Out of scope (deferred):**
- CLI parity for the new `config_dir` field (set via `bookcompanion config set` only)
- Parallel multi-book processing (queue is strictly serial)
- Browser-refresh wizard-state restoration (refresh punts to BookDetailView)
- `cli_command` migration toast (tool unreleased; no migration ceremony needed)

**Companion specs:** none.
**Anticipated downstream:** none.

---

## 2. Scenario Inventory

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | Fresh book happy path | Spec §5.1 | happy |
| S2 | Edit structure post-summarization with stale-summary invalidation | Spec §5.2 | happy |
| S3 | Multi-book serial queue with auto-promote | Spec §5.3 | happy |
| S4–S21 | Edge cases E01–E18 (folded into spec) | Spec §11 | edge |
| S22 | Codex user runs first job — verifies `codex exec --skip-git-repo-check` | Variant | happy |
| S23 | provider=auto with both CLIs installed — auto resolution + UI badge | Variant | happy |
| S24 | User installs claude AFTER preflight cached — 60s stale cache | Adversarial | timing |
| S25 | CLI binary `rm`'d mid-job — repeated SubprocessNotFound | Adversarial | failure |
| S26 | Two browser tabs seeded via GET /jobs while a job_completed fires DURING the call | Adversarial | timing |
| S27 | SSE reconnect drops a `job_promoted` event; Pinia stays in PENDING | Adversarial | retry |
| S28 | Cancel during PENDING→RUNNING promotion window | Adversarial | concurrency |
| S29 | XHR upload partial: network drops at 60% | Adversarial | failure |
| S30 | SSE delivers `job_promoted` BEFORE `processing_started` (out of order) | Adversarial | ordering |
| S31 | Drag-reorder fails, user immediately drags same row again | Adversarial | concurrency |
| S32 | Edit-structure during PENDING (queued but not running) | Model-driven | boundary |
| S33 | Cancel-RUNNING SIGTERM hangs subprocess; SIGKILL after 5s | Model-driven | timing |
| S34 | Provider switched in Settings while job RUNNING | Spec E11 + Model-driven | concurrency |
| S35 | Two app instances share library.db both polling queue | Spec E18 | concurrency |
| S36 | Inline rename: empty / 500-char / whitespace-only | Adversarial | input |
| S37 | config_dir set to non-existent path | Adversarial | input |
| S38 | Book with 200 sections — drag responsiveness | Adversarial | boundary |
| S39 | User completes wizard, returns to library, reopens wizard for same book | Model-driven | edge |
| S40 | Refresh during EditStructureView mid-unsaved-edit | Model-driven | edge |
| S41 | User on Step 4 (queued) closes browser; reopens later | Model-driven | retry |
| S42 | Edit-impact GET hangs; user clicks confirm anyway | Adversarial | timing |
| S43 | Multiple SSE events for one section land in same 16ms tick | Adversarial | ordering |

---

## 3. Coverage Matrix (key gaps)

Below: only scenario steps that exposed gaps. All other steps mapped cleanly to existing spec FRs.

| Scenario | Step | Spec Artifact (post-patch) | Status |
|----------|------|--------------------------|--------|
| S22.1 | Verify `codex exec` accepts stdin prompt + `--model` flag | OQ1 (deferred to /plan) | open question |
| S24.2 | User installs CLI; needs fast re-detect | FR-B08a + FR-F23a + §8.1a | ✓ patched |
| S25.3 | Repeated SubprocessNotFound mid-job | FR-B15b (2-strike abort) | ✓ patched |
| S26.2 | Seed-fetch vs SSE-subscribe ordering | FR-F19b (5-step connect) | ✓ patched |
| S27.2 | SSE reconnect re-seed | FR-F19b (sequence repeats on error/close) | ✓ patched |
| S28.1 | Atomic cancel-vs-promotion | FR-B14 (atomic DELETE WHERE PENDING) | ✓ patched |
| S30.1 | Cross-coroutine SSE FIFO | FR-B11 + B16 + B17 (emitter pinning) | ✓ patched |
| S33.1 | SIGTERM→SIGKILL→cleanup | §6.4 pseudocode | ✓ patched |
| S34.1 | Provider re-instantiation per-job | FR-B12 + D18 | ✓ patched |
| Split preview endpoint | API contract had no FR | FR-B18a | ✓ patched |

---

## 4. Artifact Fitness Findings

### Bucket 1 (Data & Storage)
- `processing_jobs.cancel_requested BOOLEAN NOT NULL DEFAULT 0` — fitness OK
- `ix_processing_jobs_status_created` index on (status, created_at) — supports queue-worker scan, OK
- No data-shape gaps surfaced.

### Bucket 2 (Service Interfaces)
- `GET /llm/status` — clean
- `POST /llm/recheck` — added (G1)
- `GET /processing/jobs` — clean
- `GET /sections/edit-impact` — clean
- `GET /sections/:id/split-preview` — orphan FR fixed (G6)
- `POST /processing/:job_id/cancel` — race-safety patched (G3)
- All SSE events extended with `last_event_at` for reconciliation (G2)

### Bucket 3 (Behavior / state machines)
- ProcessingJob: PENDING → RUNNING → COMPLETED|FAILED. Cancel branches: PENDING → row deleted; RUNNING → cancel_requested=true → FAILED(reason=cancelled). All branches reachable; no dead states.
- Book: SUMMARIZED → PARSED transition on book-summary invalidation (FR-B19) — clean.

### Bucket 4 (UI)
- `<JobProgress>` states: pending, running, cancelling, completed, failed, **reconnecting** (added G9). All needed UI states covered.
- Persistent indicator: visible/hidden + reconnecting badge — clean.
- StructureEditor: drag with keyboard alt + inline rename validation + bulk-delete guard — clean post-patch.

### Bucket 6 (Operational)
- Queue worker observability — added FR-B23 (structlog logs at startup, promote, cancel-detect, shutdown).
- No metrics infrastructure — accepted (single-user tool).

---

## 5. Cross-Reference (UI ↔ API)

| # | Interaction | Trigger | Endpoint | Status |
|---|---|---|---|---|
| W1 | Drop file | DropZone | POST /books/upload | ✓ existing |
| W2 | Upload progress | UploadFileCard | XHR onprogress (FR-F01) | ✓ |
| W3 | Cancel upload | Cancel button | xhr.abort() | ✓ |
| W4 | Load sections | StructureEditor mount | GET /books/:id/sections | ✓ existing |
| W5 | Inline rename | StructureEditor | PATCH /sections/:id (FR-B21 validation) | ✓ |
| W6 | Drag reorder | StructureEditor | POST /sections/move (FR-F25 retry queue) | ✓ |
| W7 | Delete (with undo) | StructureEditor | DELETE /sections/:id (deferred 5s) | ✓ |
| W8 | Bulk merge | Toolbar | POST /sections/merge | ✓ |
| W9 | Split | SplitModal | POST /sections/split | ✓ |
| W10 | Split preview | SplitModal | GET /sections/:id/split-preview (FR-B18a) | ✓ patched |
| W11 | Bulk set-type | Toolbar | PATCH /sections/:id (loop) | ✓ |
| W12 | Edit-impact | EditStructure save | GET /edit-impact (FR-F28 timeout) | ✓ |
| W13 | Preflight banner Step 3 | Step 3 mount | GET /llm/status | ✓ |
| W14 | Re-detect button | Settings banner | POST /llm/recheck (FR-F23a) | ✓ |
| W15 | Start summarize | Step 3 button | POST /summarize | ✓ |
| W16 | Job progress | Step 4 + indicator | SSE /processing/events + GET /processing/jobs | ✓ |
| W17 | Cancel job | Indicator button | POST /processing/:id/cancel | ✓ |
| W18 | Settings preflight | Settings mount | GET /llm/status | ✓ |
| W19 | Save settings | Settings save | PATCH /settings (cache invalidation FR-B08a) | ✓ |

**Reverse scan:** every endpoint has a UI consumer; every UI action has an endpoint. No orphans post-patch.

---

## 6. Pseudocode

### Flow 1: Cancel-RUNNING

Spec'd inline as §6.4 of the spec (per G4 disposition). Includes DB calls, state transitions, error branches, concurrency notes. See spec.

### Flow 2: SSE store seed-and-reconnect (FR-F19b)

```
ASYNC FUNCTION useJobQueueStore.connect():
  state.connectionState = "connecting"
  buffer = []
  bufferMode = true

  # Step 1: open SSE; route to buffer
  eventSource = new EventSource("/api/v1/processing/events")
  eventSource.onmessage = (evt) => {
    IF bufferMode:
      buffer.push(evt)
    ELSE:
      applyEvent(evt)
  }
  eventSource.onerror = () => {
    state.connectionState = "reconnecting"
    eventSource.close()
    sleep(backoff_ms())   # 1s, 2s, 4s, max 30s
    connect()             # restart from step 1
  }

  # Step 2: seed
  seed = await fetch("/api/v1/processing/jobs?status=PENDING,RUNNING").json()

  # Step 3: apply seed
  state.runningJob = seed.jobs.find(j => j.status === "RUNNING") || null
  state.pendingJobs = seed.jobs.filter(j => j.status === "PENDING")
  seedTimestamps = Map(seed.jobs.map(j => [j.job_id, j.last_event_at]))

  # Step 4: drain buffer
  FOR evt IN buffer:
    seedTs = seedTimestamps.get(evt.job_id)
    IF seedTs AND evt.last_event_at <= seedTs:
      CONTINUE   # already represented in seed
    applyEvent(evt)

  # Step 5: live mode
  bufferMode = false
  state.connectionState = "connected"
```

**State transitions (frontend):**
- `disconnected → connecting → connected` (happy path)
- `connected → reconnecting → connecting → connected` (recovery)

**Error branches:**
- Fetch failure on seed → log + retry with backoff (treat as connection error)
- SSE error → close + reconnect with exponential backoff (1, 2, 4, 8, 16, 30s cap)
- Buffer overflow (e.g., 1000 events while disconnected) → cap buffer at N=200; if exceeded, force a fresh seed instead of replaying

**Concurrency notes:**
- Single-tab Pinia store; no cross-tab synchronization. Each tab independently reconnects.
- `bufferMode` is a tab-local boolean; no race because all SSE event handling is single-threaded (event loop).

---

## 7. Gap Register

| # | Gap | Exposed By | Severity | Disposition |
|---|---|---|---|---|
| G1 | Preflight 60s cache stale after install | S24 | significant | Apply patch (FR-B08a, FR-F23a, §8.1a) |
| G2 | SSE seed/reconnect ordering not spec'd | S26 + S27 | significant | Apply patch (FR-F19b + last_event_at on all SSE) |
| G3 | Cancel vs promotion race | S28 | significant | Apply patch (FR-B14 atomic DELETE) |
| G4 | SIGTERM→SIGKILL→cleanup pseudocode missing | S33 | significant | Apply patch (§6.4 pseudocode) |
| G5 | Provider re-instantiation timing unspecified | S34 | significant | Apply patch (FR-B12 + D18) |
| G6 | §8.5 split-preview has no FR-B | W-10 | significant | Apply patch (FR-B18a) |
| G7 | Cascade on missing CLI mid-job | S25 | minor | Apply patch (FR-B15b) |
| G8 | SSE event ordering across coroutines | S30 + B-2.2 | minor | Apply patch (emitter pinning in FR-B11/B16/B17) |
| G9a | Drag concurrent-failure handling | S31 | minor | Apply patch (FR-F25) |
| G9b | Inline rename input validation | S36 | minor | Apply patch (FR-F26 + FR-B21) |
| G9c | config_dir non-existent path | S37 | minor | Apply patch (FR-B22) |
| G9d | beforeunload guard during 5s undo window | S40 | minor | Apply patch (FR-F27) |
| G9e | Edit-impact GET timeout/spinner | S42 | minor | Apply patch (FR-F28) |
| G9f | SSE-disconnected UI badge | B-4.1, B-4.2 | minor | Apply patch (FR-F19c) |
| G9g | Queue worker observability | B-6.1 | minor | Apply patch (FR-B23) |
| G10a | Wizard duplicate-book guard | S39 | minor | Accept as risk |
| G10b | Missed-completion notification when browser closed | S41 | minor | Accept as risk |
| G10c | Backend partial-upload cleanup spec | S29 | minor | Accept as risk |

---

## 8. Accepted Risks

- **G10a (S39 — wizard duplicate-book):** existing app behavior allows uploading the same EPUB twice, creating a duplicate Book row. Out of scope here; this spec doesn't change upload semantics. Future spec can add a content-hash dedup check if it becomes a real friction point.
- **G10b (S41 — missed completion):** if the user closes the browser before SSE delivers `processing_completed`, the on-completion toast doesn't fire. Persistent indicator on next app open will show the job as completed (via GET /jobs seed not including COMPLETED), but no "ready" notification. Acceptable for a single-user local tool.
- **G10c (S29 — partial upload cleanup):** XHR abort or network drop mid-upload may leave a partial file on the backend. Existing upload behavior unchanged; CLAUDE.md / requirements doc say "any partial upload is discarded" but the spec doesn't pin the cleanup mechanism. Trust existing implementation; revisit if /verify finds orphan files.

---

## 9. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| OQ1 (carried) | Confirm `codex exec` accepts `--model`, stdin-prompt, etc. as `codex -p` does | /plan code-study | first task of Codex provider rework |
| OQ2 (carried) | Final URLs for "How to install" links | Maneesh | during /plan |
| OQ3 (carried) | Drag-reorder: HTML5 native vs vuedraggable dep | /plan or design review | before implementation |

No new open questions surfaced by simulation.

---

## 10. Spec Patches Applied

All applied to `docs/specs/2026-04-30-upload-summarize-flow-ux-fixes-spec.md` during this simulation:

| # | Section/FR | Change |
|---|---|---|
| 1 | FR-B08a | Cache invalidation rules added |
| 2 | §8.1a | `POST /llm/recheck` contract added |
| 3 | FR-F23a | Re-detect button added |
| 4 | FR-B11 | Emitter pinning + `last_event_at` |
| 5 | FR-B12 + D18 | Provider re-instantiation per-job |
| 6 | FR-B14 | Atomic cancel DELETE rewrite |
| 7 | FR-B15 + FR-B15b | Reference §6.4; fail-fast on missing CLI |
| 8 | FR-B16 + FR-B17 | Emitter location + `last_event_at` on SSE |
| 9 | FR-B18a | Split-preview FR added |
| 10 | FR-B21/B22/B23 | Title validation, config_dir auto-create, observability |
| 11 | FR-F19b/F19c | 5-step SSE connect + reconnect; reconnecting badge |
| 12 | FR-F25/F26/F27/F28 | Drag retry queue, rename validation, beforeunload guard, edit-impact timeout |
| 13 | §6.4 | Cancel-RUNNING flow pseudocode (DB / state / error / concurrency) |
| 14 | D18 + D19 | Provider per-job + SSE seed sequence decisions |
| 15 | Review Log | Simulation pass logged |

---

## 11. Review Log

| Loop | Findings | Resolution |
|------|----------|-----------|
| 1 | Single review pass per skill default. All 18 gaps disposed (15 patched, 3 accepted). 5 review checks pass: scenario completeness ✓, bucket completeness ✓, cross-reference both directions ✓, every gap has disposition ✓, every blocker/significant has applied patch ✓. | Exit. |
