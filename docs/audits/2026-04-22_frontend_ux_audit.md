# Book Companion Frontend — UX + Functionality Audit

**Date:** 2026-04-22
**Build:** Running `bookcompanion serve` on `localhost:8000` (built SPA in `backend/static/`)
**Fixtures:** Existing `Understanding Michael Porter` (book 1, pre-summarized with empty summaries) + newly uploaded Gutenberg `The Art of War` (book 2, 27 sections)
**Auditor:** Playwright-driven click-through + API inspection + server-log cross-check

---

## Summary

Audit surfaced **8 blocking bugs**, **7 significant bugs**, and **~18 UX/polish gaps**. Two areas stand out as unshippable as-is:

1. **Summarization wiring from the upload wizard is broken at two layers** — the wizard ships preset IDs that don't exist on the backend, and when the (one) valid preset is picked the backend silently fails on most chapter-length sections with no error surfaced in the UI.
2. **Deep-linking into a specific section of the reader is broken.** Reload or shareable URLs like `/books/2/sections/31` render section 1 (front-matter) instead of the requested section.

Additional unfinished/stubbed work: the book-level summary route (`/books/:id/summary`) is literally a placeholder with only the string `BookSummaryView`.

---

## Blocking bugs (B-*)

### B1. Upload-wizard preset names don't map to backend presets
- **Where:** Upload wizard step 4 (`PresetPicker.vue`)
- **Repro:** Upload any book → pick "Balanced", "Brief", or "Detailed" → click Start Processing.
- **Observed:** `POST /api/v1/books/:id/summarize` returns `400 "Preset 'brief' not found. Available presets: academic_detailed, executive_brief, practitioner_bullets, study_guide, tweet_thread"`. **No visible error in the UI** — the Start Processing button just sits active-looking.
- **Root cause:** `frontend/src/components/upload/PresetPicker.vue` hard-codes `balanced`, `brief`, `detailed` which aren't real. Only `practitioner_bullets` is real.
- **Fix:** Fetch real presets from backend (endpoint needs to be added — see B2), OR align the four hardcoded IDs with the five YAML files under `backend/app/services/summarizer/prompts/presets/`.

### B2. No API endpoint to list summarization presets
- `GET /api/v1/summarize/presets` returns the SPA HTML (SPA fallback swallows 404). There is **no** backend route exposing the YAML presets on disk. Confirmed by grepping `backend/app/api/routes/` — only `reading_presets.py` exists (unrelated, for reader styles).
- Without this, the frontend can never be data-driven; the picker will always drift.

### B3. Silent Claude-CLI failures — 18/27 sections failed with empty error
- Server log (after I picked the one valid preset and hit Start Processing):
  ```
  section_summarization_failed  error='Claude CLI failed (rc=1): '   section_id=24..44
  ```
  Error body is empty (stderr not captured) and **no eval/retry banner appears in the reader**. The book status stayed at `parsed`, `has_summary: null`. The only visible sign is that clicking Summary on a given chapter shows a disabled "No Summary" button; the user cannot distinguish "not tried yet" from "tried and failed."
- **Fix candidates:** capture stderr in the subprocess provider, store per-section failure state, surface a "X failed · Retry" banner at the top of the reader and in the library card.

### B4. Upload → Summarize has NO failure UI at all
- After B1 returns 400, the console logs `ApiError: Preset "brief" not found…` but **the wizard shows zero error state**. The Start Processing button remains clickable. Users get no signal that the request failed.
- **Fix:** toast/error state on `UploadView.vue` `:catch` branch.

### B5. Deep-link to `/books/:id/sections/:sectionId` ignores the sectionId on load
- Repro: from reader go to Chapter V (section 35 in AoW), reload. URL is preserved but the reader renders section 1 (front-matter) and breadcrumb shows the book's first section. Same happens for Porter book.
- Further symptom: the Summary toggle still shows "Summary" as the *active* pill but the rendered article is clearly the Original of section 1.
- **Fix:** the router/route-guard resolver isn't reading the `sectionId` param on hard-load; only reacts to in-app navigation.

### B6. Empty summaries stored as "has_summary = true"
- Porter book has `default_summary.summary_md === ""` (empty string) for multiple sections but `has_summary: true`. The Summary tab pill is rendered as active+disabled, content area falls back to Original. Confusing for the user — looks broken but there is no error.
- **Fix:** if `summary_md` is empty, don't mark `has_summary: true`; treat as failed and show retry CTA.

### B7. `/books/:id/summary` route is an unimplemented stub
- Content is literally just a heading: `BookSummaryView`. No book-level summary, no progress counter, no section list — nothing.
- Given book-level summary is a first-order feature per the CLI (`bookcompanion summary read <book_id>`), this is the most obvious UX hole.

### B8. 503 Service Unavailable on `PUT /api/v1/reading-state` during summarization
- SQLite/WAL contention: while the summarizer writes, `reading-state` upsert fails with "db_busy_timeout", surfaces in browser console as 503. No user-visible fallback; reading progress silently fails to save.
- **Fix:** widen the `busy_timeout` pragma or queue reading-state writes with retries.

---

## Significant bugs (S-*)

### S1. Chat response is rendered as plain text; markdown is not parsed
- User message → AI returns markdown with `**Five Forces**`, numbered lists, etc. Chat bubble shows literal asterisks. Reader renders markdown correctly elsewhere (`markdown-it` + DOMPurify), so the chat bubble just isn't wired to it.

### S2. Annotation global list shows no book/section context
- `/annotations` page lists a highlight with only `"Highlight · 22/04/2026"` and the quote. No book title, no section title, no "Go to source" link. Unusable for any real library.

### S3. Command-palette has no loading or "no results" state
- When first typing, there's a brief window where the palette is empty with no spinner; if the query returns zero matches, there is still no "no results" text.

### S4. `document.title` is permanently "Vite App"
- `frontend/index.html:7` has `<title>Vite App</title>` (shipped default). Never updated per-route. Means every tab/window shows "Vite App" — noticeable on browser tab list, history, bookmarks.

### S5. TOC progress badge is an unlabelled letter "S"
- Sections that have a summary are appended with an `S` glyph — no legend, no tooltip, no color. A reader can't guess what the S means. `ariaLabel: null`, `title: ''`.

### S6. Uncaught `TypeError: e.presets.filter is not a function`
- Thrown when opening the reader settings (⚙) pane. Reader Settings still renders, but the error may break the Presets drop-down. Reproducer: open any section, click ⚙. Seen in `BookDetailView-BaE9dFiQ.js:17:7857`.

### S7. Internal EPUB anchors are kept as clickable links in rendered content
- Headings like the Introduction `<h1>` wrap a link pointing at `CR!DM74EPGPW51NHDPM59A3W1XV08NQ_split_004.html#filepos2205` (raw EPUB file anchor) and inline references to "Part 1"/"Part 2" link to similar broken URLs. Clicking navigates off-app. The migration commit that rewrote `images/...` refs didn't address text/`#anchor` links.

---

## UX / polish gaps (UX-*)

### UX1. Structure step misclassifies sections
Gutenberg `Art of War` upload — "Structure" step labels look noisy:
- `LIONEL GILES, M.A.` → `chapter` (byline)
- `Footnotes` → `chapter` (should be notes)
- `Bibliography` → `bibliography` ✓
- `THE FULL PROJECT GUTENBERG™ LICENSE` → `chapter`

### UX2. Section-type labels rendered with underscores
Structure table shows `table_of_contents`, `introduction`, `preface` in lowercase + underscores. Should be "Table of Contents", "Introduction", "Preface".

### UX3. Upload Step 2 "Metadata" is auto-skipped silently
Step indicator flashes `Upload ✓ → Metadata ✓ → Structure`. The Metadata step has no UI — it's extracted on the server and the wizard bypasses. Either drop the step from the indicator or render an editable metadata form so misread EPUB metadata can be corrected before indexing.

### UX4. Upload confirmation uses internal preset ID
After Start Processing: "Your book is being summarized with the **practitioner_bullets** preset." Should use the user-facing label ("Practitioner").

### UX5. Reader heading says "Reader" — not the book title
Every reader page shows `<h1>Reader</h1>` in the top banner regardless of which book/section is open. The book title is only in the breadcrumb. Visually weak.

### UX6. `No Summary` button is disabled with no "Summarize this section" CTA
On `is_summarizable: true` sections without a summary, the only affordance is a disabled "No Summary" pill. User has no button to trigger summarization for the one section they're reading. Spec doc implies this CTA should exist.

### UX7. No book-level "Summarize pending sections" UI surfaced
I couldn't find the "Summarize pending sections" / "X of Y summarized" progress banner mentioned in the source. For a newly-uploaded book whose background job has mostly failed, there is no way from the UI to re-trigger or resume.

### UX8. Library filter option casing is inconsistent
Status filter options: `All Statuses`, `parsed`, `summarizing`, `completed` (three lowercase).
Format filter options: `All Formats`, `EPUB`, `PDF`, `MOBI` (uppercase). Pick one convention.

### UX9. Date formatting is ambiguous DD/MM vs MM/DD
Library table "Updated: 12/04/2026", Annotations "22/04/2026". No locale-aware ISO or "Apr 12, 2026" rendering.

### UX10. Continue banner surfaces a meaningless section
"You were reading Understanding Michael Porter, **Copyright**" — the previous session auto-parked on the Copyright front-matter (probably the last section loaded during a prior test). The reader-state tracker shouldn't persist front-matter / is_summarizable=false sections as the resume point.

### UX11. Navigation label "Notes" but destination page title is "Annotations"
Left nav label: `💬 Notes`. Page `<h1>`: `Annotations`. Section-sidebar tab: `Annotations`. Pick one.

### UX12. Image alt text is the literal word "image"
All `<img alt="image">` — useless for accessibility and alt-text fallback when the image fails.

### UX13. "Export MARKDOWN" button looks shouty
`/annotations` shows **Export MARKDOWN** in all-caps. Should be "Export Markdown".

### UX14. Chat thread is titled "New Thread"
Threads never get a derived title from the first message. Over time the list becomes indistinguishable.

### UX15. Chat has no section-context indicator
Nothing in the chat UI tells the user whether it knows about the current section, the whole book, or has global scope.

### UX16. Text-selection highlight color ≈ current-selection color
After creating a highlight, the stored highlight renders in the same pale blue that browsers use for live selections. Distinguishing new-selection from stored-highlight is hard.

### UX17. Image rendering — decorative hr images (217×1) still occupy row space
The "scroll divider" image in Acknowledgments section renders at 217×1 which is correct, but it's invisible and the `<p>` wrapping it has vertical padding. Harmless but noisy markup.

### UX18. TOC inside rendered content (table of book's own TOC) uses raw EPUB anchors
The AoW front-matter "Contents" table is rendered inside the reader; every row is a link to a file path that Vue Router can't resolve. Clicking does nothing (or navigates away). Either suppress internal TOCs during parse, or rewrite the anchors to `/books/:id/sections/:sectionId`.

### UX19. `database_migrations_behind` warning at server boot
`bookcompanion serve` logs a `database_migrations_behind` warning but autoruns. Fine for dev; worth a loud "please run init" nudge in the UI (banner on library page) for users.

### UX20. Default-summary autoselection missing
Porter sections have `default_summary` objects but `default_summary_id: None` sometimes. Autoset the first/latest non-empty summary as default; otherwise the Summary tab is dead weight even though a summary exists.

---

## What works well

- **Library view** — filters, grid/list/table switcher, pagination UI, continue-reading banner all render correctly.
- **Upload wizard steps 1 → 3** — file drop, server-side parse, structure preview. UX clean aside from classifier quirks.
- **Reader Settings (font, size, spacing, width, theme, preview)** — polished, immediate preview.
- **Annotation creation** — floating toolbar with Highlight / Note / Ask AI / Copy appears reliably. Highlight persists in sidebar.
- **AI chat end-to-end** — POST/GET flow works, "Thinking…" indicator is shown, response comes back with real book-grounded content.
- **Image serving via `/api/v1/images/:id`** — requests 200 OK, `<img>` elements render with natural dimensions preserved.
- **Search API + command-palette** — Meta-K opens palette, backend `search/quick` returns structured results, arrow-key nav works.

---

## Priority-ordered fix list

1. **B3** — capture & surface Claude-CLI stderr + per-section failure UI. (Makes the whole feature honest.)
2. **B1 + B2** — backend endpoint for presets, frontend picker reads from it. (Unblocks summarize-on-upload.)
3. **B5** — fix deep-link to section on hard-load. (Breaks shareable URLs and reload.)
4. **B7** — ship `/books/:id/summary` instead of the placeholder.
5. **B6 + UX20** — don't mark empty summaries as present; autoselect default_summary.
6. **UX6 + UX7** — add "Summarize this section" + book-level "Summarize pending sections" buttons in the reader.
7. **S1** — render chat markdown with markdown-it + DOMPurify (already used elsewhere).
8. **S2** — book/section context on `/annotations` page items.
9. **S4** — dynamic `document.title`.
10. **UX5, UX11, UX8, UX9, UX13** — naming/casing consistency pass across reader heading, "Notes/Annotations", filter case, date format, button case.
