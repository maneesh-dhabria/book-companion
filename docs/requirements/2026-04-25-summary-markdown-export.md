# Summary Markdown Export — Requirements

**Date:** 2026-04-25
**Status:** Draft
**Tier:** 2 — Enhancement

## Problem

The reader has invested significant time generating per-section and book-level summaries, plus highlights and notes, but there is no usable way to take that knowledge **out** of Book Companion. The CLI has a `bookcompanion export book <id> --format markdown` command that dumps everything in one shot with no selection, and the web UI has no export affordance at all. A reader who wants a portable Markdown copy of their distilled knowledge — to read offline, paste into Obsidian, share with a colleague, or archive in a personal notes system — has to either run a CLI invocation that emits the whole kitchen sink, or manually copy each summary one section at a time from the UI.

### Who & Why Now

- **Persona:** A power reader (the project's primary user) who has summarized 5–30 books in Book Companion and treats it as a personal knowledge base. They use Obsidian/Notion/plain Markdown for long-term notes and want Book Companion summaries to flow into that system.
- **Trigger:** v1.5 has stabilized the reader experience (annotations, summaries, presets). Now that summaries are reliably good and annotations are first-class, "get my knowledge out of the tool" is the next obvious gap. Without an export path, Book Companion's value is trapped behind its own UI.

## Goals & Non-Goals

### Goals

- A reader on the **book detail page** can produce a Markdown file containing their book summary, section summaries, table of contents, and annotations in **one click**, with sensible defaults — measured by: button is reachable in ≤ 1 click from `/books/:id`.
- A reader can **customize what's included** before exporting (toggle book summary, individual sections, TOC, annotations) — measured by: every selection combination produces a valid Markdown file with only the requested items.
- A reader using the **CLI** can do the same thing today's `bookcompanion export book` does, but with new flags to exclude specific sections, the book summary, the TOC, or annotations — measured by: every UI toggle has a CLI equivalent.
- The exported Markdown **renders cleanly** in standard Markdown viewers (GitHub, Obsidian, VS Code preview) with anchor-linked TOC navigation and no broken in-app references — measured by: (a) clicking a TOC entry in a rendered preview scrolls to the corresponding section, (b) zero `image://` URLs survive into the output.
- A reader can also **copy the same Markdown to the clipboard** for direct paste into another tool — measured by: copy action produces byte-identical content to the file download.

### Non-Goals (explicit scope cuts)

- **NOT** modifying the JSON export (`--format json`). It stays full-fidelity (concepts, refs, all sections, every summary version) because *its job is full backup; the markdown export's job is human-readable distillation*. Confusing the two would weaken both.
- **NOT** persisting the original parser TOC as a separate column. *Reason:* the parser already lands the TOC into `BookSection` rows at parse time; reproducing the pre-edit TOC would require either a schema migration with backfill or re-parsing `Book.file_data` per export. Both are disproportionate work for a feature whose primary user rarely re-orders sections.
- **NOT** offering a "select non-default summary version" toggle in this iteration. *Reason:* multi-version selection adds significant UI surface for a rare flow. The default summary is what the user has already promoted as canonical; export should mirror that.
- **NOT** adding the Concepts Index, External References, or eval results to the new markdown export. *Reason:* this is a **summaries** export. Those artifacts remain in JSON for users who want them, and adding them to markdown here would re-introduce the kitchen-sink shape we're explicitly leaving behind.
- **DEPRECATING** library-level Markdown export. The CLI subcommand `bookcompanion export library --format markdown` and the API route `GET /api/v1/export/library?format=markdown` are removed in this iteration. *Reason:* a library-scope Markdown dump conflicts with the per-book "summaries" shape we're standardizing on (would either duplicate everything across books or require per-book selection UX, which multiplies complexity). Users who want a full-library backup use the JSON export, which remains untouched. The CLI emits a clear migration message: "Library Markdown export was removed in v1.6 — use `--format json` for full-library backups, or run `export book` per book."
- **NOT** offering PDF/EPUB/Word/HTML output formats. *Reason:* Markdown is portable and renders to all of these via Pandoc/external tools. Multiple output formats multiply rendering and testing surface for marginal value.
- **NOT** persisting export preferences (e.g., "always exclude TOC"). *Reason:* exports are infrequent, ad-hoc actions; per-export choices are cheaper than a settings surface.

## Solution Direction

A single user-facing concept: **"Export this book's summary as Markdown."** Two surfaces with parity, one rendering pipeline.

```
┌──────────────────────────────────────────────────────────────┐
│  Book Detail Page  (frontend, web UI)                        │
│  ┌─────────────────────────────────────────────┐             │
│  │ [Export summary]  [Copy as Markdown]        │ ← primary    │
│  │ Customize…                                  │ ← secondary  │
│  └─────────────────────────────────────────────┘             │
│         │                                                    │
│         ▼ (default OR after Customize)                       │
│   GET /api/v1/export/book/{id}?format=markdown&…             │
│         │                                                    │
│         ▼                                                    │
│   Browser download → toast: "Summary exported"               │
│   OR clipboard copy → toast: "Summary copied"                │
│   Default filename: `<book-slug>-summary-YYYYMMDD.md`        │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  CLI                                                         │
│  bookcompanion export book <id> --format markdown            │
│      [-o path.md]                                            │
│      [--no-book-summary] [--no-toc] [--no-annotations]       │
│      [--exclude-section <id>]…                               │
│                                                              │
│  REMOVED: bookcompanion export library --format markdown     │
│  (use --format json for full-library backups)                │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
              ExportService.export_book()
                       │
                       ▼
   New `_render_summary_markdown()` rendering with:
     • Front matter:  # Title  /  **Author:**  /  **Exported:**
     • TOC (anchor-linked, hierarchical via section depth)
     • Book summary
     • Per-section: ## Heading  →  summary  →  (highlights)  →  (notes)
```

**Key design choices:**

1. **One-click default + Customize…** in the UI optimizes for the common case (export everything I have for this book) while still letting power users prune. Defaults: book summary ON, all sections-with-a-summary ON, TOC ON, annotations ON.
2. **The new shape replaces today's `--format markdown` rendering.** Today's everything-dump goes away; JSON keeps full fidelity. Single source of truth, no two markdown shapes to maintain.
3. **Sections without a default summary are not selectable** in the UI list and are excluded by default in the CLI. They have nothing to contribute to a "summaries" export. The UI shows a small affordance ("12 of 17 sections summarized — 5 sections hidden because they have no summary").
4. **Annotations cascade with section selection.** Excluded section → its annotations are excluded too. Avoids orphan quotes pointing to nothing.
5. **TOC = current `BookSection` rows**, rendered with anchor links. We label it "Table of Contents" honestly: for unedited books it IS the original TOC; for books whose sections the user has merged/split it's the user's current view, which is what they actually want anyway.
6. **Image references in summaries are sanitized for portability.** In-app `image://N` URLs are replaced with `[Image: <alt-text>]` placeholders so the file renders cleanly in Obsidian, GitHub, VS Code, and any other Markdown viewer.
7. **Copy as Markdown** sits beside the download as a co-equal primary action. Same content, different sink — file vs. clipboard. Matches how Linear / Readwise expose Markdown.
8. **Post-action toast** confirms what happened (using the existing `stores/ui.ts:showToast()` infrastructure) so users have positive feedback that the export ran.

## User Journeys

### Primary Journey — One-click export from the UI

1. Reader is on `/books/:id` (book detail page) for a book they've finished summarizing.
2. They see two primary actions side-by-side: **"Export summary"** and **"Copy as Markdown"**, with a small "Customize…" link beneath.
3. They click **"Export summary"**.
4. Browser downloads `<book-slug>-summary-20260425.md` immediately, and the page shows a brief toast: *"Summary exported as <filename>"*.
5. They open it in Obsidian / a Markdown viewer; the file contains: title header, author, export date, table of contents (anchor-linked), book summary, every section that has a summary (with annotations rendered inline under each). Any in-app image references appear as `[Image: <alt>]` placeholders, not broken images.

### Primary Journey — Copy to clipboard from the UI

1. Same starting point as above.
2. Reader clicks **"Copy as Markdown"** instead of "Export summary".
3. Page shows a toast: *"Summary copied to clipboard"*.
4. Reader switches to Obsidian / Notion / Slack / wherever and pastes — the same Markdown content lands in their target tool.

### Alternate Journey — Customized export from the UI

1. Reader is on the book detail page; clicks **"Customize…"** instead of the primary button.
2. A panel/modal appears with four sections:
   - ☑ Book summary
   - ☑ Table of contents
   - ☑ Highlights & notes (annotations)
   - **Sections** — a list of all sections that have a summary, all checked by default. Plus a "Select all / Deselect all" master toggle. Sections without summaries are not in this list (or shown disabled with explanatory text).
3. Reader unchecks two sections, unchecks "Table of contents", clicks **"Export"**.
4. Browser downloads the Markdown file with only the selected items.

### Alternate Journey — CLI with exclusions

1. User runs:
   ```bash
   bookcompanion export book 3 --format markdown -o ~/notes/sun-tzu.md \
     --no-toc --exclude-section 14 --exclude-section 15
   ```
2. CLI writes the file with book summary + all summarized sections except 14 and 15 + annotations, no TOC.
3. CLI prints `Book exported to ~/notes/sun-tzu.md`.

### Error Journeys

| Scenario | What the user sees |
|---|---|
| Book has zero summaries (no `default_summary_id` on book or any section) AND user is on the book detail page | UI: both "Export summary" and "Copy as Markdown" buttons are disabled with tooltip "Generate a summary first" — there is nothing of substance to export. "Customize…" is also disabled. |
| Book is in `UPLOADING` status (file still being parsed) | UI: export buttons are disabled with tooltip "Book is still being processed". Available again on `PROCESSING` (partial summaries are valuable), `FAILED`, and `COMPLETED`. |
| User clicks "Customize…", deselects everything, clicks Export | A file is still produced (per design decision D6); contains only the front matter (title, author, exported date). Toast: "Summary exported (empty)". |
| Clipboard write fails (browser permission denied / Clipboard API unavailable) | Toast shows error: "Couldn't copy — try Export instead." Falls back gracefully without crashing the page. |
| CLI: invalid `--exclude-section <id>` (not a section of this book) | CLI exits with non-zero status: `Error: section <id> does not belong to book <book_id>.` No file is written. |
| CLI: book ID does not exist | CLI exits non-zero: `Error: book <id> not found.` (existing behavior; preserved.) |
| CLI invoked with no `--output` | Markdown is printed to stdout (existing behavior; preserved). All flag combinations work in stdout mode. |
| Browser: book has annotations referencing sections that are excluded | Those annotations are silently dropped (cascade rule). Their contents do not appear anywhere in the output. |
| Network drops mid-download | Browser shows its standard "download failed" UI. Re-clicking the button re-issues the request — server-side request is idempotent. |

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| Book has no sections at all | edge case for badly-parsed books | Sections list in Customize is empty with placeholder text "No sections found in this book." Export still works (front matter + book summary if present). |
| Book has summaries but no annotations | normal | "Highlights & notes" toggle is shown enabled but produces no inline content under sections. No empty headings. |
| All sections have summaries but the book itself doesn't (no `Book.default_summary_id`) | common pre-book-summary state | "Book summary" toggle is shown disabled with text "No book summary yet." Export skips that block. |
| Book title contains characters illegal in filenames (`/`, `:`, `?`, etc.) | OS-edge | Slugify aggressively for the download filename: lowercase, replace non-alphanumeric with `-`, collapse multiple dashes, trim, truncate to ~80 chars. |
| Two exports of the same book on the same day | desktop housekeeping | Filenames collide; browser auto-appends `(1)`, `(2)` per browser convention. We do not add a per-export uniqueness suffix. |
| Section title has Markdown special chars (`#`, `*`, `[`) | edge | Render the title verbatim in headings (Markdown handles it); the TOC anchor is derived from a slug of the title (lowercase, alphanumeric + dashes), matching GitHub-flavored Markdown anchor rules. |
| Sections with the same slugged title (duplicate anchor IDs) | rare | Append `-N` (`-2`, `-3`, …) to the duplicates' anchor IDs in TOC and section headings. Standard GFM behavior. |
| Section summary contains in-app image references like `![figure 3](image://17)` | common — eval has an `image_refs_preserved` assertion encouraging summaries to mention visuals | Render as `[Image: figure 3]` (alt-text-derived placeholder). If alt text is empty, fall back to `[Image]`. No `image://` URL ever appears in the output (per Goal: "zero `image://` URLs survive"). |
| Book has multiple authors | normal | Front matter renders `**Authors:**` (plural) joined by `, `. Single author renders `**Author:**` (singular). Zero authors renders `**Author:** Unknown`. |
| Book title is entirely non-ASCII (e.g., CJK) so slug becomes empty | edge | Default filename falls back to `book-<id>-summary-<YYYYMMDD>.md`. The H1 in the file still uses the original title verbatim. |
| CLI invoked on a book with zero summaries anywhere | edge | Produce a front-matter-only file (or stdout) silently with exit code 0. CLI users are deliberate by definition (the UI's D18 footgun rule does not apply); the Unix-style behavior is to do what was asked without unsolicited warnings. |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | Replace today's `--format markdown` shape; do not introduce a parallel "summary" mode. | (a) Parallel mode `--format markdown-summary`, (b) Generalize so the existing everything-dump becomes "all toggles on", (c) **Replace.** | One markdown shape is simpler to maintain, document, and reason about. Today's everything-dump is rarely used in practice and overlaps heavily with JSON. JSON remains the full-fidelity backup. |
| D2 | UI primary actions are one-click "Export summary" and "Copy as Markdown" (co-equal, see D16); "Customize…" is the secondary configuration affordance. | (a) Modal-always (two clicks every time), (b) Inline panel always visible, (c) **One-click + customize.** | Industry pattern for export flows (Readwise, Google Docs, Linear). The common case is "give me everything I have for this book"; forcing every user through a checkbox tree adds friction without value. |
| D3 | Defaults: book summary ON, all sections-with-summary ON, TOC ON, annotations ON. | (a) All ON, (b) All ON except TOC, (c) All OFF (force conscious choice). | Maximally informative export by default matches the one-click UX. TOC is cheap to skim past if unwanted; cheaper than a missing-feature complaint. |
| D4 | TOC = current `BookSection` rows (rendered with anchor links), labeled "Table of Contents". | (a) **Current sections** (zero schema work), (b) Add `Book.original_toc_json` column + backfill, (c) Re-parse `Book.file_data` per export. | The original TOC is not separately persisted (`epub_parser.py:162` confirms). For unedited books the sections list IS the original TOC; for edited books, the user's current view is what they actually want. (b) and (c) are large lifts for a marginal accuracy gain on edited books. |
| D5 | CLI exposes one flag per UI toggle, all using exclusion semantics: `--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section <id>` (repeatable). | (a) **All four exclusion flags**, (b) Add inclusion `--only-section` on top, (c) Bundle annotations under a generic `--no-extras` flag. | One flag per UI toggle preserves UI/CLI parity (an explicit goal). Exclusion matches the mental model when defaults already include everything. Inclusion-only flips the burden onto every invocation; bundling annotations under `--no-extras` is more flexible only if more "extras" emerge later — annotations are the only one in scope today, so explicit is cleaner. |
| D6 | Exports from the Customize-then-export path are always allowed, even if the result is empty (just front matter). The one-click path has a different rule — see D18. | (a) Disable button when no summaries exist anywhere, (b) Block submission when all toggles off, (c) **Always allow on the deliberate path.** | Trust the user once they've made a deliberate choice via Customize. "I want a Markdown file with just the title and author" is a legitimate request we should not gatekeep. The one-click footgun (clicking Export on a book with no summaries) is handled separately by D18. |
| D7 | Default download filename: `<book-slug>-summary-<YYYYMMDD>.md`. | (a) `<slug>-summary.md`, (b) **`<slug>-summary-<YYYYMMDD>.md`**, (c) `book-<id>-summary.md`. | Date suffix lets a user export the same book multiple times across iterations of summarization (re-summarized with a better preset, etc.) without overwriting earlier exports. ID-based naming is opaque. |
| D8 | Markdown structure: front matter → TOC (with anchor links) → book summary → sections inline (with annotations under each). | (a) **TOC with anchor links**, (b) plain TOC (no links), (c) no TOC ever. | Anchor-linked TOC is the standard long-doc shape and works in every common Markdown viewer. Plain TOC loses the navigation value users expect. Skipping TOC entirely contradicts the requirement. |
| D9 | Front matter uses plain Markdown lines (`# Title`, `**Author:**`, `**Exported:**`), not YAML frontmatter. | (a) **Plain lines**, (b) YAML frontmatter, (c) None. | Plain lines render consistently in every viewer. YAML frontmatter is Obsidian/Hugo-specific and renders verbatim or as a metadata table elsewhere; not portable enough as the default. |
| D10 | Annotations cascade with section selection; an excluded section's annotations are also excluded. | (a) **Cascade**, (b) Independent — annotations always included when toggle is on. | Independent annotations would produce orphan quotes pointing to sections not in the document. Cascade keeps the export internally coherent. |
| D11 | Use default summary version only; no per-section version picker. | (a) **Default only**, (b) Per-section picker, (c) Single global override (e.g., "use latest"). | The user has already promoted a version to default; the export mirroring that is the right behavior. Per-section picking is a heavy UI for a rare flow. A global override could be added later if a real need surfaces. |
| D12 | JSON export (`--format json`) is unchanged. | (a) **Unchanged**, (b) Apply selection to JSON too. | JSON is the full-backup format; markdown is the human-readable distillation. Conflating them weakens both. Filtering JSON is also a more invasive backend change. |
| D13 | Sections without a default summary are not selectable in the Customize UI. | (a) **Not in the list** (with a count line: "12 of 17 sections summarized"), (b) In the list but disabled, (c) In the list and selectable (would emit just the section heading with no body). | Including unsummarized sections in a "summaries export" produces empty, confusing entries. Hiding with a count communicates the situation clearly without polluting the UI. |
| D14 | In-app `image://N` URLs in summaries are replaced with `[Image: <alt-text>]` placeholders. | (a) **Replace with placeholder text**, (b) Embed images as base64 data URLs, (c) Strip silently, (d) Leave as-is. | Placeholders render cleanly in every Markdown viewer and preserve the visual context as readable text. Base64 inflates files into multi-MB documents that some viewers truncate; stripping silently loses information; leaving as-is produces broken images outside Book Companion. |
| D15 | Export buttons are available on the book detail page unless the book is in `UPLOADING` status. | (a) **Available unless UPLOADING**, (b) Available only when COMPLETED, (c) Always available. | A book in `PROCESSING` may already have valuable section summaries; gating to `COMPLETED` only forces the user to wait unnecessarily. `FAILED` books often have partial summaries worth exporting. `UPLOADING` is the only state where there's literally nothing meaningful to export. CLI is unaffected — power users can export at any state. |
| D16 | "Copy as Markdown" is a co-equal primary action alongside "Export summary"; both honor the same Customize selection. | (a) **Co-equal primary**, (b) Inside Customize panel only, (c) Defer to a future iteration. | Markdown is often pasted into Obsidian/Notion/Slack rather than saved. Surfacing both sinks at the same level matches Linear / Readwise. The implementation cost is negligible — same content, different sink. Hiding it inside Customize buries a fast-path. |
| D17 | After an export action, show a brief toast confirming what happened. | (a) **Toast via `stores/ui.ts:showToast()`**, (b) No feedback (browser handles it), (c) Inline button spinner. | The existing toast infrastructure (per the v1.5 polish-followups context) makes this a 3-line wire-up. Provides positive confirmation for download (where browsers vary in how visibly they signal it) and is essential for clipboard copy (browsers give no native feedback). |
| D18 | Primary export buttons are disabled (with tooltip "Generate a summary first") when the book has no summaries anywhere. The "Always allow exports" rule (D6) applies to the Customize-then-export path; the disabled-when-empty rule applies to the one-click path. | (a) **Disabled on one-click path, allowed on customize path**, (b) Always disabled, (c) Always allowed. | The two rules look contradictory but serve different cases. One-click on an empty book produces a file with nothing useful — that's a footgun and the user almost certainly wants to be told. Once the user has opened Customize and made a deliberate choice to export with no toggles on, that's their call (e.g., they want a stub file with title + author). Disabling Customize too would block legitimate intent. |

## Success Metrics

| Metric | Baseline | Target | Measurement |
|---|---|---|---|
| Time to export a book's summary (UI) from book detail page | N/A (no UI today) | ≤ 5 seconds end-to-end (click to file in download folder) for a 30-section book with default selection | Manual stopwatch in /verify; could later be a Playwright assertion |
| CLI export remains zero-friction | Single command works today | Default invocation `bookcompanion export book <id> --format markdown -o file.md` produces the same shape as the UI's one-click export | Side-by-side diff of UI download vs CLI output for a fixture book |
| Anchor-linked TOC works in real viewers | N/A | TOC entries clickable and scroll to the right section in: GitHub web preview, VS Code Markdown preview, Obsidian | Manual /verify step; capture screenshots |
| Render cost is negligible | Today's markdown render is in-process, fast | Generating a markdown export for a 30-section book completes in < 500ms server-side (excluding network) | API timing logs in /verify |
| No regression in JSON export | Current JSON export passes all tests | All existing JSON export tests still pass; JSON output byte-for-byte unchanged for a fixture book | Existing pytest suite; add a snapshot test |
| Image references survive sanitization | Today's export leaks `image://N` URLs | Zero `image://` substrings in any exported markdown for any book | Pytest assertion: `"image://" not in exported_md` for fixture books with images |
| Copy-vs-download parity | N/A | Clipboard payload byte-equal to file download payload for the same selection | Playwright e2e: capture both, assert equality |

## Research Sources

| Source | Type | Key Takeaway |
|---|---|---|
| `backend/app/services/export_service.py` | Existing code | Today's `_render_markdown()` dumps Title + Author + Quick Summary + Sections (with all summaries) + Concepts + Annotations + External References per book. We replace the rendering pipeline; we keep `_collect_book_data()` mostly intact (it gathers more than we'll render, which is fine — we filter at render time). |
| `backend/app/cli/commands/export_cmd.py` | Existing code | Existing `bookcompanion export book` Typer command takes `--format` and `--output`; we extend with `--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section` (multi-value option). |
| `backend/app/api/routes/export.py` | Existing code | Existing `GET /api/v1/export/book/{id}?format=markdown` returns `text/markdown` with `Content-Disposition: attachment`. We extend the query string with selection params and update the filename. |
| `backend/app/services/parser/epub_parser.py:162` | Existing code | Comment confirms original parser TOC is not stored separately ("Since we don't store it, re-derive from TOC"). Decision D4 follows. |
| `backend/app/db/models.py` (Book, BookSection) | Existing code | No `original_toc_json` column on Book. `metadata_` JSON exists but doesn't carry TOC. Confirms D4. |
| Readwise export UX (https://help.readwise.io/article/118-exporting-your-data) | External pattern | Per-book Markdown download with default filename derived from title; minimal selection. Validates one-click default. |
| Notion export-with-subpages | External pattern | Modal with checkboxes for "Include subpages", "Include comments". Validates the Customize panel shape. |
| GitHub-flavored Markdown anchor rules | External standard | Anchors are slugified titles (lowercase, alphanumeric + dashes); duplicate slugs get `-2`, `-3` suffixes. Followed in D8 / Edge Cases. |

## Open Questions

| # | Question | Owner | Needed By |
|---|---|---|---|
| O1 | Where in the book detail page header does the "Export summary" / "Copy as Markdown" pair live — next to existing primary actions, in an overflow menu, or in a dedicated Export tab? | Maneesh | Before /spec |
| O2 | Should the Customize panel be a modal, a slide-over drawer, or an inline expanding section? (The UX shape from D2 is locked; the visual treatment isn't.) | Maneesh | Before /spec |
| O3 | Annotation rendering format under each section: blockquote of the highlighted text + indented note line, or a more structured "highlight + note" block? Worth confirming format with a small visual mock during /spec. | Maneesh | During /spec |
| O4 | Should the export include a "Notes" footer section for free-floating notes that aren't tied to a section's selected text? (Today's annotations table allows annotations with no `selected_text`.) | Maneesh | Before /spec |

## Review Log

| Loop | Findings | Changes Made |
|---|---|---|
| 1 | (a) Section summaries can contain `image://N` references that break in external viewers; (b) UI button availability vs book lifecycle status was undefined; (c) Copy-to-clipboard sink missing as a parallel action; (d) No post-action UI feedback specified | Added D14 (image-ref placeholders), D15 (UPLOADING gates the button), D16 (Copy as Markdown co-equal action), D17 (toast feedback). Updated Solution Direction diagram, Primary Journeys (added Copy journey), Edge Cases (image refs, multi-author, CJK title slug, UPLOADING, clipboard failure, CLI stdout), Goals (added image-sanitization and copy-parity criteria), Success Metrics (added two new metrics). Promoted the "disabled when no summaries" rule to D18 to reconcile the apparent tension with D6. |
| 2 | (a) D5 listed only three CLI flags but the requirement has four toggles (annotations missing); (b) O3 left library Markdown scope unresolved; (c) D6 vs D18 wording overlap; (d) D2 still implied a single primary action even after D16 introduced the co-equal Copy action | D5: rewritten to enumerate all four flags (`--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section`) with explicit UI/CLI parity rationale. O3: closed by deprecating library Markdown export (CLI subcommand and API route both removed; non-goals updated; CLI block annotated). D6: clarified to apply to the Customize-then-export path only, deferring the empty-book one-click case to D18. D2: updated to call out both primary actions plus the secondary Customize affordance. Renumbered O4/O5 → O3/O4 after closing the original O3. |
| Final | CLI behavior on a book with zero summaries was unspecified (D18 covered UI only) | Added an Edge Cases row: CLI produces a front-matter-only file silently with exit code 0, consistent with the "trust the user" CLI ethos. |
