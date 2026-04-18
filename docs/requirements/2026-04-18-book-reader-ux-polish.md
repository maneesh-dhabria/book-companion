# Book Reader UX Polish — Requirements

**Date:** 2026-04-18
**Status:** Draft
**Tier:** 2 — Enhancement

## Problem

Opening *Understanding Michael Porter* on the web reader surfaced four related UX issues that together make the reading experience feel unfinished. The book opens on the Copyright page instead of a real chapter; the Summary tab silently falls through to original content even on sections that *have* a summary; embedded images are broken; and every in-document anchor link is clickable, including heading self-refs and footnote markers that go nowhere useful. The issues share a root cause: the reader treats all sections as equivalent — the parser misclassifies front-matter as chapters, the API never returns summary text, pre-migration books have unrendered image placeholders, and the content renderer doesn't discriminate between link types.

### Who & Why Now

A personal user (the developer) running the tool locally after the post-install packaging work landed, reading a real EPUB end-to-end for the first time. The issues are invisible in fixture-based tests (small, synthetic inputs) but show up immediately on real books with proper front-matter structure. Fixing them now — while the post-install-runtime-quality spec is still unshipped and the image-URL migration is fresh — keeps the remediation effort small and prevents each becoming a long-lived papercut.

## Goals & Non-Goals

### Goals

- **Books open on a real chapter, not front-matter.** Acceptance: on first open (no saved reading position) *Understanding Michael Porter* lands on "1. Competition: The Right Mind-Set" — not Copyright. Subsequent opens resume at the last-read position per existing behavior.
- **Front-matter stays accessible but de-emphasized.** Acceptance: Copyright, Acknowledgments, and any Part-header pseudo-section appear in the TOC under a collapsed "Front Matter" group that the user can expand.
- **Summary tab renders the summary when one exists.** Acceptance: on a section with a default summary, the Summary tab displays the rendered summary markdown — not the original content.
- **Summary tab shows a meaningful empty state, differentiated by reason.** Acceptance: front-matter sections show "Summary not applicable" (no CTA); chapters without a summary show "Not yet summarized" with a per-section *Summarize this section* CTA.
- **Existing books' images render after one server restart.** Acceptance: after startup, no section's `content_md` contains the literal substring `__IMG_PLACEHOLDER__`; every image tag in the Porter book resolves to a working URL.
- **Heading-anchor and footnote-style links inside content are not clickable; external links stay clickable and open in a new tab.** Acceptance: `<a href="#...">` in source content renders as plain text; `<a href="https://...">` remains clickable with `target="_blank" rel="noopener noreferrer"`.
- **Book detail page shows summarization progress and a one-click recovery action.** Acceptance: the Porter book detail view shows "7 of 12 summarized" (12 = summarizable-type sections) and a *Summarize pending sections* button that queues only the missing ones.
- **Summarization skips non-summarizable section types by default.** Acceptance: a fresh summarization run on the Porter book no longer produces summaries for Copyright, Acknowledgments, or Part-header sections.

### Non-Goals

- NOT adding footnote popovers or in-reader jump-to-anchor navigation, because turning relative anchors into functional reader scroll is a proper reader-feature change that deserves its own requirements pass. Stripping those links is the right v1 step.
- NOT re-parsing or re-importing existing books, because a one-time migration re-tagging section types and pruning orphan summaries achieves the same outcome without risking loss of user annotations or reading state.
- NOT changing summarization job mechanics (per-section commits, skip-already-summarized, SSE progress streams), because [`2026-04-12-post-install-runtime-quality`](./2026-04-12-post-install-runtime-quality.md) already owns those. This doc depends on that one but does not duplicate it.
- NOT making the summarizable-section-types list user-configurable, because v1 should ship a conservative fixed default; configurability can come later if users complain about appendix/glossary coverage.
- NOT changing how reading position / continue-reading is tracked, because that's an adjacent story. These fixes only affect the *first-time* landing behavior.
- NOT wiring internal TOC `<a href="#chapter-2">`-style links to reader navigation — for this iteration they are stripped, not re-routed.
- NOT preserving intentional author-placed internal anchors (concept maps, cross-references inside a chapter) as clickable, because we cannot distinguish them from heading self-refs or footnote markers at sanitization time. This is a known loss for the small number of non-fiction books that rely on them; a proper reader-internal navigation feature will restore it.

## Solution Direction

Five coordinated changes, roughly in order of user visibility:

### 1. Parser — extend section-type classification

Add missing front-matter types so Copyright, Acknowledgments, Dedication, Title Page, Table of Contents, Colophon, and Part-headers are detected instead of silently falling through to `chapter`. Detection remains title-regex based (consistent with existing patterns), with one enhancement: **Part-header detection is content-aware**. A title matching the part-header pattern is classified as `part_header` only if its content is below a short threshold (~1000 chars). If the "Part" section has substantial prose (a real intro to the part), it stays a `chapter` and is summarized normally.

Two typed sets become load-bearing throughout the system:

- **Front-matter types** (never summarized, grouped in TOC): `copyright`, `acknowledgments`, `dedication`, `title_page`, `table_of_contents`, `colophon`, `part_header`.
- **Summarizable types** (count toward progress, target of default summarization): `chapter`, `introduction`, `preface`, `foreword`, `epilogue`, `conclusion`.

Types outside both sets (`glossary`, `notes`, `appendix`, `bibliography`, `index`, `about_author`, `other`) remain accessible but are neither auto-summarized nor grouped as front-matter — they sit at their natural TOC position.

### 2. Data migration — backfill existing books

On next server start, a one-shot, idempotent migration walks every `BookSection` and:

- Re-runs the new classifier against the section's title + content; updates `section_type` where it changed.
- For every section newly classified into the front-matter set: **prune auto-generated summaries only, preserve user-curated ones** (per D6). The auto-generated ones are wasted LLM calls cluttering the library; a user-chosen default summary reflects a deliberate decision and is retained as the section's default even after reclassification.
- Logs totals: sections re-classified, auto summaries pruned, user-curated summaries preserved, books affected.

Re-running the migration after it's already run should produce zero changes.

### 3. Summary content delivery — return the markdown, not just metadata

Today the section endpoint returns summary metadata (id, preset, timestamps) but not the summary's text body, so the UI cannot render it even when it exists. The API is extended so a section fetched with content also carries its default summary's markdown body plus an `is_summarizable` signal. (Exact field shape is a spec decision.)

Also: a new book-level *summarize pending* action queues summarization only for sections of summarizable types that don't yet have a default summary. It reuses the existing summarization job pipeline.

### 4. Frontend — reader UX wiring

- **Landing section:** On first open (no last-read position), pick the first section of a summarizable type. If none exist (reference-only books), fall back to `sections[0]`.
- **TOC grouping:** Group pre-body front-matter and part-headers under a collapsible "Front Matter" accordion at the top of the TOC, collapsed by default. Later-position types like glossary/notes/about-author stay at their natural position.
- **Summary tab content:** When the mode toggle is on Summary and a summary exists, render the summary markdown. Otherwise render one of two empty states (plus an optional third, see below):
  1. Section type is front-matter → "Summary not applicable for [section title]" (no CTA).
  2. Section type is anything else (summarizable, or non-front-matter like glossary/notes/appendix/bibliography/index/about_author) with no summary → "Not yet summarized" + *Summarize this section* button. Triggering the CTA on a non-summarizable type is a deliberate user override; the resulting summary does not add to the book-level progress counter (which tracks summarizable types only).
  3. *(Stretch, conditional on per-section progress events)* A summarization job is actively running against this section → "Generating summary…" state. If SSE/polling isn't available, this state is skipped and state 2 persists until the job completes and the tab is re-opened.
- **Book detail progress:** Show "N of M summarized" where M = count of summarizable-type sections, plus a *Summarize pending sections* button that calls the new book-level action. Button is disabled while a summarization job is running on this book.

### 5. Frontend — content sanitization

After DOMPurify sanitization, post-process rendered HTML:

- Every `<a>` with a relative anchor href (starts with `#`) → replace with a span, preserving text and styling. Heading self-refs and footnote refs become plain text.
- Every `<a>` with `http://`, `https://`, `mailto:`, or a protocol-relative `//host/path` URL → add `target="_blank"` and `rel="noopener noreferrer"` (protocol-relative links inherit the page scheme, so treating them as external is correct).
- Every `<a>` with any other scheme (`javascript:`, `data:`, `file:`, or a relative file path like `./ch2.xhtml`) → replace with a span. Safe default: if it's not clearly external and not clearly in-book, don't make it interactive.

## User Journeys

### Primary Journey — Opening a book for the first time

1. User uploads *Understanding Michael Porter* → opens it from the library.
2. **Today:** reader opens on Copyright. Summary tab is visible there even though it's a copyright notice. The first real chapter is buried four clicks in.
3. **After fix:** reader opens on "1. Competition: The Right Mind-Set". TOC shows "▸ Front Matter (3)" collapsed at the top, then body chapters. Summary tab shows the generated summary if one exists.
4. User expands Front Matter, clicks Copyright out of curiosity.
5. **After fix:** Copyright renders its original text. Summary tab shows "Summary not applicable for Copyright" — no CTA.

### Primary Journey — Reading a summary

1. User is on a chapter that has a summary. Clicks Summary tab.
2. **Today:** tab toggles internally but the content panel still shows the original. User concludes "summaries don't exist for this book."
3. **After fix:** Summary tab renders the summary markdown. User sees bullets / prose per the configured preset.
4. User clicks to a later chapter that the earlier partial-run didn't cover.
5. **After fix:** Summary tab shows "Not yet summarized" + a button to summarize just this section. User can either click that, or return to the book detail page and hit *Summarize pending sections* to batch the remainder.

### Primary Journey — Existing library after upgrade

1. User pulls the new version, runs `bookcompanion serve`.
2. Server startup prints a visible "Upgrading library — N books, M sections" line, runs the image-placeholder migration and the section-reclassification migration in sequence, prints a summary at the end ("Migrated images in X sections; re-classified Y sections; pruned Z orphaned summaries"). On a typical personal library (<100 books) this completes in seconds; the `serve` command blocks on it so the UI never starts in a half-migrated state.
3. User opens the Porter book. Images render inline. Copyright is under "Front Matter". Chapter summaries are readable. No user action required.
4. *(Expected counter shift, worth anticipating):* before the upgrade the book detail page showed "7 of 17 summarized" because Copyright / Acknowledgments / Part-One had auto-generated summaries that counted. After the upgrade the counter reads something like "4 of 12 summarized" — auto summaries on the pruned front-matter are gone, and the denominator now counts only summarizable-type sections. The new number is lower but more accurate, and clicking *Summarize pending sections* fills the remainder.

### Primary Journey — Summarize pending with live progress

1. User lands on the Porter book detail page. Sees "7 of 12 sections summarized" and a *Summarize pending sections* button.
2. Clicks the button. Button becomes disabled and re-labels (e.g., "Summarizing… 7 of 12"); the counter updates as each pending section completes. The user can navigate into the reader while this runs.
3. In the reader, a section that is currently being summarized shows "Generating summary…" on the Summary tab (stretch; see note below). Completed sections swap from the "Not yet summarized" empty state to rendered summary without a reload.
4. Job finishes. Counter reads "12 of 12 summarized"; the button disappears (or becomes *Re-summarize all*, out of scope here).
5. If the job fails partway (e.g., LLM CLI crashes), the counter reflects the sections that did complete; the button re-enables as *Summarize pending sections* again so the user can retry the remainder — matching the skip-already-summarized behavior from `post-install-runtime-quality`.

*Note:* The per-section "Generating summary…" state assumes per-section completion events from the backend (SSE or polling). This depends on the SSE/progress work in `post-install-runtime-quality`. If that infra isn't live yet, the graceful degradation is: the Summary tab shows "Not yet summarized" until the whole job completes, at which point a full reload reveals all new summaries. This is a stretch goal, not a blocker for this spec.

### Primary Journey — Link behavior in original content

1. Introduction section contains a footnote reference (`¹` linking to `#note-1`), an external link to the author's site (`https://...`), and a heading whose title wraps a self-anchor (`<h2><a href="#strategy">Strategy</a></h2>`).
2. **After fix:**
   - The footnote superscript renders as plain text — no pointer cursor, no navigation.
   - The external link is clickable, opens in a new browser tab, doesn't expose the parent tab (rel=noopener).
   - The heading text "Strategy" is plain — the self-anchor is stripped.

### Error / Edge Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| Book has no summarizable sections (reference-only) | Edge: a dictionary or collection of glossaries | Reader still opens on the first section. Progress shows "0 of 0"; the *Summarize pending* button is hidden (no denominator). |
| Migration encounters a section with NULL or empty content | Legacy data | Skip silently, log a debug line. Idempotence preserved. |
| "Part Three" section contains 8000 chars of part-intro prose | Real content, not a divider | Classified as `chapter` (content-aware rule). Summarized normally. Appears in body, not under Front Matter. |
| Section title matches multiple type patterns (e.g., "Epilogue and Conclusion") | Ambiguous | Use a documented, deterministic first-match ordering of patterns in the parser. |
| User opens Summary tab while a summarization job is processing THIS section | Mid-flight | Show "Generating summary…" empty state. When the job marks this section complete, the rendered summary replaces the state on next tick or SSE update. |
| Brand-new book imported after all fixes ship | Fresh import | Parser uses new patterns end-to-end; migration is a no-op for this book; front-matter is never summarized. |
| Protocol-relative external link (`//example.com`) | Rare but valid | Treated as external: kept clickable, opens in new tab. |
| Relative file path left over from EPUB (`./ch2.xhtml`) | Occasional | Stripped — neither an in-book anchor nor an external URL. Safer to make non-interactive than to guess. |
| User deletes a book in the middle of the migration | Concurrent edge | Migration should not fail; foreign-key cascade handles deleted rows. Next startup's migration run picks up where this one left off (no partial lockfile). |
| Migration crashes or the process is killed mid-run | Power loss, SIGKILL, out-of-disk | Partial progress is committed per-book (or per-section group, small enough). On next startup, the migration re-runs and is idempotent: already-updated sections produce no change, unfinished sections get processed. No corrupt/half-migrated state is observable from the UI. |
| Migration would delete a summary that the user explicitly chose as default via the CLI (`summary set-default`) on a section that's now being re-classified as front-matter | Rare but real | Preserve the summary row and its default pointer. Detection heuristic: the default summary was set more than a short window after the auto-batch completed, or its preset differs from the section's auto-generated summaries, OR there's more than one summary for this section (implying a user choice). When in doubt, preserve. Surfacing this behavior: log "Preserved user-curated summary on section X despite reclassification." |
| Content contains the literal substring `__IMG_PLACEHOLDER__` for reasons unrelated to the parser (a book discussing the tool's internals) | False-positive risk | The full placeholder shape includes a known terminator (`__ENDIMG__`) and a filename fragment that matches a stored Image record. Require all three to match before substituting — stray occurrences of the token literal remain untouched. |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | Tag & land on first chapter; front-matter collapsed in TOC | (a) Hide front-matter entirely, (b) Merge into a single "Front Matter" section, (c) Merge into Chapter 1 as preamble, (d) Keep visible but collapsed (chosen) | Matches Kindle/Apple Books "Beginning" convention. Preserves access; moves the confusion out of the landing view. Merging into Chapter 1 mixes two distinct content kinds into one summary — bad signal for the LLM. |
| D2 | Distinct empty-state per reason in the Summary tab | (a) Single CTA for all missing cases, (b) Hide Summary tab conditionally, (c) Distinct states per reason (chosen) | Users need to distinguish "the system can't do this for me" (front-matter) from "I can take action" (unsummarized chapter). A uniform CTA would invite summarizing Copyright, wasting LLM calls and polluting the library. |
| D3 | One-time startup migration for image placeholders | (a) Manual re-import, (b) CLI repair command, (c) Startup migration (chosen) | Lowest-friction: library repairs itself after one restart. Idempotent → zero risk on re-run; logging gives visibility. Manual re-import risks losing annotations and reading state. |
| D4 | Strip relative anchors; keep http(s)/mailto clickable in new tab | (a) Strip all links, (b) Keep internal TOC jumps functional, (c) Strip relative anchors only (chosen) | Matches the user's stated intent. Making in-book anchors functional (jump-to-section) is a reader navigation feature that deserves its own pass — hacky rewrites now would need to be undone later. `rel="noopener noreferrer"` is non-negotiable for security. |
| D5 | Content-aware part-header classification | (a) Title-only regex, (b) Content-length only, (c) Title match + content-length gate (chosen) | A "Part Three" heading might be a 100-char divider OR an 8000-char part-intro essay. Classifying on title alone would silently skip summarization for the latter. Combining signals is an inexpensive safeguard. Threshold of ~1000 chars is twice the existing stub-merge threshold (500 chars), leaving a deliberate band between them: sections under 500 chars are merged away before classification; 500–1000 chars get classified as `part_header` (not summarized); above 1000 chars a title-matching section stays a `chapter` and is summarized. The two thresholds answer different questions and don't collide. |
| D6 | Delete auto-generated summaries on re-classified front-matter; preserve user-curated ones | (a) Keep all rows, null default pointer only, (b) Delete everything (previous option), (c) Delete auto-generated, preserve user-curated (chosen) | Auto-generated summaries on Copyright / Acknowledgments are noise — prune them. But a user who explicitly ran `summary set-default` to pin a particular summary made a deliberate choice; silently deleting it on upgrade would violate their intent. Heuristic for "user-curated": more than one summary exists for the section, or the default summary's preset differs from the section's most recent auto-batch, or a CLI action created it. When in doubt, preserve. Logged at INFO so the user can see what was kept. |
| D7 | Return summary body in the section response rather than a separate endpoint | (a) Separate `/sections/{id}/summary` lazy-load, (b) Include in section response (chosen) | One request gives the UI everything needed for either tab. Section summaries are small. Saves a round-trip per tab switch. A separate endpoint would only pay off if summaries became large multi-KB payloads, which they aren't. |
| D8 | Book detail page shows progress counter + *Summarize pending* button | (a) Just a button, no counter, (b) No button, user re-runs from library, (c) Both (chosen) | Counter answers the implicit "did it actually work?" question. Button gives a one-click recovery after partial runs. Together they turn the partial-state experience from mysterious to self-serve. The user raised this during brainstorm as an explicit UX ask. |
| D9 | Summarizable types = chapter, introduction, preface, foreword, epilogue, conclusion (v1 fixed list) | (a) + glossary/notes/appendix, (b) + bibliography/index (all non-front-matter), (c) body only (chosen), (d) user-configurable | Conservative v1. Summaries of reference material (glossary, index, notes) rarely serve the "absorb the argument" use case. Keeps LLM spend focused. **Escape hatch:** the per-section *Summarize this section* CTA (D2) still works on any non-front-matter type — so users with appendix-heavy technical books can summarize one-offs manually, even though those sections don't count toward the book-level progress counter. Full configurability (user-selected type set per book) is a deliberate v2 item. |
| D10 | Cross-reference partial-run behavior to `post-install-runtime-quality` rather than duplicating | (a) Duplicate requirement, (b) Out of scope silently, (c) Cross-reference + one acceptance (chosen) | The other spec already covers per-section commits and skip-already-summarized. Duplicating risks divergence. One acceptance ("re-summarize Porter from its current 7/17 state finishes cleanly") catches dependency regressions cheaply. |

## Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `frontend/src/views/BookDetailView.vue:151` | Existing code | Always passes `content_md` regardless of the Summary tab mode — frontend half of Issue #3. |
| `backend/app/api/routes/sections.py:63-75` | Existing code | Section response returns summary metadata but no `summary_md` body — backend half of Issue #3. |
| `backend/app/services/parser/epub_parser.py:16-41` | Existing code | Section-type detection regex set; missing entries for copyright/acknowledgments/dedication/title_page/toc/colophon/part_header. |
| `backend/app/services/parser/epub_parser.py:99-120` | Existing code | Stub-merge threshold (500 chars) is parse-time only; content-aware part-header classification is the related-but-distinct signal we need. |
| `backend/app/services/parser/image_url_rewrite.py:21-55` | Existing code | Placeholder scheme from commit `649dba1`; pre-fix imports still carry literal placeholder strings. |
| `frontend/src/components/reader/ReadingArea.vue:16-24` | Existing code | markdown-it + DOMPurify; no link rewriting — root of Issue #4. |
| `frontend/src/components/reader/TOCDropdown.vue:45` | Existing code | Per-section "S" marker exists; no book-level progress counter today. |
| SQLite inspection: Porter book has 7/17 `default_summary_id` set | Live data | Partial run; confirms summarization *did* execute, up to section order 6 (Ch 3). Display issues, not missing data. |
| `docs/requirements/2026-04-12-post-install-runtime-quality.md` | Internal spec (dependency) | Per-section commits + skip-already-summarized — both required for the *Summarize pending* flow to be resumable and incremental. |
| Apple Books "Beginning" / Kindle "Go to Beginning" | External / product | Open at first body section, not cover; front-matter remains in TOC but de-emphasized. |
| Readwise Reader (Ghostreader) | External / product | Per-section opt-in summarization; missing summaries get an explicit CTA, not a silent fallback. |
| Notion AI generation states | External / UX | Empty states are a first-class state-machine (generating / failed / ready) with skeleton placeholders and inline retry — anti-pattern is a blank pane. |
| OWASP `rel="noopener"` guidance | External / spec | `target="_blank"` without `noopener` is a tab-hijacking vector; always pair. |

## Open Questions

| # | Question | Owner | Needed By |
|---|---|---|---|
| 1 | Should the image-placeholder migration and the section-reclassification migration run inside the Alembic pipeline (data migrations alongside schema) or as one-shot scripts invoked on startup outside Alembic? Neither is a schema change, but consistency with schema migrations has operational benefits. | Maneesh | During spec |
| 2 | Should the *Summarize pending sections* button use the book's existing default preset (no prompt) or open the preset picker the same way the current *Summarize* button does? First is faster; second is consistent. | Maneesh | During spec |
| 3 | For the Summary tab "Generating…" state: per-section SSE events, or client polling of `has_summary` while a book-level job is running? SSE is cleaner; polling is what current infra likely supports. | Maneesh | During spec |
| 4 | TOC "Front Matter" group: default-collapsed for every book, or remember the user's expand/collapse choice per book (persisted to reader state)? | Maneesh | During spec or implementation |
| 5 | What's the exact heuristic for detecting "user-curated" summaries in D6? The requirements list three possible signals (multiple summaries for section, preset diverges from auto-batch, CLI provenance). Pick one or combine — a spec concern. | Maneesh | During spec |

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | (a) Missing journey for *Summarize pending* live progress. (b) Migration UX during upgrade silent. (c) No edge case for migration mid-run crash. (d) D9 had no escape hatch — users with appendix-heavy books had no path. (e) User-curated summaries on re-classified sections would be destroyed by D6. (f) Stripping relative anchors silently drops intentional author-placed anchors. (g) "Generating summary…" state assumed infra that may not exist. | (a) Added "Summarize pending with live progress" primary journey with graceful-degradation note. (b) Rewrote upgrade journey step 2 with explicit log messaging and blocking behavior. (c) Added mid-run crash edge case row + false-positive placeholder detection row. (d) Expanded D9 with per-section CTA escape-hatch + v2 configurability note. (e) Rewrote D6 to preserve user-curated summaries (confirmed with user); updated edge case row; rewrote OQ#5 to be about the heuristic, not the policy. (f) Added Non-Goal acknowledging author-intent anchor loss. (g) Marked state 3 of Summary empty states as stretch/conditional on post-install SSE work. |
| 2 | (a) Solution Direction §2 still said "deletes its summary rows" unconditionally — contradicted the user-curated preservation added to D6 in loop 1. (b) Counter goes from "7 of 17" to "4 of 12" for Porter after migration; worth calling out so users aren't surprised. (c) D5's 1000-char threshold and the existing 500-char stub-merge threshold might look collision-prone; the interaction is actually consistent but unstated. (d) Goal 1 acceptance was ambiguous on first-open vs. any-open. | (a) Rewrote §2 bullet to match D6 (preserve user-curated). (b) Added step 4 to the upgrade journey that anticipates the counter transition with concrete numbers. (c) Expanded D5 rationale to name the deliberate 500/1000 band and explain the separation. (d) Tightened Goal 1 acceptance to "first open, no saved reading position". |
| 3 (final) | Two coherence bugs surfaced on the final read: (a) D9's escape-hatch clause promised the per-section CTA works on "any non-front-matter type" but D2 / Solution §4 limited the CTA to summarizable types — appendix sections would get no CTA, breaking the escape hatch for appendix-heavy books. (b) Solution §5 said protocol-relative `//example.com` links are stripped while the edge-case table said they're treated as external — direct contradiction. | (a) Expanded state 2 of the Summary empty-state to cover any non-front-matter type, noting that manual summaries on non-summarizable types deliberately don't add to the progress counter. (b) Moved protocol-relative `//` to the external bucket in Solution §5 with a one-line justification (protocol-relative inherits the page scheme). |

---

*Next step: `/spec` to turn this into a technical specification.*
