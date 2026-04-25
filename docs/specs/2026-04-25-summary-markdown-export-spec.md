# Summary Markdown Export — Spec

**Date:** 2026-04-25
**Status:** Draft
**Tier:** 2 — Enhancement / UX Overhaul
**Requirements:** `docs/requirements/2026-04-25-summary-markdown-export.md`

---

## 1. Problem Statement

Readers invest hours generating per-section and book-level summaries plus highlights/notes inside Book Companion, but there is no usable path to take that knowledge **out**. The CLI's `bookcompanion export book <id> --format markdown` dumps a kitchen-sink shape (concepts, refs, eval data, every section) with zero selection, and the web UI has no export affordance at all. We're replacing the existing markdown render with a **summaries-focused, selectable, portability-sanitized** shape — exposed via one-click UI buttons, a Customize modal, and parity CLI flags. Primary success metric: a power reader can produce a clean Obsidian-paste-ready Markdown file for any book in **≤ 1 click** from `/books/:id`.

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|---------------|
| G1 | One-click default export from book detail page | `Export summary` button reachable in ≤ 1 click from `/books/:id`; produces full export with default selections |
| G2 | Customizable export (toggle book summary, sections, TOC, annotations) | Every UI toggle combination produces a valid Markdown file containing only the requested items |
| G3 | UI ↔ CLI parity for selection | Every UI toggle has a CLI equivalent (`--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section`); diff between UI and CLI output for the same selection is zero |
| G4 | Clean rendering in standard Markdown viewers | (a) Every TOC link resolves to its section heading in GitHub web, VS Code preview, and Obsidian (manual /verify step); (b) automated test asserts `"/api/v1/images/" not in output` for every fixture book with images |
| G5 | Copy-to-clipboard parity with file download | Clipboard payload byte-equal to file download payload for the same selection |
| G6 | No regression in JSON export | All existing JSON export tests still pass; JSON output for a fixture book byte-for-byte unchanged |

---

## 3. Non-Goals

- **Library-level Markdown export** — `bookcompanion export library --format markdown` and `GET /api/v1/export/library?format=markdown` are removed. Reason: a library-scope Markdown dump conflicts with the per-book summaries shape (would either duplicate everything across books or require per-book selection UX). Users who want a full-library backup use JSON.
- **Filtering JSON exports** — `--format json` is unchanged (full-fidelity backup). Reason: JSON's job is full backup; markdown's job is human-readable distillation. Conflating them weakens both.
- **Per-section summary version picker** — exports use `Section.default_summary_id` only. Reason: the user has already promoted a version to default; multi-version selection is a heavy UI for a rare flow.
- **Persisting export preferences** — every export is a fresh selection. Reason: exports are infrequent, ad-hoc actions; per-export choices are cheaper than a settings surface.
- **Persisting original parser TOC as a separate column** — TOC = current `BookSection` rows. Reason: the parser does not store the original TOC (`epub_parser.py:162` confirms); a schema migration with backfill is disproportionate work for a feature whose primary user rarely re-orders sections.
- **Concepts Index, External References, eval results in Markdown export** — these stay in JSON. Reason: this is a *summaries* export.
- **PDF / EPUB / Word / HTML output formats** — Markdown renders to all of these via Pandoc. Reason: multiple formats multiply rendering and testing surface for marginal value.

---

## 4. Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | Replace `_render_markdown()` shape; do not introduce a parallel "summary" mode. | (a) Parallel `--format markdown-summary`, (b) Generalize so existing dump = "all toggles on", (c) **Replace.** | One markdown shape is simpler to maintain. JSON remains the full-fidelity backup. |
| D2 | UI surfaces TWO co-equal primary actions (`Export summary`, `Copy as Markdown`) plus a secondary `Customize…` text link, all rendered in the existing `.actions` div alongside the `Read` button on `BookOverviewView.vue`. | (a) Inline in `.actions` (Recommended; chosen), (b) Overflow `⋯` menu, (c) New "Export" tab. | Inline preserves discoverability without adding a new surface. The `.actions` row already houses primary verbs for the book. |
| D3 | Defaults: book summary ON, all sections-with-summary ON, TOC ON, annotations ON. | (a) **All ON**, (b) All ON except TOC, (c) All OFF. | Maximally informative export by default matches the one-click UX. |
| D4 | TOC = current `BookSection` rows rendered with GFM-style anchor links, labeled "Table of Contents". | (a) **Current sections** (zero schema work), (b) New `Book.original_toc_json` column + backfill, (c) Re-parse `Book.file_data` per export. | The original TOC is not separately persisted (`epub_parser.py:162`). For unedited books the sections list IS the original TOC; for edited books, the user's current view is what they want. |
| D5 | CLI exposes one flag per UI toggle, all exclusion-style: `--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section <id>` (repeatable). | (a) **Four exclusion flags** (chosen), (b) Add inclusion `--only-section`, (c) Bundle annotations under `--no-extras`. | UI/CLI parity is an explicit goal. Exclusion matches the mental model when defaults already include everything. |
| D6 | Customize-then-export path always allows submission, even if the result is empty (front matter only). One-click path is gated by D18. | (a) Disable when no summaries, (b) Block submission when all toggles off, (c) **Always allow on the deliberate path.** | Trust the user once they've made a deliberate Customize choice. |
| D7 | Default download filename: `<book-slug>-summary-<YYYYMMDD>.md`. | (a) `<slug>-summary.md`, (b) **`<slug>-summary-<YYYYMMDD>.md`**, (c) `book-<id>-summary.md`. | Date suffix lets users export the same book multiple times across iterations of summarization without overwriting. |
| D8 | Markdown structure: front matter → TOC (anchor-linked) → book summary → sections inline (annotations under each) → optional `## Notes` footer. | (a) **Anchor-linked TOC**, (b) plain TOC (no links), (c) no TOC ever. | Anchor-linked TOC is the standard long-doc shape; works in every common Markdown viewer. |
| D9 | Front matter uses plain Markdown lines (`# Title`, `**Author:**`, `**Exported:**`), not YAML frontmatter. | (a) **Plain lines**, (b) YAML frontmatter, (c) None. | Plain lines render consistently in every viewer. YAML frontmatter is Obsidian/Hugo-specific. |
| D10 | Annotations cascade with section selection — excluding a section excludes its annotations. | (a) **Cascade**, (b) Independent. | Independent annotations would produce orphan quotes pointing to sections not in the document. |
| D11 | Default summary version only; no per-section version picker. | (a) **Default only**, (b) Per-section picker, (c) Global override. | The user has already promoted a version to default; export mirrors that. |
| D12 | JSON export (`--format json`) is unchanged. CLI exclusion flags + `--format json` is a **hard error** (exit 2). | (a) **Hard error**, (b) Silent ignore, (c) Warn + proceed. | JSON is full-fidelity backup; allowing exclusion flags to silently no-op risks user confusion (thinks they got a filtered export, got the full backup instead). |
| D13 | Sections without a `default_summary_id` are not selectable in the Customize UI list; the UI shows a one-line count ("12 of 17 sections summarized — 5 hidden"). | (a) **Not in the list**, (b) In the list but disabled, (c) Selectable but emit empty. | Including unsummarized sections in a "summaries export" produces empty, confusing entries. |
| D14 | Sanitize in-app image URLs: `![alt](/api/v1/images/{id})` → `[Image: alt]` (or `[Image]` if alt empty). Also strip `<img src="/api/v1/images/...">` HTML tags. **The requirements doc described the legacy `image://N` scheme; the codebase actually uses `/api/v1/images/{id}` per `image_url_rewrite.py:63-96`** — sanitizer targets the real pattern. | (a) **Real pattern** (chosen), (b) Match both real + legacy, (c) Skip sanitization. | The legacy `image://` scheme is never written by current code; matching it is dead-pattern overhead. Only `/api/v1/images/{id}` ever appears in `Summary.summary_md`. |
| D15 | Export buttons are disabled (with tooltip) only when book is in `UPLOADING` or `PARSING` status. Available in `PARSED`, `SUMMARIZING`, `COMPLETED`, `PARSE_FAILED`. | (a) **Disable only on UPLOADING/PARSING**, (b) Available only when COMPLETED, (c) Always available. | A book in `SUMMARIZING` may have valuable section summaries already; gating to COMPLETED forces unnecessary waiting. `PARSE_FAILED` books often have no content but are also uncommon — keep them enabled and let the empty-state rule (D18) handle them. |
| D16 | `Copy as Markdown` is a co-equal primary action alongside `Export summary`; both honor the same Customize selection. | (a) **Co-equal primary**, (b) Inside Customize panel only, (c) Defer to next iteration. | Markdown is often pasted into Obsidian/Notion/Slack rather than saved. Implementation cost is negligible — same content, different sink. |
| D17 | After every export action (download or copy), show a toast via `useUiStore().showToast()`. **Spec adds a `<ToastContainer>` mount in `AppShell.vue` since the store exposes `toasts` but no consumer renders it today.** | (a) **Toast + add outlet**, (b) No feedback, (c) Inline button spinner. | The store infrastructure is half-built; this spec finishes the wiring. Browser-native download UI is inconsistent across browsers, and clipboard copy gives no native signal at all. |
| D18 | One-click primary buttons are disabled (tooltip "Generate a summary first") when book has no summaries anywhere. The "always allow" rule (D6) applies only to the Customize path. | (a) **Disabled on one-click; allowed on Customize**, (b) Always disabled, (c) Always allowed. | One-click on an empty book is a footgun; deliberate Customize-then-export is the user's call. |
| D19 | Selection params travel as **GET querystring**: `include_book_summary`, `include_toc`, `include_annotations` (booleans, default true) and `exclude_section` (repeatable int). | (a) **GET querystring**, (b) POST with JSON body. | GET preserves browser-friendly download / `<a href>` semantics, idempotency, and cacheability. Querystring length is fine for ~50 excluded sections. |
| D20 | Render pipeline lives in a new `_render_summary_markdown(book_data, selection)` method on `ExportService`. The selection-filtering happens in the renderer, not the collector — `_collect_book_data()` is unchanged so JSON keeps full fidelity. | (a) **Filter at render time** (chosen), (b) Filter inside `_collect_book_data` (would require dual code paths). | One source of truth for collected data. JSON consumes the unfiltered shape; markdown filters at render. |

---

## 5. User Journeys

### 5.1 One-click export from UI (primary)
1. User on `/books/:id`. The `.actions` row shows `[Read ▶] [Export summary] [Copy as Markdown]` with a `Customize…` text link beneath.
2. Click `Export summary`. Frontend calls `GET /api/v1/export/book/{id}?format=markdown` (no selection params → all defaults).
3. Browser downloads `<slug>-summary-<YYYYMMDD>.md`. Toast: *"Summary exported as <filename>"*.

### 5.2 Copy-to-clipboard from UI (primary)
1. Same starting point.
2. Click `Copy as Markdown`. Frontend issues the same GET, reads body as text, calls `navigator.clipboard.writeText(text)`.
3. Toast: *"Summary copied to clipboard"* (or, on permission failure, *"Couldn't copy — try Export instead."*).

### 5.3 Customized export
1. Click `Customize…`. Modal opens (reusing `PresetPickerModal` shell pattern).
2. Modal shows four toggles + a section list with master toggle. Sections without default summaries are not in the list; a count line reads "12 of 17 sections summarized".
3. User unchecks two sections + the TOC, clicks `Export` (or `Copy`).
4. Frontend issues GET with `include_toc=false&exclude_section=14&exclude_section=15`. Download or copy proceeds; toast confirms.

### 5.4 CLI with exclusions
```bash
bookcompanion export book 3 --format markdown -o ~/notes/sun-tzu.md \
  --no-toc --exclude-section 14 --exclude-section 15
```
Writes file with book summary + summarized sections except 14/15 + annotations, no TOC. Prints `Book exported to ~/notes/sun-tzu.md`.

---

## 6. Functional Requirements

### 6.1 Backend rendering pipeline (`ExportService`)

| ID | Requirement |
|----|-------------|
| FR-B1 | Add `_render_summary_markdown(book_data: dict, selection: ExportSelection) → str` that produces the new markdown shape from the existing `_collect_book_data()` output. |
| FR-B2 | Replace the existing `_render_markdown()` rendering for `--format markdown`. The old shape is removed. |
| FR-B3 | `_collect_book_data()` is unchanged — it still gathers concepts, refs, eval data, every section. JSON export remains byte-for-byte identical for the same fixture book. |
| FR-B4 | Define `ExportSelection` (pydantic model or dataclass) with fields: `include_book_summary: bool = True`, `include_toc: bool = True`, `include_annotations: bool = True`, `exclude_section_ids: set[int] = empty`. |
| FR-B5 | Image-URL sanitizer: zero `/api/v1/images/` substrings may survive in output. Implementation MUST apply these two regexes, in this order, to every `Summary.summary_md` before rendering: <br>(1) `!\[([^\]]*)\]\(/api/v1/images/\d+\)` → `[Image: $1]` if `$1` non-empty, else `[Image]` <br>(2) `<img\s+[^>]*src=["']/api/v1/images/\d+["'][^>]*>` → `[Image: <alt>]` derived from the tag's `alt="..."` attribute, or `[Image]` if `alt` is absent / empty <br>Order matters because (1) does not match raw `<img>` tags. The placeholder text uses verbatim alt text — even if the alt contains `[`, `]`, or parentheses, the resulting `[Image: ...]` renders as literal text in every common viewer (no Markdown link parsing risk because there's no following `(...)`). |
| FR-B6 | Markdown structure (top-to-bottom): <br>1. `# {Book.title}` (verbatim) <br>2. `**Author:** {name}` or `**Authors:** {name}, {name}` (per author count); `**Author:** Unknown` if zero authors <br>3. `**Exported:** YYYY-MM-DD` <br>4. (if `include_toc`) `## Table of Contents` followed by a hierarchical list with `[Section title](#gfm-slug)` links; **the TOC alone reflects depth** via nested bullets (`BookSection.depth`) <br>5. (if `include_book_summary` AND `Book.default_summary_id` is set) book summary content directly (no extra heading) <br>6. For each section with a `default_summary_id` whose `id ∉ exclude_section_ids`, in `BookSection.order_index` ascending order: <br>&nbsp;&nbsp;`## {section.title}` — **flat H2 for every section regardless of `depth`** (the TOC's nested bullets convey hierarchy; section bodies stay at a single outline level so every section is a peer in document outlines / Obsidian sidebar). Anchor is the heading's GFM auto-slug; **no inline `<a id>` tag**. <br>&nbsp;&nbsp;{summary_md, sanitized per FR-B5} <br>&nbsp;&nbsp;(if `include_annotations` AND section has annotations with non-empty `selected_text`) `### Highlights` block (see FR-B8) <br>7. (if `include_annotations` AND there are free-floating annotations on this book — annotations with empty/null `selected_text`) `## Notes` footer (see FR-B9) |
| FR-B7 | TOC slug generation MUST follow GFM rules to align with viewer auto-anchors (GitHub web, VS Code preview, Obsidian, Marked-render variants): lowercase, drop characters that are not alphanumeric / space / hyphen / underscore, replace whitespace with `-`, collapse consecutive `-`. Duplicate slugs disambiguate via GFM convention: first occurrence is bare slug `s`; subsequent occurrences append `-1`, `-2`, … (NOT `-2`, `-3`, …) in section-encounter order. The same disambiguation table is used to compute the TOC link target — sections themselves emit only `## {title}` and rely on the viewer's auto-anchor matching the predicted slug. |
| FR-B8 | Each annotation under `### Highlights` renders as a Markdown blockquote of `selected_text`, optionally followed by an indented `> — Note: {note}` line if `note` is non-empty. Empty line between annotations. |
| FR-B9 | `## Notes` footer renders free-floating annotations (annotations whose `content_id` references this book or a section in this book AND `selected_text` is empty/null) as a `- ` bullet list of the `note` field. If no such annotations exist, the section is omitted entirely (no empty heading). Cascade rule (D10) does NOT apply to free-floating notes — they are book-level, not section-level, so they appear regardless of which sections are excluded. |
| FR-B10 | Front-matter Markdown is plain lines (D9), never YAML. |
| FR-B11 | If `include_book_summary` is true but `Book.default_summary_id` is null, render only the title + author + exported lines, then proceed to TOC/sections (no error, no placeholder). |
| FR-B12 | Section summaries from `Summary.summary_md` are rendered verbatim AFTER image-URL sanitization. No additional reflow, dedent, or markdown re-rendering. |

### 6.2 API contract delta

| ID | Requirement |
|----|-------------|
| FR-A1 | `GET /api/v1/export/book/{book_id}` accepts new query params (all optional, all only meaningful for `format=markdown`): `include_book_summary: bool = true`, `include_toc: bool = true`, `include_annotations: bool = true`, `exclude_section: list[int] = []` (repeatable). |
| FR-A2 | Filename header: `Content-Disposition: attachment; filename="{book-slug}-summary-{YYYYMMDD}.md"`. The filename uses `slugify(book.title)` (lowercase, alphanumeric + dashes, max 80 chars); falls back to `book-{id}-summary-{YYYYMMDD}.md` when slug is empty (CJK-only titles, etc.). For `format=json` the filename remains `book_{id}.json` (unchanged). |
| FR-A3 | On `format=json`, selection params are accepted, **never validated, and never affect output** — the response is full-fidelity per D12. The CLI is the strict surface (FR-C5); the API stays permissive for browser-direct calls. |
| FR-A4 | `GET /api/v1/export/library?format=markdown` is **removed**. The route returns `410 Gone` with body `{"detail": "Library Markdown export was removed in v1.6 — use format=json for full-library backups, or use /api/v1/export/book/{id}?format=markdown per book."}`. `format=json` on this route is unchanged. |
| FR-A5 | Error responses (only meaningful for `format=markdown` per FR-A3): 404 when book does not exist; 400 if `exclude_section` contains an integer that is not a section of this book (validated server-side; nothing exported on validation failure). |
| FR-A6 | On `format=markdown`, the response carries header `X-Empty-Export: true` when the rendered body contains only the front matter (zero `## ` headings AND no book-summary content emitted), else the header is omitted (or set to `false`). The frontend uses this header to pick the empty toast variant per FR-F12. The header is not set on `format=json` responses. |

### 6.3 CLI delta

| ID | Requirement |
|----|-------------|
| FR-C1 | `bookcompanion export book <id> --format markdown` accepts new flags: `--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section <id>` (Typer `multiple=True`). All default to "include" / empty. |
| FR-C2 | `--output` / `-o` semantics preserved: write to file if given, else print to stdout. All flag combinations work in both file and stdout modes. |
| FR-C3 | `--exclude-section <id>` for an `<id>` that is not a section of the book exits non-zero (status 1) with `Error: section <id> does not belong to book <book_id>.` No file is written. |
| FR-C4 | `bookcompanion export library --format markdown` is **removed**. Invoking it exits non-zero (status 2) with: `Library Markdown export was removed in v1.6 — use --format json for full-library backups, or run 'export book' per book.` `--format json` continues to work unchanged. |
| FR-C5 | Any of `--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section` combined with `--format json` exits status 2 with: `Error: --no-* and --exclude-section flags are only valid with --format markdown. JSON exports are full-fidelity.` |
| FR-C6 | A book with zero summaries anywhere AND `--format markdown` AND no `--no-*` flags produces a front-matter-only file (or stdout) with exit 0 — no warning, no error. CLI's "trust the user" ethos (D18 footgun rule applies to UI only). |

### 6.4 Frontend (Vue 3)

| ID | Requirement |
|----|-------------|
| FR-F1 | Add three actions to `BookOverviewView.vue`'s `.actions` div, after the existing `Read` button: <br>• Primary button: `Export summary` <br>• Primary button: `Copy as Markdown` <br>• Secondary text link: `Customize…` (positioned beneath, smaller font, underlined-on-hover) |
| FR-F2 | All three actions are disabled (with `aria-disabled` + tooltip) when `book.status ∈ {UPLOADING, PARSING}`. Tooltip: *"Book is still being processed."* |
| FR-F3 | `Export summary` and `Copy as Markdown` are additionally disabled when book has no summaries (`book.default_summary_id` is null AND no `book.sections[*].has_summary`). Tooltip: *"Generate a summary first."* `Customize…` remains enabled in this state — D6/D18 split. |
| FR-F4 | `Export summary` click → `GET /api/v1/export/book/{id}?format=markdown` (no selection params on default path). Read response as Blob, trigger download via existing `triggerDownload(response, filename)` helper in `frontend/src/api/export.ts`. Filename comes from the server's `Content-Disposition` header; if parsing fails, fall back to `book-{id}-summary-{YYYYMMDD}.md`. |
| FR-F5 | `Copy as Markdown` click writes the same fetched markdown to the clipboard. To survive Safari's user-gesture-chain rule (which rejects `clipboard.writeText` after an `await fetch`), the implementation MUST prefer the `ClipboardItem`-with-promise API and fall back to the legacy path only when unavailable: <br><pre>if (navigator.clipboard?.write && window.ClipboardItem) {<br>  await navigator.clipboard.write([new ClipboardItem({<br>    'text/plain': fetch(url).then(r => r.blob())<br>  })])<br>} else {<br>  const text = await fetch(url).then(r => r.text())<br>  await navigator.clipboard.writeText(text)<br>}</pre>On `DOMException` / undefined `navigator.clipboard`, show error toast (FR-F12) and do NOT throw. |
| FR-F6 | `Customize…` click → open new `ExportCustomizeModal.vue` (reuses the structural pattern of `PresetPickerModal.vue`: fixed overlay, `.modal-body` width `min(560px, 92vw)`, Escape closes, `Export` + `Copy` + `Cancel` footer). |
| FR-F7 | `ExportCustomizeModal.vue` content: <br>• Four checkboxes: Book summary (disabled when `book.default_summary_id` is null, label suffix " — no book summary yet"), Table of contents, Highlights & notes, Sections. <br>• The Sections checkbox is **tri-state**: `checked` when all individual section checkboxes are checked, `unchecked` when none are, `indeterminate` (set via `el.indeterminate = true` in a `ref` watcher) for any partial state. Click behavior: `indeterminate → checked → unchecked → checked → …` (clicking from indeterminate goes to checked first, matching Gmail/GitHub list-selection convention). Toggling Sections to checked re-checks every individual section; toggling to unchecked unchecks all. <br>• A scrollable section list ordered by `BookSection.order_index` ascending, containing only sections where `has_summary === true`, each with an individual checkbox prepopulated. <br>• Below the list, a one-line muted footer: `{summarized_count} of {total_count} sections summarized — {hidden} hidden because they have no summary` (omit the "— N hidden" clause when hidden = 0). <br>• Footer buttons: `Cancel`, `Export`, `Copy as Markdown`. |
| FR-F8 | Modal `Export` and `Copy as Markdown` issue the same GET with selection params built from the toggles (booleans) and the unchecked section list (`exclude_section` repeated). |
| FR-F9 | Add `frontend/src/api/export.ts` extension: `interface SummaryExportSelection { include_book_summary?: boolean; include_toc?: boolean; include_annotations?: boolean; exclude_section_ids?: number[] }` and `exportBookSummary(bookId: number, selection?: SummaryExportSelection): Promise<{ blob: Blob; filename: string; text: string }>` returning the response Blob, the parsed filename, AND the text content (so Copy can reuse the same body without a second fetch). |
| FR-F10 | The existing `ExportOptions` interface and `exportBook()` function in `frontend/src/api/export.ts` remain unchanged for any other callers (e.g., `BackupSettings.vue`'s library JSON export). |
| FR-F11 | `BackupSettings.vue` library export UI: **replace** the existing format-selector dropdown with a single `Export library (JSON)` button. The `exportLibrary()` helper in `frontend/src/api/export.ts` is constrained to `format: 'json'` — the `'markdown'` branch and any references to it are removed. Reason: JSON is now the only valid library export, so a single-item dropdown is dead UI. |
| FR-F12 | After every export action, call `useUiStore().showToast(message, type)` with: <br>• Download success (non-empty): `("Summary exported as {filename}", 'success')` <br>• Download success, **empty** (`X-Empty-Export: true` per FR-A6): `("Summary exported (empty)", 'success')` <br>• Copy success (non-empty): `("Summary copied to clipboard", 'success')` <br>• Copy success, **empty** (header check): `("Summary copied (empty)", 'success')` <br>• Copy permission failure (DOMException / undefined `navigator.clipboard`): `("Couldn't copy — try Export instead.", 'error')` <br>• Network failure (fetch rejects, response.ok=false): `("Export failed — check your connection.", 'error')` <br>"Empty" is detected by reading the server's `X-Empty-Export` response header — never by client-side toggle inspection (FR-A6 is the single source of truth). |
| FR-F13 | **Add `ToastContainer.vue`** (~30-line component) that renders `useUiStore().toasts` as a fixed-position stack at the top-right (or bottom-right) of the viewport, mounted once in `AppShell.vue`. Color/iconography per `Toast['type']` (success/error/info/warning). This closes the half-built toast infrastructure today. |

### 6.5 Documentation

| ID | Requirement |
|----|-------------|
| FR-D1 | Update `CLAUDE.md` with three specific edits: <br>(a) Update the "Running a book through the full pipeline" workflow example to show one of the new flags (e.g., `bookcompanion export book <id> --format markdown --no-toc -o ~/notes/<slug>.md`) so the new surface is discoverable. <br>(b) Add a "Markdown export" entry under the "CLI — Core" command listing summarizing the new flag set (`--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section <id>` repeatable) and the new default filename shape. <br>(c) Add a deprecation callout under "CLI — Core" stating that `bookcompanion export library --format markdown` was removed in v1.6 and pointing users at `--format json` for full-library backups. |
| FR-D2 | Update `docs/changelog.md` after merge (per `/changelog` skill workflow) to describe the new shape, the new UI affordances on the book detail page, and the library Markdown deprecation. |

---

## 7. API Changes

### 7.1 `GET /api/v1/export/book/{book_id}` (extended)

```
GET /api/v1/export/book/{book_id}
    ?format=markdown            (default: json)
    &include_book_summary=true  (default: true; ignored for format=json)
    &include_toc=true           (default: true; ignored for format=json)
    &include_annotations=true   (default: true; ignored for format=json)
    &exclude_section=14         (repeatable; ignored for format=json)
    &exclude_section=15
```

**Response (200, `format=markdown`):**
```
Content-Type: text/markdown
Content-Disposition: attachment; filename="<slug>-summary-<YYYYMMDD>.md"

# Book Title
**Author:** Some Author
**Exported:** 2026-04-25

## Table of Contents
- [Chapter 1](#chapter-1)
  - [Subsection](#subsection)
- [Chapter 2](#chapter-2)

Book-level summary text here...

## Chapter 1
<a id="chapter-1"></a>
Section 1 summary text here. [Image: figure 3]

### Highlights
> Highlighted passage from this section.
>
> — Note: optional reader note

> Another highlight without a note.

## Chapter 2
<a id="chapter-2"></a>
Section 2 summary text here.

## Notes
- Free-floating book-level note.
- Another book-level note.
```

**Response (200, `format=json`):** unchanged — `JSONResponse` with full `_collect_book_data()` shape; selection params silently ignored.

**Errors:**
- `400` — `exclude_section` contains an id not belonging to this book. Body: `{"detail": "section 99 does not belong to book 3"}`.
- `404` — book does not exist (preserved).

### 7.2 `GET /api/v1/export/library` (deprecated for markdown)

- `format=json` — unchanged.
- `format=markdown` — `410 Gone` with body: `{"detail": "Library Markdown export was removed in v1.6 — use format=json for full-library backups, or use /api/v1/export/book/{id}?format=markdown per book."}`

---

## 8. Frontend Design

### 8.1 Component hierarchy

```
BookOverviewView.vue                                      (existing, modified)
├── .actions div                                          (existing, extended)
│   ├── <button> Read                                     (existing)
│   ├── <button> Export summary                           (NEW, FR-F1)
│   ├── <button> Copy as Markdown                         (NEW, FR-F1)
│   └── <a class="customize-link"> Customize…             (NEW, FR-F1)
└── <ExportCustomizeModal v-if="showModal" ... />         (NEW)

ExportCustomizeModal.vue                                  (NEW)
├── header: "Export summary"
├── checkboxes: Book summary | Table of contents | Highlights & notes | Sections
├── scrollable section list (only sections with summaries)
├── count footer
└── footer: [Cancel] [Export] [Copy as Markdown]

AppShell.vue                                              (existing, modified)
└── <ToastContainer />                                    (NEW, FR-F13)

ToastContainer.vue                                        (NEW)
└── v-for over useUiStore().toasts → toast item with icon + message
```

### 8.2 State

- `BookOverviewView.vue` local refs: `showModal: boolean`, `exporting: boolean` (disables buttons during in-flight request).
- `ExportCustomizeModal.vue` local refs: `includeBookSummary`, `includeToc`, `includeAnnotations`, `selectedSectionIds: Set<number>`. Master "Sections" toggle is computed from `selectedSectionIds.size === sectionsWithSummaryCount`.
- No Pinia state added for export selection — every modal open starts with defaults.

### 8.3 Interactions

- `Export summary` (one-click): immediate fetch + download, no modal; toast on completion.
- `Copy as Markdown` (one-click): immediate fetch + clipboard write, no modal; toast on completion.
- `Customize…`: opens modal; modal's `Export` and `Copy` honor the toggle state and dispatch the same fetch (with the selection querystring).
- `Esc` closes the modal (per `PresetPickerModal` precedent).
- Disabled state: buttons render with `disabled` attribute + `title` (tooltip); rendered as muted gray.

### 8.4 Responsive behavior

- The `.actions` row stays single-line on desktop. On viewports below ~480px, the three buttons wrap to a second line; `Customize…` link drops below.
- Modal's `min(560px, 92vw)` already handles narrow viewports.

---

## 9. Edge Cases

| # | Scenario | Condition | Expected Behavior |
|---|----------|-----------|-------------------|
| E1 | Book has zero summaries AND user is on book detail page | `book.default_summary_id IS NULL` AND no `book.sections[*].default_summary_id` | UI: `Export summary` and `Copy as Markdown` disabled with tooltip *"Generate a summary first."* `Customize…` remains enabled. |
| E2 | Book is `UPLOADING` or `PARSING` | book.status enum check | All three actions disabled with tooltip *"Book is still being processed."* |
| E3 | User clicks `Customize…`, deselects everything, clicks Export | All toggles off + all sections deselected | Server produces front-matter-only file; toast: *"Summary exported (empty)"* (yes — distinct toast variant for empty exports). |
| E4 | Clipboard write throws (browser permission denied / API undefined) | `navigator.clipboard` undefined OR `writeText` rejects | Toast (error variant): *"Couldn't copy — try Export instead."* No console.error spew; caught quietly. |
| E5 | CLI: `--exclude-section 99` where 99 is not a section of the book | Validation in `export_cmd.py` before render | Exit status 1: `Error: section 99 does not belong to book <id>.` No file written. |
| E6 | CLI: book ID does not exist | `BookRepository.get_by_id` returns None | Exit status 1: `Error: book <id> not found.` (existing behavior preserved.) |
| E7 | CLI: `--no-toc --format json` (or any exclusion flag with json) | Flag combination check | Exit status 2: `Error: --no-* and --exclude-section flags are only valid with --format markdown. JSON exports are full-fidelity.` |
| E8 | CLI: `bookcompanion export library --format markdown` | Removed subcommand | Exit status 2: `Library Markdown export was removed in v1.6 — use --format json for full-library backups, or run 'export book' per book.` |
| E9 | CLI: no `--output` | stdout fallback | Markdown printed to stdout. All flag combinations supported in stdout mode. |
| E10 | Annotations cascade with section exclusion | Section X is excluded; annotations exist with `content_id = section_X.id` | Those section-anchored annotations are dropped. Free-floating notes (empty `selected_text`) are NOT cascaded — they appear in `## Notes` regardless of which sections are excluded (book-scope vs section-scope). |
| E11 | Network drops mid-download | Browser shows native "download failed" UI | Frontend catches fetch error → toast: *"Export failed — check your connection."* Re-clicking re-issues the request (server-side idempotent). |
| E12 | Book has no sections | `book.sections == []` | Customize modal section list shows placeholder: *"No sections found in this book."* Export still works (front matter + book summary if present). |
| E13 | Book has summaries but no annotations | `book.sections[*].annotations == []` everywhere | "Highlights & notes" toggle still rendered enabled (annotations might exist on book-scope); produces no inline `### Highlights` blocks; no `## Notes` block. No empty headings. |
| E14 | All sections have summaries but the book itself doesn't | `book.default_summary_id IS NULL`; sections all have summaries | "Book summary" toggle disabled in modal with text *" — no book summary yet"*. Export skips the book-summary block. |
| E15 | Book title contains filename-illegal chars (`/`, `:`, `?`) | Slugify aggressively in server | Filename: lowercase, replace non-alphanumeric with `-`, collapse multiple dashes, trim, truncate to 80 chars. |
| E16 | Two exports of the same book on the same day | Filenames identical | Browser auto-appends `(1)`, `(2)`. We do not add a per-export uniqueness suffix. |
| E17 | Section title with markdown special chars (`#`, `*`, `[`) | Edge | Title rendered verbatim in `## ...` heading; anchor slug uses GFM slug rules (strip non-alnum, lowercase). |
| E18 | Two sections with same slugged title | Slug collision | Per FR-B7, follow GFM disambiguation: first occurrence keeps bare slug `s`, second occurrence is `s-1`, third is `s-2`, etc. The disambiguation table is built in a single deterministic pass over `sections` ordered by `order_index`, then both the TOC link generator and the section-heading slug-prediction reuse the same table. |
| E19 | Section summary contains `![figure 3](/api/v1/images/17)` | Per FR-B5 | Renders as `[Image: figure 3]`. Empty alt → `[Image]`. No `/api/v1/images/` substring survives. |
| E20 | Multi-author book | `len(book.authors) > 1` | `**Authors:** Name 1, Name 2`. Single author: `**Author:** Name`. Zero authors: `**Author:** Unknown`. |
| E21 | CJK-only title slugifies to empty | `slug == ""` after slugify | Filename falls back to `book-<id>-summary-<YYYYMMDD>.md`. The H1 in the file still uses the original title verbatim. |
| E22 | CLI: book with zero summaries + `--format markdown` (no `--no-*` flags) | Trust-the-user | Front-matter-only file (or stdout), exit 0, no warning. |
| E23 | Annotation with non-empty `selected_text` AND non-empty `note` | Both fields present | Blockquote of `selected_text`, then indented `> — Note: {note}` line. |
| E24 | Annotation with non-empty `selected_text` AND empty `note` | Highlight without note | Blockquote of `selected_text` only; no `— Note:` line. |
| E25 | Annotation with empty `selected_text` AND non-empty `note` | Free-floating note | Bullet in book-level `## Notes` footer. |
| E26 | Annotation with empty `selected_text` AND empty `note` | Should never persist | Defensive: skip silently. |

---

## 10. Configuration & Feature Flags

None. The feature is always-on after merge. The deprecation of library Markdown export is immediate; no flag gate.

---

## 11. Testing & Verification Strategy

### 11.1 Unit tests (pytest, in `backend/tests/unit/`)

- `test_export_service_summary_markdown.py` (new):
  - Front-matter shape (single author, multi-author, zero authors, CJK title).
  - TOC anchor generation including duplicate-slug disambiguation (E18).
  - Slugify + filename generation (E15, E21).
  - Image-URL sanitization: `/api/v1/images/{id}` round-trip with alt-present, alt-empty, multiple in one summary, raw `<img>` tag (E19, FR-B5). Assertion: `assert "/api/v1/images/" not in output` for every test case.
  - Annotation rendering: highlight+note (E23), highlight only (E24), free-floating note (E25), section-cascade exclusion (E10).
  - Empty selection produces front-matter-only file (E3, E22).
  - Selection toggles produce expected omissions (FR-B6 each branch).

### 11.2 Integration tests (`backend/tests/integration/`)

- `test_export_api_book_markdown.py`:
  - `GET /api/v1/export/book/{id}?format=markdown` default returns expected shape, `Content-Disposition` filename matches `<slug>-summary-<YYYYMMDD>.md`.
  - Selection querystring (each combination + `exclude_section` repeatable).
  - Invalid `exclude_section` → 400.
  - `format=json` ignores selection params silently — output byte-equal to today's JSON export for a fixture book (regression gate).
- `test_export_api_library_markdown.py`:
  - `GET /api/v1/export/library?format=markdown` → 410 with the deprecation message.
  - `GET /api/v1/export/library?format=json` → 200, unchanged shape.
- `test_export_cli.py` (extend existing):
  - `bookcompanion export book <id> --format markdown` (no flags) → matches API one-click output byte-for-byte.
  - All four exclusion flags individually + combined.
  - `--exclude-section 99` for invalid id → exit 1.
  - `--no-toc --format json` → exit 2 (FR-C5, E7).
  - `bookcompanion export library --format markdown` → exit 2 (FR-C4, E8).
  - Stdout mode (no `--output`) for all flag combinations.
  - Zero-summaries book + `--format markdown` → front-matter-only, exit 0 (E22).

### 11.3 E2E / frontend (`frontend/src/`)

- `test:unit` (Vitest): `ExportCustomizeModal.spec.ts` — toggle state → querystring assembly is correct; master-toggle behavior; section-list rendering with hidden-count footer.
- `test:e2e` (Playwright):
  - Navigate to `/books/{id}` for a fixture book with summaries → click `Export summary` → verify download triggered + toast appeared.
  - Click `Copy as Markdown` → verify clipboard contains identical bytes to the download (G5).
  - Open Customize → uncheck two sections → click Export → file omits those sections.
  - Book in `UPLOADING` state → all three actions disabled with tooltip.
  - Book with zero summaries → `Export` and `Copy` disabled, `Customize…` enabled, modal can submit empty selection.

### 11.4 Verification commands (run by /verify after implementation)

```bash
# Backend
cd backend && uv run python -m pytest tests/ -v -k "export" 2>&1 | tail -40
cd backend && uv run python -m pytest tests/integration/test_export_api_book_markdown.py -v
cd backend && uv run python -m pytest tests/unit/test_export_service_summary_markdown.py -v

# Image-URL sanitization regression (G4)
cd backend && uv run python -m pytest tests/ -v -k "image_ref" 2>&1 | tail -20
# Asserts: '/api/v1/images/' not in any rendered markdown for any fixture book

# JSON regression (G6)
cd backend && uv run python -m pytest tests/integration/test_export_api_book_markdown.py::test_json_unchanged -v

# X-Empty-Export header (FR-A6)
cd backend && uv run python -m pytest tests/integration/test_export_api_book_markdown.py -v -k "empty_header"
# Asserts: header is "true" when toggles produce a front-matter-only body, absent or "false" otherwise

# CLI regression
cd backend && uv run bookcompanion export book 1 --format markdown -o /tmp/test.md
cd backend && uv run bookcompanion export book 1 --format markdown --no-toc --exclude-section 2 -o /tmp/test2.md
cd backend && uv run bookcompanion export book 1 --format json --no-toc; echo "exit=$?"   # expect exit=2
cd backend && uv run bookcompanion export library --format markdown; echo "exit=$?"        # expect exit=2

# Frontend
cd frontend && npm run test:unit
cd frontend && npm run test:e2e -- --grep "export"

# Manual /verify (Playwright MCP)
# 1. Build frontend, copy to backend/app/static, start serve --port 8765
# 2. Navigate to /books/1
# 3. Click Export summary; confirm file downloaded + toast shown
# 4. Open downloaded file in Obsidian / VS Code preview; click TOC entries; confirm anchor scroll
# 5. Click Copy as Markdown; paste into a text editor; confirm byte-equality with the download
```

---

## 12. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| O1 | Toast position (top-right vs bottom-right) and stacking order — designer judgment call, falls under FR-F13. | Maneesh | During /plan |
| O2 | When a book is in `PARSE_FAILED`, is the export-empty-state copy ("Generate a summary first") accurate, or should it be "This book failed to parse — nothing to export"? Spec defaults to the former (fewer string variants); confirm before /plan if a different message is preferred. | Maneesh | Before /plan |

---

## 13. Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `backend/app/services/export_service.py` | Existing code | `_collect_book_data()` is shared between JSON and markdown; the spec keeps it unchanged and filters at render time (D20). The current `_render_markdown()` is the kitchen-sink dump being replaced. |
| `backend/app/cli/commands/export_cmd.py` | Existing code | Existing `bookcompanion export book` and `export library` Typer commands; spec extends `book` and removes `library --format markdown`. |
| `backend/app/api/routes/export.py` | Existing code | GET endpoints with `format` query param; spec extends with selection querystring and 410-gates the library markdown route. Confirmed both surfaces are GET (recon resolved a discrepancy between subagent reports). |
| `backend/app/db/models.py` | Existing code | `Book.default_summary_id`, `BookSection.default_summary_id`, `Summary.summary_md` are the fields that drive what's exportable. `Annotation` has `content_type`, `content_id`, `selected_text`, `note`. No `slug` column on Book — derive at render time. |
| `backend/app/services/parser/image_url_rewrite.py:63-96` | Existing code | In-app image scheme is **`/api/v1/images/{id}`**, not `image://N`. The requirements doc described the legacy scheme; D14/FR-B5 target the actual scheme. |
| `backend/app/services/parser/epub_parser.py:162` | Existing code | Original parser TOC is not stored ("Since we don't store it, re-derive from TOC"). Validates D4. |
| `frontend/src/views/BookOverviewView.vue` | Existing code | `.actions` div currently contains only `[Read ▶]` button — natural landing zone for new export actions per D2. |
| `frontend/src/components/common/PresetPickerModal.vue` | Existing code | Modal precedent (overlay, body sizing, Esc to close, footer pattern) — `ExportCustomizeModal.vue` follows this. |
| `frontend/src/stores/ui.ts` | Existing code | `showToast(message, type, duration)` exists; `toasts` ref is exposed; **no consumer renders the list** — spec adds `ToastContainer.vue` (FR-F13). |
| `frontend/src/api/export.ts` | Existing code | `triggerDownload()` helper handles blob + `<a>` element pattern — reused for `Export summary` button. |
| `frontend/src/components/reader/FloatingToolbar.vue:29` | Existing code | Bare `navigator.clipboard.writeText()` precedent — Copy button reuses the same pattern with try/catch around `DOMException`. |
| Readwise export UX | External pattern | Per-book Markdown download with title-derived filename; minimal selection. Validates one-click default. |
| Notion export-with-subpages | External pattern | Modal with checkboxes for "Include subpages", "Include comments". Validates Customize modal shape. |
| GitHub-flavored Markdown anchor rules | External standard | Anchors are slugified titles; duplicate slugs get `-2`, `-3`. Followed in FR-B7. |

---

## 14. Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | (a) Anchor strategy used explicit `<a id>` tags + a `-2`/`-3` disambiguation rule that conflicts with GFM auto-anchors and could break the TOC in some viewers; (b) `clipboard.writeText` after `await fetch` breaks Safari's user-gesture chain, silently rejecting the copy; (c) FR-B5 image-sanitization regex was prose-only — implementation-ambiguous; (d) FR-A3 (silent ignore on JSON) and FR-A5 (400 on invalid `exclude_section`) were inconsistent for JSON requests; (e) Customize modal section list ordering was unspecified; (f) Empty-export toast variant referenced in E3 was missing from FR-F12; (g) FR-F11 was vague about how to clean up `BackupSettings.vue`'s now-dead format dropdown. | (a) FR-B7 rewritten to follow GFM rules exactly (bare slug → `-1` → `-2`) and FR-B6 step 6 + E18 updated to drop inline `<a id>` tags. (b) FR-F5 rewritten with `ClipboardItem`-with-promise primary path and legacy `writeText` fallback. (c) FR-B5 pinned two explicit regexes with ordering note + alt-special-character behavior. (d) FR-A3 clarified to "accepted, never validated, never affect output"; FR-A5 scoped to `format=markdown`. (e) FR-F7 specifies `BookSection.order_index` ascending. (f) FR-F12 rewritten with explicit empty-variant strings + client-side detection rule. (g) FR-F11 prescribes replacing the dropdown with a single `Export library (JSON)` button + constraining the helper. (h) Goal G4 measurement language updated to match new anchor strategy + automated assertion shape. |
| 2 | (a) FR-B6 step 6 emitted flat `## ` for every section while FR-B6 step 4 nested the TOC by `BookSection.depth` — coherence question (mirror depth in body or document the flat choice); (b) FR-F12's empty-toast detection was a client-side toggle-inspection rule that mismatches reality when toggles are on but `Book.default_summary_id` is null AND all sections excluded — server is the only authoritative signal of "empty body"; (c) FR-F7 said "master toggle" without pinning the visual (tri-state vs Select-all/Deselect-all link pair); (d) FR-D1 said "Update CLAUDE.md" without naming sections, leaving /plan to guess. | (a) FR-B6 step 6 explicitly documents the flat-`##` choice and explains the rationale (TOC bullets convey hierarchy; section bodies stay peer-level for clean outlines). (b) Added FR-A6 mandating an `X-Empty-Export: true` server response header on `format=markdown` when the rendered body is front-matter-only; FR-F12 now reads the header instead of inferring from toggles. (c) FR-F7 expanded with explicit tri-state semantics including the `indeterminate → checked → unchecked` click cycle and how to set `el.indeterminate` via a Vue ref watcher. (d) FR-D1 expanded into three specific CLAUDE.md edits (a/b/c). |
