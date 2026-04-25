# Summary Markdown Export — Design Simulation

**Date:** 2026-04-25
**Spec:** `docs/specs/2026-04-25-summary-markdown-export-spec.md`
**Tier:** 2

---

## 1. Scope

- **In scope:** backend rendering pipeline (`ExportService._render_summary_markdown`), API contract delta (`GET /api/v1/export/book/{id}` extension; `GET /api/v1/export/library?format=markdown` removal), CLI delta (new flags on `bookcompanion export book`; removal of `bookcompanion export library --format markdown`), frontend (Vue 3 + Pinia: `BookOverviewView.vue` extension, new `ExportCustomizeModal.vue`, new `ToastContainer.vue`, `BackupSettings.vue` cleanup), CLAUDE.md / changelog updates.
- **Out of scope:** DB schema changes (none — explicit non-goal); JSON export filtering (D12 keeps full fidelity); summary-version picker; persisted export preferences; original parser TOC persistence; concepts / refs / eval data in Markdown export; PDF / EPUB / Word / HTML output formats.
- **Companion specs:** none.
- **Downstream consumers anticipated:** none declared (Book Companion is unpublished per workstream context — single user, no automation depends on the old shape).

---

## 2. Scenario Inventory

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | One-click Export from book detail page | Spec §5.1 | happy |
| S2 | Copy-as-Markdown from book detail page | Spec §5.2 | happy |
| S3 | Customize → uncheck two sections + TOC → Export | Spec §5.3 | happy |
| S4 | CLI with `--no-toc --exclude-section 14 --exclude-section 15` | Spec §5.4 | happy |
| S5 | Book has zero summaries anywhere (UI gating + CLI front-matter-only + Customize empty path) | Spec E1+E14+E22 | edge |
| S6 | Book in `UPLOADING` / `PARSING` — UI buttons disabled; CLI proceeds | Spec E2 | edge |
| S7 | Customize → deselect everything → Export (front-matter-only file) | Spec E3 | edge |
| S8 | Clipboard write throws (DOMException / undefined) | Spec E4 | failure |
| S9 | CLI input validation: invalid `--exclude-section`, invalid book ID, exclusion flags + `--format json`, removed `export library --format markdown` | Spec E5+E6+E7+E8 | input |
| S10 | Network drops mid-download | Spec E11 | failure |
| S11 | Annotation cascade — excluded section drops its annotations; free-floating notes survive | Spec E10+E25 | edge |
| S12 | Annotation rendering variants — selected_text+note, selected_text only, free-floating note, both empty | Spec E23-E26 | edge |
| S13 | Image-ref sanitization — `![alt](/api/v1/images/17)` and raw `<img>` tag with/without alt | Spec E19, FR-B5 | edge |
| S14 | Author count variants — single, multi, zero | Spec E20 | edge |
| S15 | Filename slug edge cases — illegal chars, CJK-only, same-day collision | Spec E15+E21+E16 | edge |
| S16 | Section heading + slug — markdown special chars, duplicate-title disambiguation | Spec E17+E18 | edge |
| S17 | API direct caller (`curl …?exclude_section=14&exclude_section=14`) — duplicate IDs | Variant | input |
| S18 | Rapid double-click on `Export summary` → two in-flight requests, two downloads | Adversarial | concurrency |
| S19 | UI section list stale — book modified (re-summarized, sections merged) after `BookOverviewView` loaded; user opens Customize | Adversarial | timing |
| S20 | Big book — 100+ sections + 500+ annotations; render time + clipboard size + browser blob limits | Adversarial | boundary |
| S21 | User clicks Export, then immediately Copy before first request resolves | Adversarial | concurrency |
| S22 | `X-Empty-Export` detection collides with book summary text containing literal `## ` heading (false negative on "empty") | Model-driven | timing |
| S23 | Section title is purely emoji or non-alphanumeric (`🚀 The Vision`) → GFM slug strips to empty → all such titles collide on bare empty slug | Model-driven | input |
| S24 | Image with GFM title attribute `![alt](/api/v1/images/17 "title text")` — FR-B5 regex misses the title-attribute form | Model-driven | input |
| S25 | Existing CLI automation script depends on the OLD kitchen-sink Markdown shape (concepts, refs, etc.) — silent breakage on upgrade | Model-driven | migration |

---

## 3. Scenario Coverage Matrix

| Scenario | Step | Spec Artifact | Status |
|----------|------|---------------|--------|
| S1 (one-click Export) | Render UI buttons in `.actions` div | FR-F1 | ✓ |
| | Click → GET request | FR-F4 | ✓ |
| | Backend collects book data | FR-B3 | ✓ |
| | Backend renders + sanitizes | FR-B1, FR-B5, FR-B6 | ✓ |
| | Filename via slug + Cache-Control | FR-A2 | ✓ |
| | `X-Empty-Export` header | FR-A6 | ✓ |
| | Frontend triggers download | FR-F4 | ✓ |
| | Toast variant selection | FR-F12 | ✓ |
| S2 (Copy) | Same fetch as S1 | FR-F4 | ✓ |
| | ClipboardItem path with fetch promise | FR-F5 | ✓ |
| | Toast disambiguation (network vs clipboard) | FR-F5 + FR-F12 | ✓ (post-G5) |
| S3 (Customize) | Open modal | FR-F6 | ✓ |
| | Refresh section list on open | FR-F6 (post-G6) | ✓ |
| | Tri-state Sections checkbox | FR-F7 | ✓ |
| | Build query string | FR-F8 | ✓ |
| | Server validates exclude_section IDs | FR-A5 | ✓ |
| S4 (CLI) | Typer flag parsing | FR-C1 | ✓ |
| | Validate book + section IDs | FR-C3 | ✓ |
| | Render via shared service | FR-B1 | ✓ |
| | File or stdout output | FR-C2 | ✓ |
| S5 (zero summaries) | UI buttons disabled | FR-F3 | ✓ |
| S5b (book has no sections at all — Spec E12) | Customize section list shows placeholder "No sections found" | FR-F7 | ✓ |
| | Export still works (front matter + optional book summary) | FR-B6 + FR-B11 | ✓ |
| | Customize remains enabled | D6, FR-F3 | ✓ |
| | Server emits front-matter-only | FR-B11 | ✓ |
| | TOC heading omitted | FR-B6 step 4 (post-G12) | ✓ |
| | `X-Empty-Export: true` | FR-A6, FR-B1 (post-G1) | ✓ |
| | CLI exits 0 with front matter | FR-C6 | ✓ |
| S6 (UPLOADING/PARSING) | UI buttons disabled with tooltip | FR-F2 | ✓ |
| | CLI unaffected | FR-C6 (post-G13) | ✓ |
| S7 (Customize-deselect-all) | Always-allow on Customize path | D6 | ✓ |
| | Server emits front matter | FR-B11 | ✓ |
| | Empty toast variant | FR-F12, FR-A6 | ✓ |
| S8 (Clipboard write throws) | DOMException caught | FR-F5 | ✓ |
| | Toast disambiguation: network vs clipboard | FR-F5 (post-G5) | ✓ |
| S9 (CLI validation) | Invalid section ID → exit 1 | FR-C3 | ✓ |
| | Book ID does not exist → exit 1 | FR-C6 (preserved) | ✓ |
| | Exclusion + `--format json` → exit 2 | FR-C5 | ✓ |
| | Removed library subcommand → exit 2 | FR-C4 | ✓ |
| S10 (network drop) | Frontend catches fetch error | FR-F12 | ✓ |
| | Re-issue idempotent | E11 | ✓ |
| S11 (cascade) | Section excluded → annotations dropped | FR-B6 step 6 | ✓ |
| | Free-floating notes survive | FR-B9 | ✓ |
| S12 (annotation variants) | All four variants | FR-B8, FR-B9 (post-G4) | ✓ |
| | Newline / `>` / `#` escaping | FR-B8 (post-G10) | ✓ |
| S13 (image sanitize) | Markdown image regex | FR-B5 (1) | ✓ |
| | Raw `<img>` regex | FR-B5 (2) | ✓ |
| | GFM-title-attribute variant | FR-B5 (1, post-G3) | ✓ |
| S14 (author counts) | Single/multi/zero | FR-B6 step 2, E20 | ✓ |
| S15 (filename slug) | Illegal chars stripped | FR-A2 (post-G8) | ✓ |
| | CJK fallback to `book-{id}-...` | FR-A2 | ✓ |
| | Same-day collision | E16 | ✓ |
| S16 (heading + slug) | Markdown special chars in title | E17 | ✓ |
| | Duplicate disambiguation | FR-B7, E18 | ✓ |
| | Unicode preservation | FR-B7 (post-G9), E31 | ✓ |
| S17 (duplicate exclude_section) | List → set deduplication | FR-B4 (`exclude_section_ids: set[int]`) | ✓ |
| S18 (rapid double-click) | In-flight disable + spinner | FR-F14 (post-G7) | ✓ |
| S19 (stale UI section list) | Modal refreshes section list on open | FR-F6 (post-G6) | ✓ |
| S20 (big book) | Render time NFR up to 100 sections | G1 (post-G11) | ✓ |
| | Clipboard size — browsers cap ~5MB; render falls inside this | (no explicit guard; size NFR makes it implicit) | partial |
| S21 (Export+Copy mid-flight) | In-flight disable | FR-F14 (post-G7) | ✓ |
| S22 (X-Empty-Export false negative) | Renderer-intent emptiness | FR-B1 + FR-A6 (post-G1) | ✓ |
| S23 (emoji-only title) | Empty-slug fallback `section-{order_index}` | FR-B7 (post-G2), E27 | ✓ |
| S24 (image title attribute) | Regex (1) extended | FR-B5 (post-G3), E28 | ✓ |
| S25 (old CLI shape break) | Accepted risk | §8 (post-G18) | accepted |

---

## 4. Artifact Fitness Findings

### 4.1 Data & Storage
- **B1-1 (significant):** FR-B9 free-floating annotation partitioning was ambiguous given `Annotation.content_type` is a 3-member enum (`SECTION_CONTENT` / `SECTION_SUMMARY` / `BOOK_SUMMARY`). Different `content_type` × `selected_text` combos demanded explicit rules. → resolved as G4 (Apply patch).
- No DB schema changes in scope. Existing Book / BookSection / Summary / Annotation / Image schemas are sufficient.

### 4.2 Service Interfaces
- **B2-1 (minor):** Cache-Control header was unspecified on the export response. → resolved as G17 (Apply patch — `Cache-Control: private, max-age=0` added to FR-A2).
- All other interface concerns (request shape, response shape, error responses, idempotency, versioning) covered by FR-A1 through FR-A6.

### 4.3 Behavior (State / Workflows)
- Export is stateless — no state machine to critique. CLI subcommand removal handled via FR-C4 / FR-A4 with explicit removed-route messaging.

### 4.4 Interface (UI + CLI)
- **B4-1 (minor):** `exporting: boolean` in §8.2 had no FR manifesting it as button state. → resolved as G7+G15 (Apply patch — new FR-F14).
- **B4-2 (minor):** Modal accessibility (focus trap, focus return) and toast ARIA live-region were unspecified. → resolved as G14 (Apply patch — extended FR-F6 + FR-F13).
- **B4-3 (minor):** CLI `--help` content for new flags was implicit. → resolved as G16 (Apply patch — FR-C1 expanded with Typer `help=` requirement and command-docstring grouping).

### 4.5 Operational (NFRs, Rollout)
- **B6-1 (minor):** No NFR for books > 30 sections. → resolved as G11 (Apply patch — G1 success metric extended to 100 sections / 1000 annotations linear).
- Rollout: feature is always-on. Library Markdown deprecation handled via 410 Gone + CLI exit 2 with named errors. No flag gates needed for a single-user tool.

### 4.6 Other Artifacts
- Documentation FRs (FR-D1, FR-D2) cover CLAUDE.md and changelog updates; no other artifact types.

---

## 5. Interface ↔ Core Cross-Reference

### 5.1 Forward (UI / CLI → API)

| # | Interaction | Trigger | Endpoint / Function | Req Match | Res Has Consumer Needs | Error Mapping | Notes |
|---|---|---|---|---|---|---|---|
| W1 | Click `Export summary` (no selection) | `BookOverviewView.vue` button | `GET /api/v1/export/book/{id}?format=markdown` | ✓ | blob + filename header + `X-Empty-Export` | network → toast | clean |
| W2 | Click `Copy as Markdown` (no selection) | `BookOverviewView.vue` button | same as W1 | ✓ | text + `X-Empty-Export` | clipboard fail vs network fail toasts disambiguated (post-G5) | clean |
| W3 | Modal Export with selection | `ExportCustomizeModal.vue` Export button | `GET /api/v1/export/book/{id}?format=markdown&include_*=…&exclude_section=…` | ✓ | same as W1 | + 400 invalid section (mitigated by modal-open refresh post-G6) | clean |
| W4 | Modal Copy with selection | `ExportCustomizeModal.vue` Copy button | same as W3 | ✓ | text + header | same as W3 | clean |
| W5 | Click `Export library (JSON)` | `BackupSettings.vue` button | `GET /api/v1/export/library?format=json` | ✓ | JSON blob | ✓ | dropdown removed per FR-F11 |
| W6 | CLI `bookcompanion export book <id> --format markdown [...flags]` | Typer command | direct `ExportService` call | ✓ | string body | ✓ exit 1/2 mapping per FR-C3/C4/C5 | clean |
| W7 | CLI `bookcompanion export library --format markdown` (REMOVED) | Typer command | exit 2 stub | n/a | n/a | ✓ migration message | clean |

### 5.2 Reverse (API endpoints → consumers)

| Endpoint | Consumer(s) | Status |
|---|---|---|
| `GET /api/v1/export/book/{id}?format=markdown` | W1, W2, W3, W4, W6 | wired |
| `GET /api/v1/export/book/{id}?format=json` | W6 (CLI) and direct API users | intentional CLI/API parity (post-G19 — note added to §7.1) |
| `GET /api/v1/export/library?format=json` | W5 | wired |
| `GET /api/v1/export/library?format=markdown` | n/a — REMOVED | 410 Gone |

No orphan endpoints. No orphan interface actions.

---

## 6. Targeted Pseudocode

Two flows qualify under the selection criteria: (a) `_render_summary_markdown` is multi-step with branches, slug disambiguation, image sanitization, and emptiness tracking; (b) the frontend Copy flow is concurrency-sensitive (user-gesture chain) with branching error paths.

### 6.1 Flow: `_render_summary_markdown(book_data, selection)`

**Entry:** Called by API route handler and CLI command. Pure function with respect to inputs.

```
FUNCTION _render_summary_markdown(book_data, selection):
  # selection: ExportSelection(include_book_summary, include_toc, include_annotations, exclude_section_ids: set[int])

  toc_emitted = False
  book_summary_emitted = False
  any_section_emitted = False
  notes_emitted = False
  body_lines = []

  # === Front matter (always) ===
  body_lines.append(f"# {book_data.title}")
  authors = book_data.authors
  IF len(authors) == 0:
    body_lines.append("**Author:** Unknown")
  ELIF len(authors) == 1:
    body_lines.append(f"**Author:** {authors[0]}")
  ELSE:
    body_lines.append(f"**Authors:** {', '.join(authors)}")
  body_lines.append(f"**Exported:** {today_iso_date()}")
  body_lines.append("")

  # === Predict slug table for sections (single deterministic pass) ===
  # Filter to sections that will actually render
  rendered_sections = [s FOR s IN book_data.sections
                       IF s.default_summary_id IS NOT NULL
                       AND s.id NOT IN selection.exclude_section_ids]
  rendered_sections.sort(key=lambda s: s.order_index)

  slug_table = {}      # section.id -> assigned_slug
  slug_counter = {}    # bare_slug -> next-suffix-int (0 = bare, 1 = -1, ...)
  FOR s IN rendered_sections:
    base = gfm_slug(s.title)       # Unicode-aware; lowercase, alnum/space/-/_, collapse
    IF base == "":
      base = f"section-{s.order_index:03d}"   # empty-slug fallback (G2)
    n = slug_counter.get(base, 0)
    assigned = base IF n == 0 ELSE f"{base}-{n}"
    slug_table[s.id] = assigned
    slug_counter[base] = n + 1

  # === TOC (only if include_toc AND will render at least one section) ===
  IF selection.include_toc AND len(rendered_sections) > 0:
    body_lines.append("## Table of Contents")
    FOR s IN rendered_sections:
      indent = "  " * s.depth
      slug = slug_table[s.id]
      body_lines.append(f"{indent}- [{s.title}](#{slug})")
    body_lines.append("")
    toc_emitted = True

  # === Book summary (no extra heading; rendered directly) ===
  IF selection.include_book_summary AND book_data.book_summary_md:
    body_lines.append(sanitize_image_urls(book_data.book_summary_md))
    body_lines.append("")
    book_summary_emitted = True

  # === Sections ===
  FOR s IN rendered_sections:
    body_lines.append(f"## {s.title}")
    body_lines.append(sanitize_image_urls(s.summary_md))
    body_lines.append("")

    # Inline section highlights (cascade rule)
    IF selection.include_annotations:
      section_anns = [a FOR a IN book_data.annotations
                      IF a.content_type IN ('section_content','section_summary')
                      AND a.content_id == s.id
                      AND a.selected_text]
      IF len(section_anns) > 0:
        body_lines.append("### Highlights")
        FOR a IN section_anns:
          body_lines.append(render_blockquote_annotation(a))
        body_lines.append("")
    any_section_emitted = True

  # === Notes footer (book-scoped annotations) ===
  IF selection.include_annotations:
    book_anns = [a FOR a IN book_data.annotations IF a.content_type == 'book_summary']
    rendered_notes = []
    FOR a IN book_anns:
      IF a.note AND a.selected_text:
        rendered_notes.append(f"- > \"{escape_md(a.selected_text)}\"\n  — {escape_md(a.note)}")
      ELIF a.note:
        rendered_notes.append(f"- {escape_md(a.note)}")
      ELIF a.selected_text:
        rendered_notes.append(f"- > \"{escape_md(a.selected_text)}\"")
      # both empty → silently skip (defensive)
    IF len(rendered_notes) > 0:
      body_lines.append("## Notes")
      body_lines.extend(rendered_notes)
      body_lines.append("")
      notes_emitted = True

  body = "\n".join(body_lines)
  is_empty = NOT (toc_emitted OR book_summary_emitted OR any_section_emitted OR notes_emitted)
  RETURN (body, is_empty)
```

**DB calls:**
- None inside this function. `book_data` is supplied by `_collect_book_data()` which already issued: `SELECT … FROM books WHERE id = :id`, `SELECT … FROM book_sections WHERE book_id = :id ORDER BY order_index`, `SELECT … FROM summaries WHERE id IN (default_summary_ids)`, `SELECT … FROM annotations WHERE (content_type='book_summary' AND content_id=:book_id) OR (content_type IN ('section_content','section_summary') AND content_id IN section_ids)`. The render function is pure over its input.

**State transitions:**
- None. The function is stateless and does not write.

**Error branches:**
- Missing `book_data.title` → render `# ` (empty H1). Defensive — book.title is non-nullable per schema; this would be a corrupt DB row. Caller surfaces 404 if book missing.
- Missing `summary_md` for a section listed in `rendered_sections` → would normally not happen (filtered on `default_summary_id IS NOT NULL`); if it does (orphan FK), render an empty body for that section. Caller is responsible for data integrity.
- `gfm_slug` returns empty → fallback to `section-{order_index:03d}` (FR-B7).
- `sanitize_image_urls` regex doesn't match malformed input → string passes through unchanged. Test gate `assert "/api/v1/images/" not in body` enforces correctness.

**Concurrency notes:**
- Pure function; reentrant. Multiple in-flight requests for the same book read isolated `book_data` snapshots from `_collect_book_data()`. SQLAlchemy session isolation handles read consistency. No shared state.

### 6.2 Flow: Frontend `Copy as Markdown` with ClipboardItem fallback

**Entry:** User clicks `Copy as Markdown` button on `BookOverviewView.vue` or in `ExportCustomizeModal.vue` footer.

```
FUNCTION onCopyClick(bookId, selection):
  # selection: optional SummaryExportSelection (one-click path = none)
  exporting.value = true
  url = buildExportUrl(bookId, format='markdown', selection)

  TRY:
    IF navigator.clipboard?.write AND window.ClipboardItem:
      # Modern path — survives Safari user-gesture chain
      fetchPromise = fetch(url).then(r => {
        IF NOT r.ok: THROW new Error('fetch failed')
        # Capture X-Empty-Export header for toast variant decision
        isEmpty.value = r.headers.get('X-Empty-Export') === 'true'
        RETURN r.blob()
      })
      AWAIT navigator.clipboard.write([new ClipboardItem({
        'text/plain': fetchPromise
      })])
    ELSE:
      # Legacy path
      response = AWAIT fetch(url)
      IF NOT response.ok: THROW new Error('fetch failed')
      isEmpty.value = response.headers.get('X-Empty-Export') === 'true'
      text = AWAIT response.text()
      AWAIT navigator.clipboard.writeText(text)

    # Success
    msg = isEmpty.value ? 'Summary copied (empty)' : 'Summary copied to clipboard'
    showToast(msg, 'success')

  CATCH err:
    # Disambiguate by error type
    IF err.message == 'fetch failed' OR err instanceof TypeError:
      # Network or HTTP failure
      showToast('Export failed — check your connection.', 'error')
    ELIF err instanceof DOMException AND err.name IN ('NotAllowedError','SecurityError'):
      # Clipboard permission denial
      showToast("Couldn't copy — try Export instead.", 'error')
    ELSE:
      # Anything else — assume clipboard
      showToast("Couldn't copy — try Export instead.", 'error')

  FINALLY:
    exporting.value = false
```

**DB calls:** none on the frontend. The API route → `ExportService.export_book()` → `_collect_book_data()` reads (per Flow 6.1).

**State transitions:**
- `exporting: false → true` on click; `→ false` in `finally`. Bound to BOTH primary buttons via FR-F14 (mutual disable).
- `isEmpty: undefined → bool` once response headers parse. Used for toast variant.

**Error branches:**
- Fetch reject (network down, CORS, CSP) → caught as `TypeError`/`Error('fetch failed')` → network toast.
- HTTP error (404 book deleted, 400 stale `exclude_section`) → `r.ok = false` → throw → network toast.
- ClipboardItem promise rejection chains through clipboard.write — distinguish from clipboard-permission rejection via the inner-fetch having succeeded vs failed (the `THROW new Error('fetch failed')` happens before clipboard touches the promise, so a fetch error always bubbles as fetch error, not clipboard error).
- `navigator.clipboard.writeText` reject (Safari permission, Firefox in non-secure context) → DOMException with name `NotAllowedError` → clipboard toast.
- `navigator.clipboard` undefined (very old browser, file:// protocol) → branch into legacy-path else clause; same DOMException handling on the legacy path.

**Concurrency notes:**
- FR-F14 disables both Export and Copy buttons while `exporting=true`, eliminating Export-then-Copy and rapid double-click overlap.
- The user-gesture chain is preserved by passing the `fetchPromise` directly into `ClipboardItem` rather than `await`-ing the fetch first. Browser sees a synchronous `clipboard.write([...])` invocation inside the click handler.
- No locking required — GET is idempotent server-side; client-side state is a single boolean ref.

---

## 7. Gap Register

| # | Gap | Exposed By | Severity | Disposition | Notes |
|---|-----|-----------|----------|-------------|-------|
| G1 | `X-Empty-Export` detection used `body.count('## ')` text-grep — false negatives when book summary contains `## ` | S22 | significant | **Apply patch** | FR-A6 + FR-B1 changed to renderer-intent (4-bool tracking, returned in tuple). |
| G2 | Empty-slug case (purely non-alphanumeric title) → invalid `#` anchor target | S23 | significant | **Apply patch** | FR-B7 fallback to `section-{order_index:03d}`. Added E27. |
| G3 | FR-B5 regex (1) missed GFM image with title attribute | S24 | significant | **Apply patch** | Regex (1) extended with optional `\s+"[^"]*"` group. Added E28. |
| G4 | FR-B9 free-floating annotation partitioning ambiguous given 3-member ContentType enum | B1-1, S12 | significant | **Apply patch** | FR-B9 rewritten with 4-rule partitioning using `BOOK_SUMMARY` content_type; section-scope + empty-selected_text silently skipped. Added E30. |
| G5 | ClipboardItem inner-fetch failure — which toast (clipboard vs network)? | S8 | minor | **Apply patch** | FR-F5 disambiguates: fetch reject → network toast; clipboard-permission → clipboard toast. |
| G6 | Stale UI section list → 400 from server is the only recovery path | S19 | minor | **Apply patch** | FR-F6 refreshes section list via `GET /api/v1/books/{id}` on modal open. |
| G7 | No in-flight button disable on Export/Copy (rapid double-click → multiple downloads) | S18, S21 | minor | **Apply patch** | New FR-F14 wires `exporting: boolean` to button-disable + spinner; mutual disable across Export and Copy. |
| G8 | Slugify implementation library/function not pinned | S15 | minor | **Apply patch** | FR-A2 pins `app/services/slug.py::filename_slug(title)` with explicit ASCII-only regex. |
| G9 | Slug functions diverge by purpose (TOC=Unicode, filename=ASCII) — unstated in Decision Log | S16 | minor | **Apply patch** | New D21 explains the asymmetry explicitly. Added E31 (Unicode title). |
| G10 | Annotation note/selected_text content can break blockquote rendering | S12 | minor | **Apply patch** | FR-B8 escaping rule: newlines collapse to space; block-level markdown triggers escaped with `\`. |
| G11 | No NFR for books > 30 sections | S20 | minor | **Apply patch** | G1 success metric extended to 100 sections / 1000 annotations linear. |
| G12 | TOC behavior when zero summarized sections (empty heading risk) | S5 | minor | **Apply patch** | FR-B6 step 4: omit TOC heading + list when `len(rendered_sections) == 0`. |
| G13 | CLI behavior on UPLOADING/PARSING book status unspecified | S6 | minor | **Apply patch** | FR-C6: CLI is unaffected by status; render whatever `_collect_book_data` finds and exit 0. |
| G14 | Modal accessibility (focus trap, focus return) and toast ARIA live-region unspecified | B4-2 | minor | **Apply patch** | FR-F6 mirrors PresetPickerModal focus pattern; FR-F13 wraps toasts in `role=status aria-live=polite`. |
| G15 (folded into G7) | `exporting: boolean` had no UI manifestation in FRs | B4-1 | minor | **Apply patch (G7)** | Resolved via the same FR-F14. |
| G16 | CLI `--help` content for new flags not pinned | B4-3 | minor | **Apply patch** | FR-C1 mandates Typer `help=` strings + grouped command docstring. |
| G17 | No Cache-Control header on export response | B2-1 | minor | **Apply patch** | FR-A2 adds `Cache-Control: private, max-age=0`. |
| G18 | Old CLI scripts using OLD markdown shape silently break on upgrade | S25 | forward-compat | **Accept as risk** | Rationale: per workstream, Book Companion is unpublished; single-user; no automation depends on the old shape. D1 already chose 'replace not parallel'. See §8. |
| G19 | `GET /api/v1/export/book/{id}?format=json` has no v1.6 frontend consumer | W1-rev | minor | **Apply patch** | §7.1 note clarifies JSON is preserved for CLI/API parity (CLI uses it; API users may script against it). |

---

## 8. Accepted Risks

- **G18 — Old CLI shape break:** Existing CLI automation scripts that depend on the OLD kitchen-sink Markdown shape (Concepts Index, External References, every-section dump) will silently break on upgrade. Accepted because Book Companion is unpublished (per `~/.pmos/workstreams/book-companion.md`), single-user, and D1 has already explicitly chosen "replace not parallel" rather than running two markdown shapes in parallel. If the tool is ever published or shared, the changelog note (FR-D2) will surface the breakage; revisit then with `--legacy-shape` or a one-shot deprecation banner.

---

## 9. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| O1 (carried from spec) | Toast position (top-right vs bottom-right) and stacking order | Maneesh | During /plan |
| O2 (carried from spec) | When a book is in `PARSE_FAILED`, is the empty-state copy "Generate a summary first" accurate, or should it be "This book failed to parse — nothing to export"? | Maneesh | Before /plan |

No new Open Questions surfaced by simulation — all gaps resolved via patches or accepted risks.

---

## 10. Spec Patches Applied

| # | Section | Change Summary | Gap # |
|---|---------|---------------|-------|
| 1 | FR-B1 | Return `(body, is_empty)` tuple where `is_empty` is derived from 4 block-emit booleans tracked during render | G1 |
| 2 | FR-A6 | Detection now reads renderer's `is_empty` flag; explicit prohibition on text-grep | G1 |
| 3 | FR-B7 | Empty-slug fallback to `section-{order_index:03d}`; Unicode-aware alphanumeric clarified | G2, G9 |
| 4 | FR-B5 | Regex (1) extended with optional title-attribute group | G3 |
| 5 | FR-B9 | Rewritten with explicit 4-rule partitioning over `Annotation.content_type` | G4 |
| 6 | FR-F5 | Toast disambiguation: fetch-fail → network toast; clipboard-permission → clipboard toast | G5 |
| 7 | FR-F6 | Modal mount issues `GET /api/v1/books/{id}` to refresh section list; focus-trap + focus-return mirror PresetPickerModal | G6, G14 |
| 8 | FR-F14 (NEW) | In-flight button disable + spinner pattern; mutual disable across Export and Copy | G7, G15 |
| 9 | FR-A2 | `app/services/slug.py::filename_slug` pinned (ASCII-only regex); `Cache-Control: private, max-age=0` added | G8, G17 |
| 10 | D21 (NEW) | Decision Log entry calling out TOC slug (Unicode) vs filename slug (ASCII) divergence | G9 |
| 11 | FR-B8 | Annotation content escaping rule (newlines → space; block-level triggers escaped with `\`) | G10 |
| 12 | G1 success metric | Extended to 100 sections / 1000 annotations linear | G11 |
| 13 | FR-B6 step 4 | Omit TOC heading + list when no sections render | G12 |
| 14 | FR-C6 | CLI is unaffected by `book.status` (UPLOADING/PARSING render front-matter-only, exit 0) | G13 |
| 15 | FR-F13 | ToastContainer ARIA live-region + per-toast aria-label | G14 |
| 16 | FR-C1 | Typer `help=` per flag + grouped command docstring | G16 |
| 17 | §7.1 | Note explaining JSON path is preserved for CLI/API parity even though no v1.6 frontend consumes it | G19 |
| 18 | §9 Edge Cases | Added E27 (emoji-only title), E28 (image with title attr), E29 (book summary with `## ` substring), E30 (BOOK_SUMMARY-scope annotations), E31 (Unicode title) | G2, G3, G1, G4, G9 |

18 surgical edits across 11 distinct spec sections.

---

## 11. Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | (a) Scenario completeness — Spec E12 ("book has no sections at all") was implicitly covered via S5 + S12 but not explicitly traced. Cosmetic. (b) All 5 review checks otherwise passed: bucket completeness ✓, cross-reference (forward + reverse) ✓, Gap Register integrity ✓, high-severity coverage ✓. | Added S5b row to §3 Coverage Matrix tracing spec E12 to FR-F7 (modal placeholder) + FR-B6/FR-B11 (front-matter export still works). No new gaps surfaced. |
