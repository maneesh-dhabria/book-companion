# Reader + Book Detail UX Fixes — Requirements

**Date:** 2026-04-30
**Status:** Draft
**Tier:** 2 — Enhancement (bundle of UX bugs and polish on existing surfaces)

## Problem

Once a book has been parsed and summarized, the next surfaces the user lives in — **the book detail page** and **the section reader** — accumulated 13 distinct UX problems that surfaced in a single end-to-end session on `/books/3`. Two are functional bugs (per-section retry blocked, broken images in summaries); the rest are polish: missing affordances, route state that doesn't survive reload, visual hierarchy that misreads as disabled, duplicated information, and reader-settings presets that look identical and partially don't apply.

These are not unrelated — they all fall on the post-summarization workflow ("I have a summarized book, now I want to read, navigate, and act on it") and most share the same components, so bundling avoids three separate small PRs touching adjacent code.

### Who & Why Now
**Persona:** the maintainer (Maneesh) using the tool as a daily driver. **Trigger:** first sustained reading session on a fully-summarized book exposed every gap in one sitting. The upload+summarize flow was just polished in [`2026-04-30-upload-summarize-flow-ux-fixes.md`](2026-04-30-upload-summarize-flow-ux-fixes.md); this doc is the natural continuation — same pattern, the next-stage surface.

### Confirmed Bugs (root-causes pinned during recon)

| # | Bug | Root Cause |
|---|-----|-----------|
| 1 | Per-section retry returns 409 "summarization job is already running" | The active-job guard on the book treats any in-flight job as blocking, regardless of scope. A section-scoped retry is rejected even when the only active job is a different scope on the same book (or a stale "running" row left over from a prior crash). |
| 5 | "Original" / "Summary" tab buttons read as disabled | The inactive tab is styled at half-opacity with disabled-style affordances, which mimics a real disabled button. Active tab uses accent color; inactive looks dimmed and unclickable. |
| 6 | Images broken in summary content (`/books/3/sections/47`) | The LLM emits markdown image refs in a legacy URL scheme that the in-app renderer doesn't resolve. The same URL-rewriting step that already runs on parsed section content does not run on summary content, so legacy refs stay broken. |
| 7 | Tab choice (summary vs original) doesn't survive reload or prev/next navigation | Tab state lives in a local component ref that resets on section change and is never reflected in the URL. |
| 9 | Book-detail action row is visually inconsistent | Five actions across three style tiers: Read = primary button, Export Summary + Copy as Markdown = secondary buttons, Customize and Edit Structure = inline text links. The mix reads as accidental. |
| 9.1 | "Summaries: 21 of 21 (0 pending, 0 failed)" header text is duplicated by the green "All 21 sections summarized" pill at the bottom | A static header counter and the dynamic progress component render the same fact twice. |
| 9.3 | "Copy as Markdown" fails with "Couldn't copy — try Export instead" | The handler bundles image blobs into the clipboard payload. Fails when image URLs 404 (same root cause as #6) or when the payload exceeds the browser's clipboard quota. |
| 10 | Reader-settings system presets are visually indistinguishable for typography, and Night / High-Contrast appear to do nothing | All 6 system presets ship with identical typography (same font, size, line-height, content width) — they differ only in theme. So clicking Night or High-Contrast only swaps the theme, and if the theme's color variables aren't fully defined in CSS, the click is a true no-op. |

### Confirmed Gaps (no bug; just missing affordance)

- **2.** No way to deep-link to an in-flight summarization job. Once the upload wizard closes, the user can't reload back into the live progress view.
- **3.** No CTA to open the focused book-summary view. The `/books/{id}/summary` route exists but is unreachable from the book detail page; users either find the inline render on overview or don't know there's a dedicated reading surface for the book summary at all.
- **4.** Section list (TOC) renders only title + a summary check mark on both the book detail page and the reader's TOC dropdown. Char count, summary status (✓/pending/failed), and compression ratio are all already in the data model but not displayed. The two components are distinct copies that don't share code.
- **8.** Font picker in reader settings is a native `<select>` — option labels are rendered in the system UI font, so the user can't preview the font.
- **9.2.** "Export Summary" hits the endpoint and triggers a browser download instantly. There's no visible "compiling…" feedback even on slow exports, so the action feels abrupt and the user wonders if they clicked correctly.

## Goals & Non-Goals

### Goals

- **G1 (functional bugs).** Per-section retry, image rendering, tab styling, button hierarchy, duplicate counter, copy-as-markdown failure, and theme-preset application are all corrected. None of the eight bugs in the table above survives this iteration.
- **G2 (route state).** The user can reload any reading or job-progress URL and land in exactly the same state — including which content tab is active and which job they were watching. Prev/next navigation respects the user's tab choice (if they were reading summaries, "next" lands on the next summary, not the next original).
- **G3 (book summary access).** From the book detail page, the user has a clear, primary affordance to read the book summary. The inline render is preserved or replaced — but the dedicated reading surface is reachable.
- **G4 (TOC clarity).** The section list shows enough metadata at a glance — character count, summary status (done / pending / failed), compression ratio when summarized — for the user to gauge a section's weight and pick where to start reading. The same component is reused on the book detail page and in the reader's TOC.
- **G5 (reader-settings variety).** System presets are visibly distinct in typography AND theme, not just theme. Clicking any preset (including Night and High-Contrast) produces an immediately visible change.
- **G6 (visual coherence).** The book detail page action row reads as one designed group, not five buttons of three styles. Power-user actions (Edit Structure, Customize) do not compete with primary CTAs.

### Non-Goals (explicit scope cuts)

- **NOT** building a fully-editable TOC component in this iteration. The existing structure editor (from the upload-summarize doc) covers the edit case; this iteration's TOC is read-with-metadata. **Reason:** keep scope tight; the structure editor is a different mental model (selection, merge, split) and shouldn't be smushed into the reader's nav.
- **NOT** redesigning the reader chrome (margins, sidebar, top bar). **Reason:** outside the immediate-bug scope; reader-settings popover was redesigned recently in `2026-04-30-reader-settings-popover-consolidation.md`.
- **NOT** adding a custom font-preview dropdown that loads the actual web font for every option. **Reason:** native `<select>` cannot style options; building a fully-custom dropdown is a bigger UX surface than this bundle deserves. The fix here is narrower (see D-row below).
- **NOT** adding parallel job execution or a generic "jobs" admin page. The `/jobs/{id}` route is a deep-link to a single job's progress, not a queue dashboard.
- **NOT** building artificial delays into the export flow. The fix for #9.2 is honest loading state during real latency, with a minimum visible duration so it doesn't flash. **Reason:** fake delays insult the user; honest loading earns trust.
- **NOT** re-summarizing existing books to fix the legacy image references. The migration is a server-side text rewrite of stored summary content, not an LLM re-run. **Reason:** re-summarizing wastes API spend and introduces summary drift; the rewriter is deterministic and idempotent.
- **NOT** removing the existing inline book-summary render from the overview page. The new "Read Summary" CTA opens the focused view; the inline render stays as a quick glance. **Reason:** discoverability + depth, not either-or.
- **NOT** keeping "Copy as Markdown" as a top-level button. It is demoted to a menu item under Export. **Reason:** simplifies the action row (G6) and isolates the failure mode.

## Solution Direction

A polish pass on the book detail header, the section reader, and the reader settings — with one server-side fix (image URL rewrite on summary writes + a one-shot migration) and one new route (`/jobs/{id}`).

```
                  Book Detail Page (/books/{id})                         Section Reader (/books/{id}/sections/{sectionId})
┌──────────────────────────────────────────────────────────┐   ┌─────────────────────────────────────────────────────────────┐
│  Title • Author                                          │   │  ◀ prev   [Original | Summary]   next ▶          ⚙ settings │
│                                                          │   │  (tabs: clear active vs inactive contrast, both clickable)  │
│  [ Read ]  [ Read Summary ]  [ Export ▾ ]    ⋯ menu     │   │  ?tab=summary persists; prev/next preserves tab             │
│   ↑primary   ↑primary         ↑split:                   │   │                                                             │
│                               • Download .md            │   │  [ rendered content with images that ACTUALLY render ]      │
│                               • Copy to clipboard       │   │                                                             │
│                                                          │   │  TOC dropdown (top-left, same component as overview list):  │
│  Inline book summary (existing render, preserved)        │   │   #  Title              Type    Chars   Summary  Compr.    │
│                                                          │   │   01 Foreword           front   4,231   ✓        18%       │
│  Sections (uses shared TOC component):                   │   │   02 Introduction       chap    8,402   ✓        21%       │
│   #  Title          Type    Chars   Summary  Compr.      │   │   03 ...                                                   │
│   01 Foreword       front   4,231   ✓        18%         │   └─────────────────────────────────────────────────────────────┘
│   02 Introduction   chap    8,402   ✓        21%         │
│   03 Strategy        chap   12,008  pending  —           │   Reader Settings popover:
│   04 ...                                                  │     ┌─────────────────────────────────────┐
│                                                          │     │ Light  Sepia  Dark  Night  Paper    │
│  Status pill: "All 21 summarized" (single source of      │     │ HC                                  │
│  truth — header counter removed)                         │     │ Each tile shows the actual          │
└──────────────────────────────────────────────────────────┘     │ typography + theme it applies       │
                                                                  │ (size, font, bg) at a glance        │
   Job progress deep-link (/jobs/{id}):                            │                                     │
   ┌─────────────────────────────────────────────────────┐         │ Font: [ Aa Georgia ▾ ]              │
   │ Summarizing "Playing to Win"  ▓▓▓░░ 12/24 sections │         │   options render IN their own font   │
   │ Current: "How Strategy Wins"                        │         └─────────────────────────────────────┘
   │ [Open Book] [Cancel]    (links to /books/{id})      │
   └─────────────────────────────────────────────────────┘
```

The bug fixes (#1, #5, #6, #7, #9.1, #9.3, #10) are each a localized change. The gaps (#2, #3, #4, #8, #9, #9.2) are visual / IA reshuffles. One backend change (rewrite `image:N` on summary write + one-shot migration) and one new shared component (TOC with metadata) are the only two non-trivial additions.

## User Journeys

### Primary Journey 1 — Read a fully-summarized book
1. User opens `/books/3` (Playing to Win, fully summarized).
2. Header shows the title, author, and three primary actions: **Read** (resume reader), **Read Summary** (open focused book-summary view), **Export ▾** (split-button: Download .md, Copy to clipboard).
3. A small overflow `⋯` menu collects power-user actions: Edit Structure, Customize Reader Settings.
4. Below the actions, the existing inline book summary render is preserved as a quick glance. Below that, the section list shows: `# | Title | Type | Chars | Summary | Compression`. User scans, sees Section 12 is the largest (18k chars), clicks it.
5. Reader opens `/books/3/sections/12?tab=summary` (default tab is summary if one exists). User sees clearly-styled active "Summary" tab and clearly-styled clickable "Original" tab — neither reads as disabled.
6. User reads the summary. Images render correctly (the markdown rewriter mapped `image:N` → `/api/v1/images/N` at write time). Clicks "next ▶" — lands on Section 13's summary tab (tab choice preserved).
7. User clicks "Original" to compare. URL updates to `?tab=original`. Reload preserves the view.

### Primary Journey 2 — Retry a single failed section
1. From `/books/3` user sees one section in the list with summary status = "failed" (red marker / count).
2. User clicks the failed section row → opens the reader → empty-state with "Retry summarization" button (existing).
3. User clicks Retry. Backend's job-active guard now considers job scope: a section-scoped retry is allowed because no full-book job is currently RUNNING for this book. Job is queued; the same SummarizationProgress component shows live progress just for this section.
4. Section completes. User reads the new summary inline.

### Primary Journey 3 — Watch a job from a deep link
1. User closes the upload wizard mid-job and navigates around the app. Persistent processing indicator (from the prior doc) shows the live job at the bottom.
2. User accidentally closes the browser, reopens, navigates to `/jobs/{id}` (URL pasted from elsewhere, or from a "view job" link in a notification).
3. The route renders a job-progress page with: book title, progress bar, current section, ETA, [Open Book] (links to `/books/{id}`), [Cancel] (kills the job).
4. On job completion, the route shows a "Done" summary card and a primary "Open Book" CTA. No auto-redirect.

### Primary Journey 4 — Reader settings: try a theme
1. User clicks the reader-settings gear → popover opens with 6 system preset tiles.
2. Each tile is **visually distinct** in both typography (size, line-height, font family) and theme (bg / fg / accent). The exact preset palette is a /spec-level choice (see OQ4) — the requirement here is that no two tiles look the same.
3. User clicks Night. Reader chrome flips to a dark theme; typography also shifts (size, font, or both) so the change is unambiguous and not a single-variable color swap.
4. User clicks the font picker. The dropdown is custom (not native `<select>`) so each option renders in its own font — Georgia option in Georgia, Inter option in Inter, etc. User picks one based on visual preview.

### Error Journeys

- **E1. Section retry blocked by an actually-running job.** If a full-book job is RUNNING (not just queued), section retries on that book remain blocked with a clearer message: "Wait for the current full-book summarization to finish, then retry." Tooltip on the disabled retry button explains.
- **E2. Stale RUNNING job rows.** If the active-job guard finds a row marked RUNNING but the worker process is gone (orphan from a crash), the guard treats it as not-running after a freshness check and the retry proceeds. Out of scope for design here — backend orphan-detection already exists for processing jobs and applies.
- **E3. Image rewriter fails for a section.** Rewriter is best-effort and idempotent. If a particular `image:N` reference resolves to no image (orphan reference), it falls back to a markdown link (`[alt](#)`) with a console warning rather than dropping the alt text. Reason: alt text is still useful context.
- **E4. /jobs/{id} for a finished or unknown job.** Finished job → render a static completion card with "Open Book" link. Unknown / deleted job → 404 page with a link back to library.
- **E5. Theme preset clicks but DOM theme variable isn't wired.** The fix in this iteration is to wire all theme variables (light, sepia, dark, night, paper, contrast) so this can't happen post-fix. Verification before close: each system preset visibly changes both bg and fg.
- **E6. Custom-font-preview dropdown fails to load a webfont.** Falls back to a system fallback for that one option; option label still readable (just not in the target font).

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|----------|-----------|-------------------|
| Section has no summary (never summarized) | section never went through summarization | TOC row shows "—" in Summary and Compression columns; reader defaults tab to Original; Summary tab shows the existing empty-state with "Summarize this section" CTA. |
| Section has a stale summary | summary marked stale after re-import or structure edit | TOC row shows "stale" badge; reader Summary tab shows a "this summary is stale, re-summarize?" banner above the content. |
| Compression ratio undefined | section never summarized or summary length unknown | TOC shows "—" not "0%". |
| Book has no book-level summary | no book-level summary has been generated yet | "Read Summary" button is disabled with tooltip "No book summary yet — summarize sections first" OR hidden entirely (see OQ1). Inline render section is replaced by an empty-state card. |
| User reloads `/books/{id}/sections/{sectionId}` with `?tab=summary` but section has no summary | mismatch | Falls back to Original silently; URL updates to `?tab=original`. |
| User reloads `/books/{id}` while a section retry is in flight | active job exists | Header shows the SummarizationProgress component (existing); the failed section's row updates to "running"; on completion, the row updates and the success pill recalculates. |
| Native browser blocks clipboard write (insecure context, denied permission) | clipboard API rejected | Toast: "Copy needs HTTPS or clipboard permission. Use Download .md instead." Same Export menu item is one click away. |
| Export takes < 200ms | small book | Loader does not flash — minimum visible duration ~250ms; if the response arrives faster, hold the loader to that floor before triggering download. |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | One Tier-2 bundle for all 13 items | (a) bundle; (b) split into 3 docs; (c) carve out #10 as Tier-1 bug | Same surface (post-summarization workflow), same components touched, single PR scope. Matches the precedent set by the 2026-04-30 upload-summarize bundle. |
| D2 | Per-section retry: backend guard considers job scope | (a) guard checks scope; (b) retry endpoint bypasses guard for scope=section; (c) keep current behavior (block) | (a) is the smallest correct fix — the guard is wrong, not the endpoint. (b) leaks job-state semantics into the route. The bug is "guard is too coarse," fix the guard. |
| D3 | Tab styling: drop `:disabled` opacity on inactive tab | (a) high-contrast inactive (slightly muted but clearly clickable); (b) underline-only active indicator; (c) leave as-is | (a) is the industry norm (Linear, Notion tabs). Inactive should read as "available," not "off." (b) would also work but the project already uses pill-style tabs elsewhere — consistency wins. |
| D4 | Image rewrite on summary write + one-shot migration for existing summaries | (a) rewriter at write + migration; (b) prompt fix only; (c) both rewriter and prompt | (a) is robust and deterministic. (b) is brittle — LLMs deviate from prompts. (c) is over-engineered when the rewriter already handles the transform reliably. Migration is one-shot and idempotent (skips already-rewritten content). |
| D5 | Tab state in URL via `?tab=summary\|original`; prev/next preserves the active tab | (a) URL state + nav-preserves; (b) URL state, nav resets; (c) localStorage state | (a) makes reload deterministic AND respects the user's reading mode through navigation. (b) breaks the natural "I'm reading the summaries" flow. (c) is invisible to URL sharing/copy-paste. |
| D6 | Job deep-link: dedicated `/jobs/{id}` route | (a) `/jobs/{id}`; (b) `/books/{id}?job=N`; (c) both | User chose dedicated route. It's the canonical way to reload into a specific job's progress and pairs with the persistent processing indicator's "view details" link. Querystring on book detail would mix two concerns (book vs job). |
| D7 | Book-detail action hierarchy: 3 primaries + overflow | (a) Read / Read Summary / Export as primary, Edit Structure & Customize in overflow; (b) all five buttons same tier; (c) Read primary, others secondary | (a) preserves the user's three actual top intents (read, read summary, export) and demotes power-user actions. The overflow is a clean visual escape hatch for the long tail. |
| D8 | "Copy as Markdown" demoted to a split-button menu under Export; underlying clipboard failure verified-then-fixed | (a) demote + verify-then-fix; (b) fix and keep top-level; (c) remove entirely | (a) addresses #9 (button clutter) AND likely fixes #9.3 incidentally — the clipboard payload likely failed because of the same legacy image-URL scheme as #6. After #6 ships, /spec verifies whether Copy MD still fails; if so, add a text-only fallback (drop image blobs from the ClipboardItem and retry with writeText). (c) is too aggressive — power users do clipboard things. |
| D9 | Single shared TOC component (read-with-metadata) used on book detail page + reader TOC dropdown | (a) shared component, read-only; (b) shared component with edit affordances; (c) keep two separate components | (a) addresses #4 with minimum scope. (b) collides with the structure editor (separate component, separate mental model) — combining them creates a multi-mode beast. (c) is the status quo and leaves the duplication. The component shows: `# / Title / Type / Chars / Summary status / Compression`. |
| D10 | Remove the static "Summaries: X of Y (...)" header counter; SummarizationProgress is the single source of truth | (a) remove static; (b) remove dynamic; (c) make them complementary | (a) — the dynamic component handles all states (in-progress, complete, failed) and animates with live updates. The static counter is duplicated info and goes stale during a job. |
| D11 | Loading state on Export with minimum visible duration ~250ms | (a) honest loader + min-duration floor; (b) artificial 1-2s delay; (c) no loader (current) | (a) gives the user feedback during real latency without lying about how long compilation takes. (b) is dishonest and feels slow on small books. (c) is the current abrupt experience. The 250ms floor avoids a flash on instant exports. |
| D12 | Reader presets: typography variety + theme variety | (a) all presets distinct in BOTH typography and theme; (b) typography only; (c) theme only (status quo) | (a) — the user perceives a preset as a complete look (size + spacing + theme + font), not just a color swap. Each preset gets a deliberate combination: e.g., Night = larger size + low-blue dark theme + sans; Paper = comfortable serif + generous line-height + cream theme; HC = even larger size + black/white. |
| D13 | Every preset theme has fully-defined color variables (no missing values that no-op the click) | (a) audit and define every theme; (b) only fix those visibly broken; (c) consolidate to fewer themes | (a) is the smallest fix that makes (D12) honest. The bug in #10 is partly that some theme variables aren't defined, so the click is a true no-op. Consolidation (c) is a separate design discussion not warranted by this bundle. |
| D14 | "Read Summary" is a top-level primary CTA AND the inline render is preserved | (a) both — CTA + inline render; (b) CTA replaces inline; (c) inline only (status quo) | (a) gives discoverability for first-time visitors (CTA is unmissable) and quick-glance utility for repeat visitors (inline saves a click). The two-channel approach matches Notion's "expand to focused view" pattern. |
| D15 | Custom font dropdown (not native `<select>`) so options preview in their own font | (a) build a small custom popover dropdown; (b) keep native `<select>`; (c) skip the feature | (a) is the only way to render per-option font preview in the browser. The popover is small (3-6 fonts), so the build cost is bounded. (b) precludes the feature. (c) drops a real UX win for low cost. |
| D16 | One-shot image-URL migration is idempotent and self-applies | (a) silent self-apply at the natural trigger point; (b) on-demand admin button; (c) re-summarize affected books | (a) is invisible to the user once it runs and skips on subsequent invocations. The transformation is deterministic. (b) is a discoverability foot-gun for a one-time fix. (c) is wasteful and introduces summary drift. The exact trigger point (boot, lazy-on-read, migration step) is a /spec choice — see OQ3. |

## Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| OQ1 | "Read Summary" CTA disabled vs hidden when no book summary exists. Disabled-with-tooltip is more discoverable; hidden is cleaner. | Maneesh | before /spec |
| OQ2 | The new `/jobs/{id}` route — do we also link to it from the persistent processing indicator's expanded queue (replacing the indicator's own "view" affordance), or is the indicator self-contained? | Maneesh | before /spec |
| OQ3 | Migration scope: rewrite all stored `summary_md` strings on first boot, or only the ones explicitly accessed? Whole-table is simpler; on-demand is lazier but doesn't need a long-running boot step. | Maneesh | during /spec |
| OQ4 | Theme presets variety (D12): does the maintainer want a specific spec of which preset has which size/font/spacing combination, or is "make them visibly different and reasonable" enough for /spec to fill in? | Maneesh | during /spec |
| OQ5 | Does the shared TOC component need to render differently on small/mobile widths? Reader TOC dropdown is a popover; book-detail page is a full-width table. Both? | Maneesh | during /spec |
| OQ6 | "Compression ratio" display format: % of original (e.g., "21%"), ratio ("1:5"), or raw chars saved? % is most readable; ratio is more accurate; chars-saved is most actionable. | Maneesh | during /spec |
| OQ7 | Custom font dropdown (D15): which fonts ship as built-in options? The current native select probably has 3-5; do we want to expand the list or just preview the existing ones? | Maneesh | during /spec |
| OQ8 | ~~Cancel semantics — kill subprocess vs. let current section finish~~ — **resolved 2026-04-30:** Cancel is **best-effort**: the in-flight LLM call for the current section completes, then the worker stops and the job is marked cancelled. Applies to both the upload-summarize doc's OQ2 and this doc's `/jobs/{id}` Cancel button. | resolved | — |

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 (self-applied) | F1: implementation-detail leaks — DB column names (`summary_id IS NULL`, `book.default_summary_id`), file path (`image_url_rewrite.py`), internal state strings (`RUNNING`, `data-theme`, `image:N`, `night`/`contrast`) — unsuitable for a requirements doc | Replaced with neutral user/observable language across bug-table item #6, item #10, edge-case table, D4, D13, D16. |
| 1 (self-applied) | F2: Journey 4 step 2 enumerated specific (Light/Sepia/Dark/Night/Paper/HC) typography pairings, pre-empting OQ4 | Softened to "visually distinct in typography and theme; exact palette is a /spec-level choice". Step 3 likewise generalized away from naming specific theme tokens. |
| 1 | F3: clarify whether the inline-render-on-book-3 verification is a separate bug worth scoping | Disposition: Drop. The new "Read Summary" CTA covers the access gap; investigate only if the user reports it again post-fix. No doc change. |
| 1 | F4: should we explicitly fix `clipboard.write` failure or rely on #6 fixing it incidentally? | Disposition: Verify-then-fix. Updated D8 to capture: after #6 ships, /spec verifies; if Copy MD still fails, add a text-only fallback (drop image blobs, retry `writeText`). |
| 1 | F5: "Read Summary" CTA + inline render coexistence — over-engineered? | Disposition: Keep both as documented. D14's rationale stands; no change. |
| 1 | F7: OQ8 (Cancel semantics) was duplicate-asked across two open docs | Disposition: Resolve now as best-effort (current section finishes, then worker stops). OQ8 marked resolved; same resolution applies to the upload-summarize doc's OQ2. |
| 2 (self-applied) | F8: residual implementation-detail leaks (`RUNNING`, `:disabled`, `SummarizationProgress`, `navigator.clipboard.write()`, `ClipboardItem`, `image:N`, `summary_md`) in bug table rows 1, 5, 9.1, 9.3 and Non-Goals | Replaced with neutral language across all six locations. |
| 2 (self-applied) | F9: Confirmed-Gap row #3 still mentioned "(Inline render also needs verification — user did not see it on book 3.)" — contradicts F3 disposition (drop) | Removed the trailing parenthetical. |
