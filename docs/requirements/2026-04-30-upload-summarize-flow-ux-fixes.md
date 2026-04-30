# Upload + Summarize Flow — UX Fixes & Structure Editor — Requirements

**Date:** 2026-04-30
**Status:** Draft
**Tier:** 2 — Enhancement (bundled with one Tier-1 config-bug fix)

## Problem

The "add a new book" wizard has four user-facing gaps that surfaced when the maintainer used the app on a fresh book (Playing to Win):

1. **Silent upload.** After picking a file, the dropzone shows no loader; the user almost re-uploaded thinking nothing happened.
2. **Read-only Structure Review with a missing UI.** Step 2 lists chapters but shows no per-chapter character count and no merge/split/reorder/rename/delete affordances — even though the backend `SectionEditService` is fully implemented (merge, split-at-heading/paragraph/char, move, delete, undo, set_type) and HTTP routes exist. The capability is wired in code but invisible in the UI.
3. **Static "processing started" screen.** Step 4 of the wizard is a card with a "View Progress" CTA. The backend already emits 6 SSE event types (`section_started/completed/skipped/failed/retrying`, `processing_started`) with `{section_id, title, index, total, ...}` and the BookDetailView already renders them via `SummarizationProgress.vue` — but the wizard step 4 doesn't reuse that component. Pure composition gap.
4. **Free-form `cli_command` input is a foot-gun and silently breaks summarization.** The Settings → LLM page exposes a free-form text input for `cli_command`. The user typed `claude-personal` (a zsh alias defined in `~/.zshrc`), which works in an interactive shell but does NOT work for non-interactive `subprocess.run(['claude-personal', ...])` — `subprocess` does not source rc files, so aliases and shell functions are invisible. Every section's call failed with "binary not found." The summarize job returned HTTP 200 and only logged per-section failures; the user got no clear signal that the configured CLI was the root cause.

   The right fix is **structural**: remove the free-form `cli_command` input entirely. Replace it with (a) a **provider** dropdown bound to auto-detected binaries (`claude` / `codex`), (b) `model`, and (c) a new **profile/config directory** field that gives the user the isolated-profile capability they were trying to express via the alias. Removing `cli_command` eliminates the alias-confusion class of bug.

   **Implementation note (codex vs claude have different profile mechanisms — confirmed by code recon 2026-04-30):**
   - `claude` CLI supports `--config-dir <path>` as a flag; today's `ClaudeCodeCLIProvider` does NOT pass it (gap to close as part of this work).
   - `codex` CLI uses the `CODEX_HOME=<path>` environment variable, not a flag.
   - The `LLMConfig` pydantic model currently has no `config_dir` field at all (and uses `extra="forbid"`), so existing YAML keys like `config_dir: ~/.claude-personal` are rejected at load — the user's intent has been silently ignored.
   - Therefore the user-facing setting is a single field (e.g., "Profile directory"), but the provider abstraction routes it correctly: `--config-dir` flag for claude, `CODEX_HOME` env var for codex. New `LLMConfig.config_dir: Path | None` field is required.

### Who & Why Now
**Persona:** the maintainer (Maneesh) using the tool as a daily driver to summarize his own non-fiction reading list. **Trigger:** first real-world end-to-end run on a fresh book exposed all four gaps in one session, blocking the workflow.

## Goals & Non-Goals

### Goals
- **G1.** During Step 1, the user always knows the upload + parse is in progress (no silent state).
- **G2.** During Step 2, the user can edit the parsed structure (per-section char count visible; merge / split / reorder / rename / delete / set-type all work) before committing to summarization.
- **G3.** The same structure editor is reusable from the BookDetailView, so the user can fix structure mistakes after summarization (with safe invalidation of affected summaries).
- **G4.** During Step 4, the user sees real-time per-section progress in the wizard itself, not a static "view progress" link.
- **G5.** Multiple books can be queued; the user can see the queue and current job at all times.
- **G6.** Settings → LLM cannot accept a value that will silently doom summarization. Free-form `cli_command` is removed; the user picks from auto-detected providers and only configures `config_dir` + `model`. If the chosen provider isn't actually installed, the user is told before any work is wasted.

### Non-Goals (explicit scope cuts)
- NOT supporting **parallel multi-book processing** in this iteration — jobs are queued and serialized. Reason: LLM CLI rate-limit risk and reasoning-complexity cost not justified at single-user scale.
- NOT building **CLI parity for section editing** (`bookcompanion edit sections <book>`). Reason: CLAUDE.md mentions it, but the command does not actually exist in `cli/commands/` and the maintainer's workflow is now web-first. Defer to a separate doc if it ever becomes needed.
- NOT exposing a free-form `cli_command` text input anywhere in the UI. Reason: it invites alias-and-shell-function bugs that look like settings issues but are subprocess-PATH issues. The `provider` enum (auto-detected to a real binary) plus `config_dir` covers every legitimate use case the free-form input was serving.
- NOT migrating existing user `cli_command` values to anything other than the provider default. Reason: any non-default value (like `claude-personal`) is by definition broken or shell-only; the migration silently drops it, logs a one-time warning, and surfaces the new `config_dir` field pre-filled if it was set.
- NOT redesigning the dropzone visual — only the loading-state behavior. Reason: scope discipline.
- NOT adding word-count or page-count to the section editor — only character count (matches what `SectionItem.char_count` already exposes). Reason: avoid recomputation; chars is the existing primitive.

## Solution Direction

A polish pass on the existing 4-step upload wizard plus a reusable structure-editor surface, plus a thin validation layer for the configured LLM CLI command, plus a queue-aware persistent processing indicator at the bottom of the app.

```
Step 1: Upload                    Step 2: Review Structure          Step 3: Preset           Step 4: Processing
┌─────────────────────┐           ┌──────────────────────────┐      ┌──────────────────┐    ┌──────────────────────────┐
│  [dropzone]         │  →        │  Editable section list:  │  →   │ Preset picker    │ →  │  Live progress card:     │
│   ↓ pick file       │           │   - per-row char count   │      │  + preflight CLI │    │  (live updates, %, count,│
│  ┌───────────────┐  │           │   - multi-select toolbar │      │    validation    │    │   current section)       │
│  │ book.epub     │  │           │   - merge / split modal  │      │                  │    │                          │
│  │ ▓▓▓▓▓░░░ 62%  │  │           │   - drag-handle reorder  │      │                  │    │  [Open Book Now]         │
│  │ Parsing…      │  │           │   - inline rename        │      │                  │    │  [Dismiss → Library]     │
│  └───────────────┘  │           │   - delete (min 1 guard) │      │                  │    │  on done: success card    │
└─────────────────────┘           └──────────────────────────┘      └──────────────────┘    └──────────────────────────┘
                                                                            │
                                                                            └── if configured CLI not on PATH →
                                                                                inline error + "Fix in Settings →" link
                                                                                (job NOT queued)

      Persistent processing indicator (always-visible bar at app bottom):
      ┌──────────────────────────────────────────────────────────────────────┐
      │ ⏳ Summarizing "Playing to Win"  ▓▓▓▓░░░░ 8/25  +2 queued  [▼]      │
      │   click ▼ → expand to show queued books with [Cancel] per row       │
      └──────────────────────────────────────────────────────────────────────┘
```

The same structure-editor surface is also rendered from the book-detail page under a new "Edit Structure" affordance, with a confirm dialog that warns about summary invalidation before any destructive edit.

## User Journeys

### Primary Journey 1 — Fresh book, happy path
1. User clicks "Add a Book" → opens wizard.
2. Drops `playing-to-win.epub` into dropzone.
3. Dropzone is replaced by a per-file card showing filename + size + a determinate progress bar during HTTP upload, then transitions to indeterminate spinner with "Parsing EPUB…" text. The card has a Cancel button — **active during upload** (aborts the HTTP request), **disabled once parse starts** with tooltip "Cannot cancel during parse." Parse is fast enough (typically seconds) that no cancel path is built.
4. On parse success, wizard advances to Step 2 (Structure Review).
5. User sees a list of 25 chapters with `# | Title | Type | Chars | Actions` columns and a multi-select toolbar above the list. The **per-row "Actions" cell** offers rename, delete, split, and a drag handle for reorder. The **toolbar** (active when 1+ rows selected) offers merge, bulk delete, and bulk set-type. Notices Chapter 24 is "About the Authors" and clicks the row's Delete (it disappears with a one-shot Undo toast).
6. User selects rows 4 and 5 (checkboxes), clicks "Merge" in the toolbar, confirms title in a small dialog. Merged contents are concatenated in **document order** (row 4 first, then row 5); the resulting section takes the position of the lowest-index member (slot 4) and order_indexes shift up.
7. User clicks "Continue" → Step 3 (Preset Picker).
8. Picks `practitioner_bullets`, clicks "Start Processing."
9. Wizard advances to Step 4. Inline progress card shows: progress bar (0/24), current section title, ETA, skip/fail counters (0/0). Two CTAs are visible: **"Open Book Now"** (jump to BookDetailView; progress continues there + in the persistent indicator) and **"Dismiss → Library"** (close wizard; watch via the persistent indicator). User watches first 3 sections complete.
10. User clicks "Dismiss → Library." Wizard closes; the persistent processing indicator at the bottom of the app shows the same progress and stays visible across views.
11. When the job finishes: if the user is still on Step 4, the card transforms into a success summary ("24 sections summarized in 6 minutes, 0 failures") with a primary "View Book" button — no auto-redirect. If the user has dismissed to the library or moved elsewhere, the persistent indicator fades out and a one-shot toast says "'Playing to Win' is ready" with a deep link to the book.

### Primary Journey 2 — Edit structure after summarization
1. From BookDetailView, user clicks "Edit Structure" (new tab/route).
2. The same structure-editor surface used in the upload wizard renders here. User wants to split Chapter 7 at a sub-heading.
3. User clicks "Split" on Chapter 7's row → opens modal.
4. Modal has 3 tabs: **Auto-detect headings** (default — shows "We found 3 ## headings; split into 4 sections?"), **At paragraph** (rendered content with click-to-mark split points snapped to `\n\n`), **At cursor** (precise char position via text selection).
5. User picks "Auto-detect" → preview shows the 4 resulting sections → clicks Confirm.
6. Pre-save confirm dialog: "This will invalidate 1 section summary. The book summary will also be invalidated because it was generated from these sections. Continue?" — the dialog only mentions the book summary if a book summary exists AND at least one of the affected sections was previously summarized. If the affected sections were never summarized, the book summary is preserved untouched.
7. User confirms. On save: affected section summaries are marked stale (existing eval-trace stale-marking pattern). The book summary is invalidated only if any affected section had a summary that contributed to it. Book status → PARSED, summary view shows "Re-summarize" CTA.

### Primary Journey 3 — Multi-book queue
1. User uploads Book A, runs through wizard, kicks off summarization.
2. While it's running, user uploads Book B. Wizard works normally; on Step 3 click "Start Processing," the job is **queued** (status=PENDING).
3. Step 4 of Book B's wizard shows: "Queued — 1 book ahead. Will start when current finishes." with a queue-position indicator. The wizard stays open if the user wants to wait, and **auto-updates seamlessly** to live progress when Book B promotes to running (same component, just different bound state).
4. The persistent processing indicator at the bottom shows current job + "+1 queued" badge; click ▼ expands a mini queue list with [Cancel] per queued row.
5. Book A finishes → Book B auto-promotes to running → both Book B's wizard step 4 (if still open) and the floating bar update in lock-step.

### Error Journeys

**E1. No LLM provider available.** The selected provider (e.g., `claude`) is not installed on this machine, or auto-detect found neither `claude` nor `codex`. On Step 3 "Start Processing" click, the wizard issues a server-side preflight that resolves the provider's binary on the host's executable PATH. If it does not resolve, the wizard shows an inline red banner: **"The 'claude' CLI isn't installed on this machine. [Fix in Settings → LLM]"** with installation hints. The Start button is disabled. Job is NOT queued.

**E1a. Same condition, settings page.** The Settings → LLM page shows a persistent warning banner at the top whenever the selected provider's binary does not resolve on PATH: "The 'claude' CLI isn't on this machine's PATH. Summarization will fail until this is fixed. [How to install]" The provider dropdown lists each option with a status indicator (✓ detected / ✗ not found).

**E1b. Migration: stale `cli_command` removal.** On first launch after the upgrade, any non-default `cli_command` in the user's settings.yaml is dropped and logged as a one-time info message. If `config_dir` was implied by the dropped value (e.g., `claude-personal` → `~/.claude-personal`), the user is shown a one-time toast: "We simplified the LLM settings. Your custom CLI was an alias that doesn't work outside an interactive shell — please re-confirm your config_dir in Settings → LLM."

**E2. Upload fails / parse yields zero sections.** Per-file card shows red error state with the existing `upload-error` message and a Retry button (returns to dropzone).

**E3. Section count would drop to zero on bulk delete.** Backend already enforces min-1 guard. Frontend disables the Delete button if the selection covers all sections, with a tooltip "At least one section must remain."

**E4. User edits structure during summarization.** "Edit Structure" route is hidden / disabled while job is RUNNING for that book. Tooltip: "Wait for the current summarization to finish before editing structure."

**E5. Drop unsupported file type.** Existing dropzone error path unchanged.

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|----------|-----------|-------------------|
| First-time visit, no books | `library is empty` | Library view's existing empty state unchanged. |
| Persistent indicator with zero jobs | no PENDING / RUNNING jobs | Bar is hidden. |
| Queue with > 5 books | 6+ queued | Bar shows current + "+N queued" with expandable list (no truncation). |
| User navigates away mid-upload | active HTTP upload | Cancel + warn-on-leave (existing browser dialog OK). Server-side: any partial upload is discarded. |
| Cancel a queued job | job in PENDING state | Job removed from queue, no side effects. Cancel a running job is a separate decision (OQ2). |
| User changes provider from `claude` (not installed) to `codex` (installed) | banner showing | On successful save the banner clears immediately. The provider dropdown's status indicator updates in lock-step. |
| User deletes a section that is the only summarizable section | (only one chapter, user clicks delete) | Backend rejects (min-1 guard); frontend shows the same disabled-tooltip message. |
| Browser refresh during Step 4 | job in flight | On wizard re-mount, infer current step from book status + active job; resume Step 4 view. (Or simpler: refresh always sends user back to BookDetailView with the floating bar — see OQ3.) |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Single requirements doc for all 4 issues | (a) one doc all 4; (b) split #4 as Tier-1 bug doc; (c) skip doc for #4 | One doc — same flow, will likely ship as one polish PR; pipeline overhead of splitting outweighs the tier-mismatch concern. |
| D2 | Step 1 upload feedback: per-file row with two-phase indicator | (a) per-file row two-phase; (b) inline overlay on dropzone; (c) full-card skeleton | Two-phase per-file row is the dominant industry pattern (Notion, Linear, Readwise) and gives an honest "upload" vs "parse" distinction. The dropzone-overlay pattern is too quiet for >2s parses. |
| D3 | Step 2 editor scope: full merge + split + reorder + rename + delete | (a) full editor; (b) char count + rename + delete only; (c) char count display only | Backend supports it all; front-loading the work avoids two design passes. The editor is also reused on BookDetailView so the iteration cost is paid once, not twice. |
| D4 | Editor reused in two surfaces: wizard step 2 + new BookDetailView "Edit Structure" tab | (a) reuse both; (b) wizard only; (c) wizard now, defer detail-view | Reuse wins long-term — single component, one set of tests. The post-summarization edit path is essential for users who realize a parse error after summarizing. |
| D5 | All three split modes exposed: heading, paragraph, char | (a) all three; (b) heading + paragraph; (c) paragraph only | Backend supports all three; one modal with tabs is cheaper than re-litigating which to ship. Heading-detect handles the 80% case; the other modes are escape hatches for messy parses. |
| D6 | Editing structure post-summarization: warn + auto-invalidate affected summaries; book summary invalidated only when at least one affected section had contributed to it | (a) always invalidate book summary; (b) only invalidate if affected sections were summarized; (c) leave book summary alone with a "possibly stale" banner | Option (b) is the most precise: merging two never-summarized sections doesn't dirty the book summary because it never read them. Option (a) over-invalidates and forces unnecessary re-summarization. Option (c) leaves data integrity to the user. Pre-save confirm dialog text adapts to whether the book summary will be invalidated. |
| D7 | Step 4: inline live progress + on-completion success card with manual "View Book" CTA (no auto-redirect); two mid-job CTAs ("Open Book Now" jumps to BookDetail with progress continuing, "Dismiss → Library" closes wizard with persistent indicator taking over) | (a) inline + auto-redirect on completion; (b) inline + on-completion success card with manual CTA; (c) toast first then auto-redirect | Auto-redirect can yank the user out of the wizard mid-thought. A success card with stats (sections summarized, elapsed time, failure count) gives closure and lets the user choose when to navigate. The two mid-job CTAs cover both "I want to start exploring partial results" and "I want to start another book" without forcing a single path. The persistent indicator at the app bottom stitches everything together regardless of which CTA the user picked. |
| D8 | Multi-book: serial queue with visible queue in the persistent indicator | (a) serial + queue; (b) parallel up-to-N; (c) block second upload; (d) defer | Serial avoids LLM CLI rate-limit complexity at single-user scale. Visible queue closes the "what's happening to my second upload?" gap. Parallel and per-job-cancel can come later if the maintainer's library habits demand it. |
| D9 | Remove the free-form `cli_command` text input from Settings → LLM. Replace with: (a) `provider` dropdown bound to auto-detected binaries (`claude` ✓ / `codex` ✓ / unavailable ✗), (b) profile/config directory text input (routed to `--config-dir` for claude, `CODEX_HOME` env var for codex), (c) `model` dropdown. Add `LLMConfig.config_dir` field. Wire `--config-dir` into `ClaudeCodeCLIProvider.cmd` and `CODEX_HOME` into `CodexCLIProvider.env`. Preflight at Step 3 + persistent banner on Settings page cover the "selected provider not installed" case | (a) keep `cli_command` + add validation; (b) remove `cli_command` entirely with per-provider profile wiring (this option); (c) keep `cli_command` but make it a dropdown of auto-detected binaries | Removing the input eliminates the alias/shell-function class of bug at the source. The user's actual need — an isolated profile — is served by per-provider profile wiring (`--config-dir` for claude is a real flag; `CODEX_HOME` for codex is the upstream-supported mechanism). Validation alone leaves the foot-gun in place. The dropdown alternative is essentially the same as the new `provider` dropdown. |
| D10 | Migration on upgrade: any non-default `cli_command` value is dropped with a one-time toast explaining the change | (a) drop silently; (b) drop with toast; (c) hard-error on first launch if value is non-default | Silent drops feel deceptive. Hard-error blocks app launch for what's now a settings-shape change. A toast acknowledges the user's prior config and points them to the new fields. |
| D11 | Per-row size shown as character count only (not word or page count) | (a) chars only; (b) chars + words; (c) chars + words + pages | Char count is already exposed by the existing section data model. Word and page require new derivation logic and bring no decision-relevant value over chars for "is this section big enough to summarize?" judgments. |
| D12 | Build the editor in the wizard rather than relying on re-import to fix bad parses | (a) editor; (b) editor + re-import as fallback; (c) re-import only | Re-import re-runs the same parser against the same EPUB and produces the same bad split. The editor catches structural errors once and fixes them once; re-import remains available as the nuclear option. |
| D13 | Affordance map for the structure editor: per-row vs. toolbar | (a) split as documented; (b) all controls in a per-row overflow menu; (c) all controls in a single toolbar | **Per-row controls:** rename, delete, split, drag-handle reorder. **Toolbar (active on multi-select):** merge, bulk delete, bulk set-type. Per-row covers single-section operations; toolbar covers operations that need a selection set. Matches Calibre/Scrivener norms. |
| D14 | Merge ordering: document-order, non-contiguous selections allowed, result takes lowest-index slot | (a) document-order, non-contiguous OK; (b) contiguous-only constraint; (c) selection-order | (a) is most flexible without surprising the user — the resulting section's content reads in the same order it appeared in the book, regardless of how the user ticked the checkboxes. Contiguous-only would block legitimate cases (e.g., merging three scattered "References" sections). Selection-order is unintuitive when the visible list is document-ordered. |
| D15 | Queued-job wizard: same component auto-promotes to live progress when its job runs | (a) auto-promote in place; (b) auto-redirect to library on queue | (a) keeps the user's mental thread — if they stayed on Step 4 to watch, they shouldn't have to navigate. The persistent processing indicator covers users who dismiss to library, so both paths are first-class. |

## Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| OQ1 | Verify upstream codex CLI version compatibility for `CODEX_HOME` profile isolation across the versions Book Companion supports. If a supported codex version doesn't honor `CODEX_HOME`, decide whether to (a) hide the profile field for codex, (b) document the version requirement, or (c) skip codex profile support entirely in this iteration. | Maneesh | before /spec |
| OQ1a | Should the profile field be exposed always, or only when the selected provider supports it (i.e., hide when codex is selected and we've decided not to support codex profiles)? | Maneesh | before /spec |
| OQ2 | Cancel a running job (vs. only queued jobs) — supported in this iteration or deferred? Backend likely needs a kill-subprocess code path; not free. | Maneesh | before /spec |
| OQ3 | Browser refresh during Step 4: do we restore wizard state, or always punt to BookDetailView? Latter is simpler and the floating bar makes it nearly equivalent. | Maneesh | before /spec |
| OQ4 | Per-file upload progress requires backend-side streamed-upload reporting; is XHR upload progress good enough (covers HTTP upload only, not parse)? Parse phase stays indeterminate. | Maneesh | before /spec |
| OQ5 | Should the BookDetailView "Edit Structure" surface be a new tab on the existing book page, a modal, or a dedicated route? Tab is most consistent with current IA; modal is faster to build. | Maneesh | before /spec |
| OQ6 | Does the "auto-detect headings" split-mode preview need to show full-text rendering of each candidate sub-section, or is a count + first-line preview enough? Affects modal complexity. | Maneesh | during /spec |

## Wireframes

Static HTML wireframes attached at [`docs/wireframes/2026-04-30_upload_summarize_flow_ux_fixes/`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/index.html). Open `index.html` in a browser, or click any file directly.

| # | Component | File | Maps to |
|---|-----------|------|---------|
| 01 | Step 1 — Upload (per-file card, two-phase indicator, Cancel rules) | [`01-step1-upload.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/01-step1-upload.html) | Issue #1 · G1 · D2 |
| 02 | Step 2 — Structure Editor (per-row + multi-select toolbar; rename / split / delete / drag / merge / bulk) | [`02-step2-structure-editor.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/02-step2-structure-editor.html) | Issue #2 · G2 · D3 · D13 · D14 |
| 03 | Split Modal — three modes: heading-detect / paragraph / cursor | [`03-split-modal.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/03-split-modal.html) | Issue #2 · D5 · OQ6 |
| 04 | Step 3 — Preset Picker + CLI Preflight Block | [`04-step3-preset-with-cli-preflight.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/04-step3-preset-with-cli-preflight.html) | Issue #4 · G6 · D9 |
| 05 | Step 4 — Live Progress + Completion Success Card | [`05-step4-live-progress.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/05-step4-live-progress.html) | Issue #3 · G4 · D7 |
| 06 | Persistent Processing Indicator (queue badge + expandable queue panel) | [`06-persistent-processing-indicator.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/06-persistent-processing-indicator.html) | Issue #3 + multi-book · G5 · D8 |
| 07 | Settings → LLM (persistent warning banner + inline save validation) | [`07-settings-llm-validation.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/07-settings-llm-validation.html) | Issue #4 · D9 · E1a/b |
| 08 | Edit Structure on Book Detail + invalidation confirm | [`08-edit-structure-post-summary.html`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/08-edit-structure-post-summary.html) | Issue #2 · G3 · D4 · D6 |

The wireframes commit visually to a few open questions (OQ1, OQ2, OQ4, OQ5, OQ6) at the wireframe level only — the open questions in the requirements doc remain authoritative and /spec can revisit each before locking design. See the Notes section in [`README.md`](../wireframes/2026-04-30_upload_summarize_flow_ux_fixes/README.md) for the wireframe-level commitments.

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 (self-applied) | F1: doc leaked component / API / function names (`<StructureEditor>`, `<SummarizationProgress>`, `POST /api/v1/llm/validate`, `shutil.which`) — implementation detail unsuitable for requirements | Replaced with generic "structure-editor surface", "live progress card", "persistent processing indicator", and "host's executable PATH" language across Solution Direction, E1, E1a, E1b. |
| 1 (self-applied) | F6: D12 was a wishy-washy detail-level decision ("could move to spec") | Repurposed D12 to capture the more decision-relevant choice — editor in the wizard vs. re-import as the only fix path — answering the skeptical-stakeholder critique (F7). Reorder-UX detail kicked to /spec. |
| 1 | F2: per-row vs. toolbar affordance ambiguity (Journey 1) | Disposition: Fix as proposed. Added affordance specifics to Journey 1 step 5 + new D13 capturing the split. |
| 1 | F3: merge-order ambiguity | Disposition: Fix as proposed (document-order, non-contiguous allowed, lowest-index slot). Updated Journey 1 step 6 + new D14. |
| 1 | F4: book-summary invalidation on post-summary structural edit | Disposition: Only invalidate book summary if affected sections were summarized. Updated Journey 2 step 6/7 + revised D6. |
| 1 | F5: queued wizard auto-promotion behavior | Disposition: Fix as proposed (in-place auto-update). Updated Journey 3 step 3 + new D15. |
| 2 (self-applied) | F8: D-rows out of numerical order | Reordered D6→D15 to read sequentially. |
| 2 (self-applied) | F9: implementation-name leaks remaining (`<StructureEditor>` in Journey 2 step 2; "floating ProcessingBar" / "ProcessingBar" in Journey 1 steps 10-11 and edge case) | Replaced with generic "structure-editor surface", "persistent processing indicator". |
| 2 (self-applied) | F13: edge-case row implied polling for banner clear | Rewrote to event-driven: banner clears on successful save (no polling needed). |
| 2 | F10: D7 vs Journey 1 step 11 conflict on completion behavior | Disposition: Toast + manual "View Book" CTA, no auto-redirect. Rewrote step 11 to split "still on Step 4 → success card" vs "elsewhere → toast"; rewrote D7 to match. |
| 2 | F11: Step 4 CTA semantics undefined | Disposition: Both CTAs visible with distinct meanings (Open Book Now = jump to BookDetail mid-job; Dismiss → Library = close wizard, persistent indicator takes over). Updated Journey 1 step 9 + D7 rationale. |
| 2 | F12: Cancel-button scope on per-file upload card | Disposition: Cancel active during upload only; disabled during parse with tooltip. Updated Journey 1 step 3. |
| 3 | F14: Maneesh's `claude-personal` was a zsh alias, not a binary. User asked whether dropping the free-form `cli_command` input is the right structural fix. Recon found `LLMConfig` has no `config_dir` field at all (despite YAML accepting it because of silent-ignore semantics), `ClaudeCodeCLIProvider` doesn't pass `--config-dir`, and codex uses `CODEX_HOME` env var (not a CLI flag). The whole "use config_dir" recommendation was on the wrong premise. | Pivoted Issue #4 design from "validate `cli_command` at write" to **"remove `cli_command` input entirely; replace with auto-detected provider dropdown + per-provider profile-directory routing"**. Updated Problem #4, Goals G6, Non-Goals (added two), E1/E1a/E1b, D9, D10, OQ1/OQ1a. Wireframe 07 rewritten end-to-end (no `cli_command` input; provider dropdown lists only detected binaries; profile field with per-provider help; new migration-toast state for legacy users; new codex-selected state). Wireframe 04 banner copy adjusted. |
