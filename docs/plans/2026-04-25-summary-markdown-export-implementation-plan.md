# Summary Markdown Export — Implementation Plan

**Date:** 2026-04-25
**Spec:** `docs/specs/2026-04-25-summary-markdown-export-spec.md`
**Simulation:** `docs/simulations/2026-04-25-summary-markdown-export-simulation.md`
**Requirements:** `docs/requirements/2026-04-25-summary-markdown-export.md`

---

## Overview

Rebuild the per-book Markdown export shape into a summaries-focused, selectable, portability-sanitized artifact. New shape: front matter → optional anchored TOC → optional book summary → per-section rendering with cascade-respecting highlights → optional `## Notes` footer for book-scope annotations. The CLI gains four exclusion flags (`--no-book-summary`, `--no-toc`, `--no-annotations`, `--exclude-section`); the API GET extends with the same four selection params; the frontend grows three actions on the book detail page (Export / Copy / Customize) wired through a tri-state-toggled modal. JSON export is untouched. Library Markdown export is removed (CLI exits 2; HTTP returns 410 Gone). Approach: backend foundation → API → CLI → frontend → docs, with TDD (red-green-commit) at every task and inline verification.

**Done when:** All 39 spec FRs are implemented; `pytest tests/` passes including new behavioral tests for renderer + slug + API + CLI; `npm run test:unit` passes including ExportCustomizeModal spec; manual /verify smoke confirms (a) Export downloads the new shape with anchored TOC working in Obsidian/GitHub, (b) Copy lands byte-equal markdown in clipboard, (c) library Markdown export hits 410, (d) `assert "/api/v1/images/" not in body` for fixture book exports; CLAUDE.md updates landed.

**Execution order:**

```
Phase A — Backend foundation (sequential):
  T1 (slug helpers) → T2 (ExportSelection + book-scope annotation helper)
                    → T3 (image sanitizer)
                    → T4 (renderer: front matter + sections + emptiness tuple)
                    → T5 (renderer: TOC + slug-disambiguation table)
                    → T6 (renderer: highlights + notes + escaping;
                          public method `export_book_markdown(book_id, sel)`)

Phase B — API (depends on Phase A):
  T7 (extend GET book/{id}: selection params, X-Empty-Export, Cache-Control,
      slug filename, 400 invalid section, 410 library markdown)

Phase C — CLI (depends on Phase A):
  T9 (book: 4 flags + help text + strict --format json combo error;
      library: --format markdown → exit 2 with named error)

Phase D — Frontend (depends on Phase B):
  T11 (api/export.ts: exportBookSummary helper + SummaryExportSelection + library JSON-only)
  T12 (BookOverviewView: 3 buttons + in-flight UX + clipboard pattern + toasts) [P with T13]
  T13 (ExportCustomizeModal.vue + tests) [P with T12]
  T14 (BackupSettings cleanup: dropdown → button)
  T15 (ToastContainer regression test — verify existing infra)

Phase E — Docs:
  T16 (CLAUDE.md three edits per FR-D1)

Final:
  TN (final verification: lint, tests, JSON regression, FR-ID coverage grep,
      Playwright smoke; post-merge run /changelog for FR-D2)
```

[P] = can run in parallel with the marked sibling.

Note: task slots T8 and T10 were merged into T7 and T9 respectively during review loop 1 — the API library-410 lives inside T7 and the CLI library-exit-2 lives inside T9.

---

## Decision Log

> Inherits 21 architecture decisions from spec D1-D21. Entries below are implementation-specific.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| P1 | `_render_summary_markdown` lives **as a method on `ExportService`** (not a separate `export_renderer.py` module). | (a) **Method on ExportService** (chosen), (b) New `app/services/export_renderer.py` module, (c) Free function in `export_service.py`. | Spec FR-B1 explicitly calls it "a new method on `ExportService`". The render is closely coupled to `_collect_book_data()` (consumes its output). Splitting into a separate module would require either passing the service or duplicating model imports. The file remains < 500 lines with the new method added. |
| P2 | Add a sibling helper `_collect_book_annotations(book) → list[dict]` for book-scope annotations rather than mutating `_collect_book_data`. | (a) **Sibling helper** (chosen), (b) Extend `_collect_book_data` to include book-scope annotations. | The current `_collect_book_data` filters annotations purely by `content_id IN section_ids` — book-scope annotations (`content_type=BOOK_SUMMARY`, `content_id=book.id`) are not loaded today. Spec FR-B3 promises JSON output is byte-for-byte identical for the same fixture. Option (b) would change the JSON shape if any fixture has book-scope annotations (currently none, but the contract is strict). Option (a) keeps `_collect_book_data` literally unchanged; the new helper is invoked only from the new render path. |
| P3 | Slug helpers live in **`backend/app/services/slug.py`** with two named functions: `filename_slug(title) → str` (ASCII-only) and `gfm_slug(title) → str` (Unicode-aware). Per spec D21, two helpers, one intent each. | (a) **`app/services/slug.py`** (chosen), (b) `app/utils/slug.py`, (c) module-level helpers inside `export_service.py`. | Services directory is the established home for cross-cutting helpers (`section_classifier.py`, `image_url_rewrite.py`). Two functions in one ~50-line module is right-sized; co-locating their tests in `tests/unit/test_slug.py` keeps the test surface clean. |
| P4 | Image sanitizer lives in `app/services/export_service.py` as a private module-level function `_sanitize_image_urls(text: str) → str`, NOT in `app/services/parser/image_url_rewrite.py`. | (a) **Private to export_service** (chosen), (b) Public helper in `image_url_rewrite.py`. | The `image_url_rewrite.py` module's role is the **reverse** direction — it inserts `/api/v1/images/{id}` URLs into parsed content. The export sanitizer **removes** them for portability; opposite intent. Co-locating opposite operations in the same module would invite confusion. The function is only used by the renderer; private is appropriate. |
| P5 | New backend tests split: `tests/unit/test_slug.py`, `tests/unit/test_export_renderer.py` (tests `_render_summary_markdown` directly via the service), `tests/integration/test_api/test_export_book_markdown.py` (new file for the new HTTP route shape). The existing `test_export_api.py` is **modified** to update the `test_export_library_markdown` test to expect 410. | (a) **Split** (chosen), (b) Append everything to `test_export_api.py`. | The renderer test is unit-scope (no DB / HTTP). Integration tests for the new shape benefit from a focused file the executor can run as a fast feedback loop (`pytest tests/integration/test_api/test_export_book_markdown.py -v`). Old library-markdown test must change in place because the fixture path is unchanged. |
| P6 | `ExportSelection` is a `@dataclass(frozen=True)` (not a pydantic model). Spec FR-B4 said "pydantic model or dataclass" — pick. | (a) **Frozen dataclass** (chosen), (b) Pydantic BaseModel, (c) Plain dataclass, (d) TypedDict. | Pure-internal type with no validation needs (route handler validates `exclude_section` against `book.sections`; CLI validates flag combinations). Frozen prevents accidental mutation in render-time logic. Zero dependency cost. Pydantic would buy us nothing here. |
| P7 | `ExportCustomizeModal.vue` lives in **`frontend/src/components/book/`** (new directory if not present), NOT in `components/common/`. | (a) **`components/book/`** (chosen — co-locates with `SuggestedTagsBar.vue`, `SummarizationProgress.vue`), (b) `components/common/`, (c) `components/export/` (new dir). | The modal is book-scoped — it operates against `book.sections`, fetches `/api/v1/books/{id}`, and is mounted from `BookOverviewView`. `components/book/` already groups book-detail subcomponents per existing imports in `BookOverviewView.vue:107-108`. New top-level `export/` directory would orphan a single component. |
| P8 | FR-F13 (ToastContainer) is **verification-only**, not new build. The component already exists at `frontend/src/components/common/ToastContainer.vue` and is mounted in `AppShell.vue` (commit `764b7d0` — landed after the /spec session began). T15 writes a regression test ensuring `useUiStore().showToast(msg, type)` toasts render with `aria-live="polite"` and the type-specific class; no new component code. | (a) **Verify only** (chosen), (b) Build new ToastContainer (would conflict with existing). | Discovered during Phase 2 deep code study — recon-stale spec assumption. The existing component already implements ARIA live-region (`role="region" aria-live="polite"`) per FR-F13's requirement. Re-implementing would regress the existing 5-toast FIFO cap and dismiss timer logic. |
| P9 | T12 (BookOverviewView) and T13 (ExportCustomizeModal) are marked `[P]` (parallel) in the execution order; both depend on T11 (api client) but neither blocks the other. | (a) **Mark as parallel**, (b) Force sequential. | If two engineers / sessions are running, the modal can be developed in isolation against an empty book detail page that just renders the buttons. Tests don't share state. The plan acknowledges this but a single-engineer execution can still do them sequentially without harm. |
| P10 | TDD strictness: **red → green → commit** at every code-producing step. Backend tests use `pytest`'s `tmp_path` + an in-memory SQLite database via `aiosqlite:///:memory:` for renderer unit tests; integration tests use the existing `client` fixture. Frontend tests use Vitest + Vue Test Utils (existing pattern in `__tests__/` directories). | (a) **Strict TDD** (chosen), (b) Implement-first then test, (c) TDD only for backend. | Workstream learnings under `## /execute` repeatedly emphasize red-green proof for non-trivial logic. The render function has multiple branches (toggles, slug disambiguation, escape rules, emptiness tracking) — TDD makes each branch's correctness verifiable per task. |

---

## Code Study Notes

**Patterns to follow:**
- `ExportService.__init__` takes `AsyncSession`, constructs `BookRepository` and `SummaryRepository`. `_render_summary_markdown` should be a method that consumes `book_data: dict` (output of `_collect_book_data`) plus `selection: ExportSelection`. Render function is **pure** (no DB calls inside).
- Existing test fixture pattern: `tests/integration/test_api/test_export_api.py:43` uses `pytest.skip("No books in test DB")` when fixtures aren't seeded — tests that require seeded data must seed inside the test or use a fixture from `conftest.py`. The codebase has no shared seeded-book fixture today; new tests should construct minimal `Book + BookSection + Summary + Annotation` rows via the repos.
- API route pattern: `app/api/routes/export.py:14-35` uses `@router.get`, `Query` with regex, `Depends(get_export_service)`, returns `PlainTextResponse(content, media_type="text/markdown", headers={"Content-Disposition": ...})`. Extend by adding more `Query()` params and headers.
- CLI pattern: `app/cli/commands/export_cmd.py:11-28` uses `@async_command`, `async with get_services() as svc:` returns dict; errors caught and printed via `print_error()`, exit 1 on `Exception`. Add new flags via `typer.Option`.
- Frontend modal pattern: `PresetPickerModal.vue` uses `class="modal-overlay"` (fixed inset, `rgba` backdrop), `class="modal-body"` width `min(480px, 92vw)`, Escape via `document.addEventListener('keydown', onKeydown)` set on `onMounted` and removed on `onUnmounted`, emits `submit`/`cancel`. Reuse the same CSS pattern (or extract to a shared component if a third modal lands later — out of scope for this plan).
- API client pattern: `frontend/src/api/export.ts` uses bare `fetch`. The codebase has a `frontend/src/api/client.ts` with `apiClient.get/post/...` wrappers — the new `exportBookSummary` will use bare `fetch` to mirror the existing helper, consistent with prior judgment.
- Toast pattern: `BackupSettings.vue:33` shows the `useUiStore().showToast('Backup created', 'success')` call style. Mirror exactly.

**Existing infrastructure to reuse:**
- `frontend/src/api/export.ts:23-31` `triggerDownload(response, filename)` helper — used as-is by FR-F4.
- `frontend/src/components/common/ToastContainer.vue` + `useUiStore().showToast/dismissToast/toasts` — already mounted in `AppShell.vue` per P8.
- `frontend/src/components/reader/FloatingToolbar.vue:29` — bare `navigator.clipboard.writeText` precedent. New code uses the `ClipboardItem`-with-promise pattern per FR-F5.
- `BookSection.depth`, `BookSection.order_index`, `Book.default_summary_id`, `BookSection.default_summary_id`, `Summary.summary_md`, `Annotation.content_type` (3-member enum: `SECTION_CONTENT`, `SECTION_SUMMARY`, `BOOK_SUMMARY`), `Annotation.selected_text`, `Annotation.note` — all confirmed via `models.py:74-77, 203-215, 354-380, 419-444`.

**Constraints discovered (verified at file:line):**
- `app/services/parser/image_url_rewrite.py:63-96` confirms in-app images are written as `/api/v1/images/{id}` (NOT `image://N`). Sanitizer regex must target the real pattern.
- `app/db/models.py:74-77` confirms `ContentType` enum has exactly three values: `SECTION_CONTENT`, `SECTION_SUMMARY`, `BOOK_SUMMARY`. There is **no** `BOOK_CONTENT` value. FR-B9 partitioning aligns with this.
- `app/services/export_service.py:97-103` filters annotations by `content_id IN section_ids` only — book-scope annotations are NOT in `book_data["annotations"]` today. Per P2, the renderer queries them via a new sibling helper.
- `frontend/src/components/app/AppShell.vue:23` confirms `<ToastContainer />` is already mounted globally.
- `frontend/src/views/BookOverviewView.vue:51-69` confirms `.actions` div currently contains a router-link `Read` button + the `SummarizationProgress` component. New buttons land here.
- `frontend/src/components/settings/BackupSettings.vue:122-140` confirms current library-export UI: format `<select>` (`json`/`markdown`) + `Export` button. Replace per FR-F11.
- `backend/app/api/deps.py:130-136` exposes `get_export_service` dependency. No change needed.
- `backend/app/cli/deps.py:221-223` instantiates `ExportService` for CLI. No change needed.

**Data flow trace (write→read pipeline):**
- Write entry: `_render_summary_markdown` → returns markdown string + emptiness flag.
- Storage target: none — purely synchronous render; no persistence, no cache, no queue.
- Read entry: HTTP route handler returns `PlainTextResponse`; CLI command writes to file or stdout.
- Verification: confirmed all three points exist in spec FRs (FR-B1, FR-A1/A6, FR-C2). No missing wiring.

---

## Prerequisites

- Backend dev environment ready: `cd backend && uv sync --dev`.
- Frontend dev environment ready: `cd frontend && npm install`.
- At least one seeded book with summaries for manual verification: `cd backend && uv run python tests/fixtures/download_fixtures.py && uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub` (run once; persists in the dev SQLite DB).
- Baseline: run `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py -v` and capture the output. Existing tests should pass; the plan changes some of them deliberately. Record the count of pre-existing tests so /verify can detect regressions vs. intentional changes.
- Pre-baseline: `cd backend && uv run ruff check .` to capture any pre-existing lint debt unrelated to this work — scope ruff assertions in tasks to changed files only if the baseline is dirty (per `~/.pmos/learnings.md` /execute entry).

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/app/services/slug.py` | `filename_slug(title)` ASCII-only + `gfm_slug(title)` Unicode-aware helpers (D21) |
| Create | `backend/tests/unit/test_slug.py` | Behavioral tests for both slug helpers across edge cases (illegal chars, CJK, empty, length cap, duplicates) |
| Modify | `backend/app/services/export_service.py` | Add: module-level `_sanitize_image_urls(text)`, frozen `@dataclass ExportSelection`, method `_collect_book_annotations(book)`, method `_render_summary_markdown(book_data, selection) → tuple[str, bool]`. Replace the markdown branch of `export_book` to call the new renderer. Remove the markdown branch of `export_library` (raise `ExportError` so route/CLI surface their own messages). |
| Create | `backend/tests/unit/test_export_renderer.py` | Behavioral tests for `_render_summary_markdown` covering: front matter shapes, TOC anchors + slug disambiguation, image sanitizer (md+html+title-attr), annotation rendering (highlight only, highlight+note, free-floating note), cascade rule, emptiness tuple invariants |
| Modify | `backend/app/api/routes/export.py:14-55` | Extend `GET /book/{id}` with selection query params + new headers (Content-Disposition slug, Cache-Control, X-Empty-Export); convert library `format=markdown` to 410 |
| Modify | `backend/tests/integration/test_api/test_export_api.py` | Update `test_export_library_markdown` to expect 410. Keep other tests untouched. |
| Create | `backend/tests/integration/test_api/test_export_book_markdown.py` | New behavioral tests for the new GET shape (selection querystring, 400 invalid section, X-Empty-Export header, slug filename, Cache-Control header) |
| Modify | `backend/app/cli/commands/export_cmd.py` | Add 4 flags + grouped help docstring; add flag-combination guard for `--format json`; replace `export_library` body to early-exit with named error when `fmt == "markdown"` |
| Create | `backend/tests/e2e/test_export_cli.py` | New CLI behavioral tests using `CliRunner` — flag combinations, exit codes, stdout vs file output, removed library subcommand |
| Modify | `frontend/src/api/export.ts` | Add `interface SummaryExportSelection`, `exportBookSummary(bookId, selection?)` returning `{ blob, filename, text, isEmpty }`. Constrain `exportLibrary` to `format: 'json'` (drop the `'markdown'` branch). |
| Modify | `frontend/src/views/BookOverviewView.vue:51-69` | Add `Export summary`, `Copy as Markdown` primary buttons, `Customize…` text link inside `.actions` div. Add `<ExportCustomizeModal v-if="showModal" :book-id="..." :book="..." @close="..." />`. Add reactive state (`showModal`, `exporting`) + click handlers per FR-F2/F3/F4/F5/F12/F14. |
| Create | `frontend/src/components/book/ExportCustomizeModal.vue` | New modal: refresh-on-open, four toggles (Book summary disabled if no book summary, TOC, Annotations, Sections tri-state), section list ordered by `order_index`, count footer, Cancel/Export/Copy buttons + in-flight UX |
| Create | `frontend/src/components/book/__tests__/ExportCustomizeModal.spec.ts` | Vitest unit tests covering: tri-state toggle behavior, querystring assembly, hidden-count footer, Export and Copy emit the same selection, refresh-fail fallback, in-flight disable |
| Modify | `frontend/src/components/settings/BackupSettings.vue:122-140` | Replace format `<select>` + button with single `Export library (JSON)` button. Drop `exportFormat` ref. |
| Modify | `frontend/src/components/common/__tests__/ToastContainer.spec.ts` | Add (or verify) regression test asserting `useUiStore().showToast(msg, type)` produces a toast with `aria-live="polite"` region + `toast--{type}` class |
| Modify | `CLAUDE.md` | Three FR-D1 edits: workflow-example flag, Markdown-export entry, library-deprecation callout |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Existing JSON export test breaks due to fixture book having book-scope annotations | Low | Per P2, `_collect_book_data` is **literally** unchanged — book-scope annotations are loaded by a new sibling helper called only from the markdown render path. JSON regression test (TN) re-runs `test_export_book_json_when_books_exist` to confirm. |
| GFM slug Unicode rule diverges across viewers (GitHub uses one regex, Obsidian uses another) | Medium | T5 implements the most-restrictive form (lowercase, alphanumeric / space → dash, collapse consecutive dashes, strip non-Unicode-alnum). Manual /verify exercises GitHub web preview + VS Code preview + Obsidian on the same exported file. If TOC anchors fail in any viewer, capture the actual auto-anchor it generates and adjust `gfm_slug` to match. |
| `ClipboardItem` API shape varies across browsers (some require explicit `'text/plain'` MIME) | Medium | T12 implements the spec's exact branch + a feature-detect on `navigator.clipboard?.write && window.ClipboardItem`. Manual /verify on Safari, Chrome, Firefox confirms both paths. Test at the unit level is brittle (`navigator.clipboard` is jsdom-mocked) — manual is the source of truth. |
| Frontend build catches a TypeScript drift between `Book` interface and the new `book.default_summary_id` access | Low | Read `frontend/src/types/index.ts` `Book` interface during T12 — confirm `default_summary_id` field exists; if not, FR-F3's empty-state check needs a different signal (e.g., compute from `summary_progress.summarized > 0 || (book.sections || []).some(s => s.has_summary)`). T12 step 1 verifies the type before writing UI logic. |
| Stale section list refresh (FR-F6) — modal mount fetch failure leaves user in confused state | Low | T13 implements the spec's "fall back to cached sections + inline notice" behavior. Tested in `ExportCustomizeModal.spec.ts` via mocked fetch reject. |
| CLAUDE.md edit (T16) accidentally drops other content | Low | Use `Edit` tool with surgical `old_string` / `new_string` — never `Write` over the whole file. |

---

## Rollback

This plan does not introduce database migrations or destructive operations. Standard rollback: `git revert` the merge commit. No data backfill to undo.

If T8 (library-markdown 410) ships before the frontend BackupSettings cleanup (T14) and a user is on the dev server, the existing dropdown's "Markdown" option will return 410 and surface as a toast error. Mitigation: ship T14 in the same commit as T8 (or commit T14 first). The plan orders Phase B before Phase D for backend correctness, but T14 has no backend dependency and could be re-ordered if a UI freeze risk surfaces.

---

## Tasks

### T1: Slug helpers (`app/services/slug.py`)

**Goal:** Two pure functions that produce filename-safe and GFM-anchor-safe slugs, with comprehensive edge-case tests.
**Spec refs:** FR-A2, FR-B7, D21

**Files:**
- Create: `backend/app/services/slug.py`
- Create: `backend/tests/unit/test_slug.py`

**Steps:**

- [ ] Step 1: Write failing tests for `filename_slug`
  ```python
  # backend/tests/unit/test_slug.py
  from app.services.slug import filename_slug, gfm_slug

  class TestFilenameSlug:
      def test_simple_lowercases_and_dashes(self):
          assert filename_slug("The Art of War") == "the-art-of-war"

      def test_strips_punctuation(self):
          assert filename_slug("War & Peace: A Novel!") == "war-peace-a-novel"

      def test_collapses_multiple_spaces_and_dashes(self):
          assert filename_slug("a   b---c") == "a-b-c"

      def test_strips_leading_trailing_dashes(self):
          assert filename_slug("  hello  ") == "hello"

      def test_truncates_to_80_chars(self):
          long = "x" * 200
          assert filename_slug(long) == "x" * 80

      def test_cjk_only_returns_empty(self):
          assert filename_slug("北京概要") == ""

      def test_emoji_only_returns_empty(self):
          assert filename_slug("🚀🎯") == ""

      def test_empty_string_returns_empty(self):
          assert filename_slug("") == ""

  class TestGfmSlug:
      def test_simple_lowercases(self):
          assert gfm_slug("Chapter 1") == "chapter-1"

      def test_preserves_unicode_alnum(self):
          assert gfm_slug("Café") == "café"
          assert gfm_slug("北京 概要") == "北京-概要"

      def test_strips_emoji_and_punctuation(self):
          assert gfm_slug("🚀 The Vision!") == "the-vision"

      def test_returns_empty_for_pure_emoji(self):
          assert gfm_slug("🚀🎯") == ""

      def test_collapses_consecutive_dashes(self):
          assert gfm_slug("a -- b") == "a-b"
  ```

- [ ] Step 2: Run tests; expect all to fail with ImportError
  Run: `cd backend && uv run python -m pytest tests/unit/test_slug.py -v`
  Expected: ImportError or collection failure (module doesn't exist)

- [ ] Step 3: Implement both helpers
  ```python
  # backend/app/services/slug.py
  """Slug helpers for filename and TOC anchor derivation.

  Two helpers, one intent each (per spec D21):
    - filename_slug: ASCII-only, cross-OS filesystem safety
    - gfm_slug: Unicode-aware, matches GFM viewer auto-anchors
  """
  import re
  import unicodedata

  _FILENAME_RE = re.compile(r"[^a-z0-9]+")
  # Unicode-aware alnum class: \w in Python re matches Unicode by default.
  # We strip everything that's NOT (alnum / whitespace / hyphen / underscore).
  _GFM_KEEP_RE = re.compile(r"[^\w\s\-]+", re.UNICODE)
  _GFM_WS_RE = re.compile(r"[\s_]+")
  _GFM_DASH_RE = re.compile(r"-{2,}")


  def filename_slug(title: str) -> str:
      """ASCII-only filesystem-safe slug. Returns empty string for non-ASCII titles."""
      return _FILENAME_RE.sub("-", title.lower()).strip("-")[:80]


  def gfm_slug(title: str) -> str:
      """Unicode-aware GFM slug. Lowercase, drop non-(alnum|ws|dash|underscore),
      collapse whitespace/underscores to dashes, collapse consecutive dashes,
      strip leading/trailing dashes."""
      lowered = title.lower()
      stripped = _GFM_KEEP_RE.sub("", lowered)
      dashed = _GFM_WS_RE.sub("-", stripped)
      collapsed = _GFM_DASH_RE.sub("-", dashed)
      return collapsed.strip("-")
  ```

- [ ] Step 4: Run tests; expect all to pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_slug.py -v`
  Expected: 13 passed, 0 failed

- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/slug.py backend/tests/unit/test_slug.py
  git commit -m "feat(backend): add slug helpers for filename + GFM anchor derivation"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/slug.py tests/unit/test_slug.py` — no errors
- `cd backend && uv run python -m pytest tests/unit/test_slug.py -v` — 13 passed

---

### T2: ExportSelection + book-scope annotation helper

**Goal:** Define the immutable `ExportSelection` dataclass and add `_collect_book_annotations(book)` as a sibling helper to `_collect_book_data`. Verified that book-scope annotations are queried correctly.
**Spec refs:** FR-B4, FR-B9 (annotation source), P2

**Files:**
- Modify: `backend/app/services/export_service.py` (add at module top + new method)
- Create: `backend/tests/unit/test_export_renderer.py` (start the file with this test)

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend/tests/unit/test_export_renderer.py
  import pytest
  from app.services.export_service import ExportSelection, ExportService

  class TestExportSelection:
      def test_default_includes_all(self):
          sel = ExportSelection()
          assert sel.include_book_summary is True
          assert sel.include_toc is True
          assert sel.include_annotations is True
          assert sel.exclude_section_ids == frozenset()

      def test_immutable(self):
          sel = ExportSelection()
          with pytest.raises((AttributeError, Exception)):
              sel.include_toc = False  # type: ignore

      def test_with_excludes(self):
          sel = ExportSelection(exclude_section_ids=frozenset({1, 2, 3}))
          assert 2 in sel.exclude_section_ids

  # _collect_book_annotations behavioral test deferred to integration tier (T7)
  # since it requires a DB session — covered there with seeded annotations.
  ```

- [ ] Step 2: Run; expect ImportError on `ExportSelection`
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestExportSelection -v`
  Expected: ImportError

- [ ] Step 3: Implement `ExportSelection` and `_collect_book_annotations`
  ```python
  # backend/app/services/export_service.py — add near imports
  from dataclasses import dataclass, field
  from sqlalchemy import select
  from app.db.models import Annotation, ContentType
  ```
  ```python
  # New: module-level dataclass (after existing imports, before class ExportService)
  @dataclass(frozen=True)
  class ExportSelection:
      include_book_summary: bool = True
      include_toc: bool = True
      include_annotations: bool = True
      exclude_section_ids: frozenset[int] = field(default_factory=frozenset)
  ```
  ```python
  # New method on ExportService — book-scope annotations only
  async def _collect_book_annotations(self, book: Book) -> list[dict]:
      """Load annotations whose content_type=BOOK_SUMMARY and content_id=book.id.

      Sibling to _collect_book_data. Kept separate so JSON export remains
      byte-identical (FR-B3); the markdown render path is the only consumer.
      """
      result = await self.session.execute(
          select(Annotation).where(
              Annotation.content_type == ContentType.BOOK_SUMMARY,
              Annotation.content_id == book.id,
          )
      )
      anns = list(result.scalars().all())
      return [
          {
              "id": a.id,
              "selected_text": a.selected_text or "",
              "note": a.note or "",
              "type": a.type.value if a.type else None,
          }
          for a in anns
      ]
  ```

- [ ] Step 4: Run unit test — expect pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestExportSelection -v`
  Expected: 3 passed

- [ ] Step 5: Verify the existing JSON export test still passes (no regression on `_collect_book_data`)
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py::test_export_library_json -v`
  Expected: 1 passed

- [ ] Step 6: Commit
  ```bash
  git add backend/app/services/export_service.py backend/tests/unit/test_export_renderer.py
  git commit -m "feat(backend): add ExportSelection dataclass + book-scope annotation collector"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/export_service.py tests/unit/test_export_renderer.py` — no errors
- `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py tests/integration/test_api/test_export_api.py::test_export_library_json -v` — 4 passed

---

### T3: Image-URL sanitizer

**Goal:** Strip every `/api/v1/images/{id}` reference from rendered markdown via two pinned regexes (FR-B5).
**Spec refs:** FR-B5

**Files:**
- Modify: `backend/app/services/export_service.py` (add private module-level function)
- Modify: `backend/tests/unit/test_export_renderer.py` (add a test class)

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # Append to backend/tests/unit/test_export_renderer.py
  from app.services.export_service import _sanitize_image_urls

  class TestSanitizeImageUrls:
      def test_md_image_with_alt(self):
          result = _sanitize_image_urls("Body ![figure 3](/api/v1/images/17) text")
          assert result == "Body [Image: figure 3] text"
          assert "/api/v1/images/" not in result

      def test_md_image_empty_alt(self):
          assert _sanitize_image_urls("![](/api/v1/images/5)") == "[Image]"

      def test_md_image_with_title_attr(self):
          # Spec G3 / FR-B5 regex (1) extension
          result = _sanitize_image_urls('![figure](/api/v1/images/17 "Title text")')
          assert result == "[Image: figure]"
          assert "/api/v1/images/" not in result

      def test_md_image_special_chars_in_alt(self):
          # alt with [ ] would break Markdown image syntax upstream — won't reach here
          result = _sanitize_image_urls('![alt with parens (here)](/api/v1/images/9)')
          assert result == "[Image: alt with parens (here)]"

      def test_html_img_with_alt(self):
          result = _sanitize_image_urls('<img src="/api/v1/images/12" alt="diagram" />')
          assert result == "[Image: diagram]"

      def test_html_img_no_alt(self):
          result = _sanitize_image_urls('<img src="/api/v1/images/12" />')
          assert result == "[Image]"

      def test_html_img_single_quotes(self):
          result = _sanitize_image_urls("<img src='/api/v1/images/12' alt='x' />")
          assert result == "[Image: x]"

      def test_html_img_extra_attrs(self):
          src = '<img class="big" src="/api/v1/images/12" alt="t" width="200" />'
          assert _sanitize_image_urls(src) == "[Image: t]"

      def test_multiple_images_in_one_text(self):
          src = "First ![a](/api/v1/images/1) middle ![b](/api/v1/images/2) end"
          assert _sanitize_image_urls(src) == "First [Image: a] middle [Image: b] end"

      def test_no_images_passthrough(self):
          assert _sanitize_image_urls("plain text") == "plain text"

      def test_zero_substring_invariant(self):
          # G4 success metric: "/api/v1/images/" never survives
          src = '![x](/api/v1/images/1) <img src="/api/v1/images/2"/> ![](/api/v1/images/3 "t")'
          assert "/api/v1/images/" not in _sanitize_image_urls(src)
  ```

- [ ] Step 2: Run; expect AttributeError on import
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestSanitizeImageUrls -v`
  Expected: ImportError

- [ ] Step 3: Implement the sanitizer
  ```python
  # backend/app/services/export_service.py — module level, near top
  import re

  _MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(/api/v1/images/\d+(?:\s+"[^"]*")?\)')
  _HTML_IMG_RE = re.compile(
      r'<img\s+[^>]*src=["\']/api/v1/images/\d+["\'][^>]*?>',
      re.IGNORECASE,
  )
  _ALT_ATTR_RE = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)


  def _sanitize_image_urls(text: str) -> str:
      """Replace in-app image references with portable [Image: alt] placeholders.

      Targets two patterns (per spec FR-B5):
        1. Markdown image: ![alt](/api/v1/images/{id}) optionally with " title"
        2. HTML <img src="/api/v1/images/{id}" alt="...">
      Order matters; Markdown form is replaced before HTML form (regex 1 wouldn't
      match raw <img>, but applying in order keeps intent explicit).
      """
      def _md_repl(m: re.Match) -> str:
          alt = (m.group(1) or "").strip()
          return f"[Image: {alt}]" if alt else "[Image]"

      def _html_repl(m: re.Match) -> str:
          alt_match = _ALT_ATTR_RE.search(m.group(0))
          alt = (alt_match.group(1).strip() if alt_match else "")
          return f"[Image: {alt}]" if alt else "[Image]"

      out = _MD_IMG_RE.sub(_md_repl, text)
      out = _HTML_IMG_RE.sub(_html_repl, out)
      return out
  ```

- [ ] Step 4: Run tests; expect all pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestSanitizeImageUrls -v`
  Expected: 10 passed

- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/export_service.py backend/tests/unit/test_export_renderer.py
  git commit -m "feat(backend): add image-URL sanitizer for portable Markdown export"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/export_service.py` — no errors
- `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py -v` — 13 passed (3 from T2 + 10 from T3)

---

### T4: `_render_summary_markdown` — front matter + sections + emptiness tuple

**Goal:** Implement the core rendering pipeline producing `(body, is_empty)`. Front-matter shape, per-section emit with image sanitization, emptiness tracking. TOC and annotations land in T5/T6.
**Spec refs:** FR-B1, FR-B2, FR-B6 (steps 1-3, 5, 6 partial), FR-B10, FR-B11, FR-B12

**Files:**
- Modify: `backend/app/services/export_service.py` (add `_render_summary_markdown` method; replace markdown branch of `export_book`; remove markdown branch of `export_library`)
- Modify: `backend/tests/unit/test_export_renderer.py` (add a test class)

**Steps:**

- [ ] Step 1: Write failing tests for the renderer's front-matter + book-summary + sections + emptiness
  ```python
  # Append to backend/tests/unit/test_export_renderer.py
  from datetime import date

  def _book_data(title="Test Book", authors=None, summary=None, sections=None):
      return {
          "id": 1,
          "title": title,
          "authors": authors if authors is not None else ["Test Author"],
          "quick_summary": summary,
          "sections": sections or [],
          "annotations": [],  # section-scope; collected by _collect_book_data
      }

  class TestRenderSummaryMarkdownFrontMatter:
      def setup_method(self):
          # Inject a fake "today" by patching datetime in the module under test.
          # For simplicity, tests assert the body lines that precede the date and
          # parse the date line separately when needed.
          pass

      async def test_single_author_front_matter(self, async_session):
          # async_session: pytest fixture providing AsyncSession (existing in tests/conftest.py)
          svc = ExportService(async_session)
          body, is_empty = await svc._render_summary_markdown(
              _book_data(title="The Art of War", authors=["Sun Tzu"], summary=None),
              ExportSelection(),
          )
          assert body.startswith("# The Art of War\n")
          assert "**Author:** Sun Tzu" in body
          assert "**Authors:**" not in body
          assert "**Exported:** " in body
          # No book summary, no sections, no annotations -> is_empty=True
          assert is_empty is True

      async def test_multi_author(self, async_session):
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(authors=["A", "B", "C"]), ExportSelection()
          )
          assert "**Authors:** A, B, C" in body

      async def test_zero_authors(self, async_session):
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(authors=[]), ExportSelection()
          )
          assert "**Author:** Unknown" in body

      async def test_book_summary_renders_under_front_matter(self, async_session):
          svc = ExportService(async_session)
          body, is_empty = await svc._render_summary_markdown(
              _book_data(summary="The book is about strategy."),
              ExportSelection(),
          )
          assert "The book is about strategy." in body
          assert is_empty is False  # book summary block emitted

      async def test_book_summary_skipped_when_toggle_off(self, async_session):
          svc = ExportService(async_session)
          body, is_empty = await svc._render_summary_markdown(
              _book_data(summary="Strategy stuff"),
              ExportSelection(include_book_summary=False),
          )
          assert "Strategy stuff" not in body
          assert is_empty is True

      async def test_sections_render_with_h2(self, async_session):
          sections = [
              {"id": 10, "title": "Chapter 1", "order_index": 0, "depth": 0,
               "has_summary": True, "summary_md": "Chapter 1 content."},
              {"id": 11, "title": "Chapter 2", "order_index": 1, "depth": 0,
               "has_summary": True, "summary_md": "Chapter 2 content."},
          ]
          svc = ExportService(async_session)
          body, is_empty = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection()
          )
          assert "## Chapter 1" in body
          assert "## Chapter 2" in body
          assert "Chapter 1 content." in body
          assert "Chapter 2 content." in body
          assert is_empty is False

      async def test_sections_without_summary_skipped(self, async_session):
          sections = [
              {"id": 10, "title": "Pending", "order_index": 0, "depth": 0,
               "has_summary": False, "summary_md": None},
              {"id": 11, "title": "Done", "order_index": 1, "depth": 0,
               "has_summary": True, "summary_md": "Real content."},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection()
          )
          assert "## Pending" not in body
          assert "## Done" in body

      async def test_excluded_section_skipped(self, async_session):
          sections = [
              {"id": 10, "title": "Keep", "order_index": 0, "depth": 0,
               "has_summary": True, "summary_md": "K"},
              {"id": 11, "title": "Drop", "order_index": 1, "depth": 0,
               "has_summary": True, "summary_md": "D"},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections),
              ExportSelection(exclude_section_ids=frozenset({11})),
          )
          assert "## Keep" in body
          assert "## Drop" not in body

      async def test_image_sanitization_applies_to_section_summary(self, async_session):
          sections = [
              {"id": 10, "title": "Ch", "order_index": 0, "depth": 0,
               "has_summary": True,
               "summary_md": "See ![figure](/api/v1/images/3) below."},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection()
          )
          assert "[Image: figure]" in body
          assert "/api/v1/images/" not in body

      async def test_image_sanitization_applies_to_book_summary(self, async_session):
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(summary='Chart ![alt](/api/v1/images/9) is here.'),
              ExportSelection(),
          )
          assert "[Image: alt]" in body
          assert "/api/v1/images/" not in body

      async def test_emptiness_tuple_invariant(self, async_session):
          # All toggles off, no content -> is_empty=True
          svc = ExportService(async_session)
          _, is_empty = await svc._render_summary_markdown(
              _book_data(summary="x", sections=[
                  {"id": 1, "title": "S", "order_index": 0, "depth": 0,
                   "has_summary": True, "summary_md": "y"}
              ]),
              ExportSelection(
                  include_book_summary=False,
                  include_toc=False,
                  include_annotations=False,
                  exclude_section_ids=frozenset({1}),
              ),
          )
          assert is_empty is True
  ```

- [ ] Step 2: Verify a `async_session` fixture exists; if not, add it
  Run: `cd backend && grep -rn "async_session\|@pytest.fixture" tests/conftest.py tests/unit/conftest.py 2>/dev/null | head -10`
  If `async_session` fixture doesn't exist in `tests/conftest.py`, add to `backend/tests/conftest.py`:
  ```python
  import pytest_asyncio
  from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
  from app.db.models import Base

  @pytest_asyncio.fixture
  async def async_session():
      engine = create_async_engine("sqlite+aiosqlite:///:memory:")
      async with engine.begin() as conn:
          await conn.run_sync(Base.metadata.create_all)
      Session = async_sessionmaker(engine, expire_on_commit=False)
      async with Session() as s:
          yield s
      await engine.dispose()
  ```
  And mark the new test class methods with `@pytest.mark.asyncio`.

- [ ] Step 3: Run new tests; expect all to fail
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestRenderSummaryMarkdownFrontMatter -v`
  Expected: 10 failures (method `_render_summary_markdown` not yet defined)

- [ ] Step 4: Implement `_render_summary_markdown` core path (front matter + sections + image sanitization + emptiness flags); leave TOC + annotations as no-ops returning empty
  ```python
  # backend/app/services/export_service.py — new method on ExportService
  from datetime import date as _date

  async def _render_summary_markdown(
      self, book_data: dict, selection: ExportSelection
  ) -> tuple[str, bool]:
      """Render the new summaries-focused Markdown shape.

      Returns (body, is_empty) where is_empty reflects whether ANY of the four
      block types (TOC, book-summary, per-section, notes-footer) was emitted.
      Per spec FR-A6: do NOT text-grep body to detect emptiness.
      """
      toc_emitted = False
      book_summary_emitted = False
      any_section_emitted = False
      notes_emitted = False
      lines: list[str] = []

      # Front matter (always)
      lines.append(f"# {book_data['title']}")
      authors = book_data.get("authors") or []
      if not authors:
          lines.append("**Author:** Unknown")
      elif len(authors) == 1:
          lines.append(f"**Author:** {authors[0]}")
      else:
          lines.append(f"**Authors:** {', '.join(authors)}")
      lines.append(f"**Exported:** {_date.today().isoformat()}")
      lines.append("")

      # Filter & sort sections that will render
      rendered_sections = sorted(
          [
              s for s in (book_data.get("sections") or [])
              if s.get("has_summary")
              and s.get("summary_md")
              and s["id"] not in selection.exclude_section_ids
          ],
          key=lambda s: s["order_index"],
      )

      # TOC: deferred to T5

      # Book summary
      summary = book_data.get("quick_summary")
      if selection.include_book_summary and summary:
          lines.append(_sanitize_image_urls(summary))
          lines.append("")
          book_summary_emitted = True

      # Sections
      for s in rendered_sections:
          lines.append(f"## {s['title']}")
          lines.append(_sanitize_image_urls(s["summary_md"]))
          lines.append("")
          any_section_emitted = True
          # Highlights: deferred to T6

      # Notes footer: deferred to T6

      body = "\n".join(lines)
      is_empty = not (
          toc_emitted or book_summary_emitted or any_section_emitted or notes_emitted
      )
      return body, is_empty
  ```

- [ ] Step 5: Replace markdown branch of `export_book` to use the new renderer (the route handler reads the tuple separately; for backward compat, this method returns the body string)
  ```python
  # In ExportService.export_book — replace the "markdown" branch
  if fmt == "json":
      content = self._render_json([book_data])
  elif fmt == "markdown":
      body, _is_empty = await self._render_summary_markdown(
          book_data, ExportSelection()
      )
      content = body
  else:
      raise ExportError(f"Unsupported format: {fmt}. Use 'json' or 'markdown'.")
  ```
  ```python
  # In ExportService.export_library — remove the "markdown" branch entirely
  if fmt == "json":
      content = self._render_json(all_data)
  else:
      raise ExportError(
          "Library Markdown export was removed in v1.6 — use --format json "
          "for full-library backups, or run 'export book' per book."
      )
  ```

- [ ] Step 6: Run tests; expect all to pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py -v`
  Expected: 23 passed (3 from T2 + 10 from T3 + 10 from T4)

- [ ] Step 7: Verify the existing `test_export_book_markdown_has_sections` integration test still passes (the new shape still emits `## ` headings)
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py::test_export_book_markdown_has_sections -v`
  Expected: 1 passed (note: it may skip if no books in DB, which is also acceptable)

- [ ] Step 8: Commit
  ```bash
  git add backend/app/services/export_service.py backend/tests/unit/test_export_renderer.py backend/tests/conftest.py
  git commit -m "feat(backend): add _render_summary_markdown core (front matter + sections + sanitization)"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/export_service.py tests/unit/test_export_renderer.py` — no errors
- `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py -v` — 23 passed

---

### T5: `_render_summary_markdown` — TOC + slug disambiguation table

**Goal:** Render anchored TOC bullets that match GFM viewer auto-anchors. Empty-slug fallback to `section-{order_index:03d}`. Disambiguation: bare slug, then `-1`, `-2`, … per encounter order.
**Spec refs:** FR-B6 step 4, FR-B7

**Files:**
- Modify: `backend/app/services/export_service.py` (extend `_render_summary_markdown`)
- Modify: `backend/tests/unit/test_export_renderer.py` (add test class)

**Steps:**

- [ ] Step 1: Write failing TOC tests
  ```python
  # Append to backend/tests/unit/test_export_renderer.py
  class TestRenderSummaryMarkdownTOC:
      @pytest.mark.asyncio
      async def test_toc_emitted_with_anchors(self, async_session):
          sections = [
              {"id": 1, "title": "Chapter 1", "order_index": 0, "depth": 0,
               "has_summary": True, "summary_md": "x"},
              {"id": 2, "title": "Chapter 2", "order_index": 1, "depth": 0,
               "has_summary": True, "summary_md": "y"},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection()
          )
          assert "## Table of Contents" in body
          assert "- [Chapter 1](#chapter-1)" in body
          assert "- [Chapter 2](#chapter-2)" in body

      @pytest.mark.asyncio
      async def test_toc_indents_by_depth(self, async_session):
          sections = [
              {"id": 1, "title": "Part 1", "order_index": 0, "depth": 0,
               "has_summary": True, "summary_md": "a"},
              {"id": 2, "title": "Sub", "order_index": 1, "depth": 1,
               "has_summary": True, "summary_md": "b"},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection()
          )
          assert "- [Part 1](#part-1)" in body
          assert "  - [Sub](#sub)" in body  # 2-space indent for depth 1

      @pytest.mark.asyncio
      async def test_toc_omitted_when_no_sections_render(self, async_session):
          # No sections at all
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(), ExportSelection()
          )
          assert "## Table of Contents" not in body

      @pytest.mark.asyncio
      async def test_toc_omitted_when_toggle_off(self, async_session):
          sections = [
              {"id": 1, "title": "Chapter 1", "order_index": 0, "depth": 0,
               "has_summary": True, "summary_md": "x"},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection(include_toc=False)
          )
          assert "## Table of Contents" not in body
          assert "## Chapter 1" in body  # but section still renders

      @pytest.mark.asyncio
      async def test_duplicate_titles_disambiguate_with_dash_n(self, async_session):
          # GFM convention: first=bare, second=-1, third=-2 (NOT -2/-3)
          sections = [
              {"id": 1, "title": "Intro", "order_index": 0, "depth": 0,
               "has_summary": True, "summary_md": "a"},
              {"id": 2, "title": "Intro", "order_index": 1, "depth": 0,
               "has_summary": True, "summary_md": "b"},
              {"id": 3, "title": "Intro", "order_index": 2, "depth": 0,
               "has_summary": True, "summary_md": "c"},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection()
          )
          assert "(#intro)" in body
          assert "(#intro-1)" in body
          assert "(#intro-2)" in body

      @pytest.mark.asyncio
      async def test_empty_slug_falls_back_to_section_orderindex(self, async_session):
          # Spec G2: emoji-only title -> section-{order_index:03d}
          sections = [
              {"id": 1, "title": "🚀🎯", "order_index": 7, "depth": 0,
               "has_summary": True, "summary_md": "a"},
          ]
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=sections), ExportSelection()
          )
          assert "[🚀🎯](#section-007)" in body

      @pytest.mark.asyncio
      async def test_toc_emitted_flag_drives_emptiness(self, async_session):
          # toc_emitted alone makes is_empty=False
          sections = [
              {"id": 1, "title": "Ch", "order_index": 0, "depth": 0,
               "has_summary": True, "summary_md": "a"},
          ]
          svc = ExportService(async_session)
          _, is_empty = await svc._render_summary_markdown(
              _book_data(sections=sections),
              ExportSelection(include_book_summary=False, include_annotations=False),
          )
          # TOC + section both emitted -> not empty
          assert is_empty is False
  ```

- [ ] Step 2: Run; expect failures
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestRenderSummaryMarkdownTOC -v`
  Expected: 7 failures (TOC not yet implemented)

- [ ] Step 3: Implement TOC + slug-disambiguation in `_render_summary_markdown`
  Insert before the "Book summary" block:
  ```python
  # Build slug-disambiguation table over rendered_sections (single deterministic pass)
  from app.services.slug import gfm_slug
  slug_table: dict[int, str] = {}
  slug_counter: dict[str, int] = {}
  for s in rendered_sections:
      base = gfm_slug(s["title"]) or f"section-{s['order_index']:03d}"
      n = slug_counter.get(base, 0)
      slug_table[s["id"]] = base if n == 0 else f"{base}-{n}"
      slug_counter[base] = n + 1

  # TOC (only if toggle ON and at least one section will render)
  if selection.include_toc and rendered_sections:
      lines.append("## Table of Contents")
      for s in rendered_sections:
          indent = "  " * (s.get("depth", 0) or 0)
          lines.append(f"{indent}- [{s['title']}](#{slug_table[s['id']]})")
      lines.append("")
      toc_emitted = True
  ```

- [ ] Step 4: Run TOC tests; expect all pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestRenderSummaryMarkdownTOC -v`
  Expected: 7 passed

- [ ] Step 5: Run full renderer test suite; ensure no regressions
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py -v`
  Expected: 30 passed (3 + 10 + 10 + 7)

- [ ] Step 6: Commit
  ```bash
  git add backend/app/services/export_service.py backend/tests/unit/test_export_renderer.py
  git commit -m "feat(backend): add anchored TOC + GFM slug disambiguation to summary export"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py -v` — 30 passed

---

### T6: `_render_summary_markdown` — Highlights + Notes + escaping

**Goal:** Per-section `### Highlights` block from section-scope annotations; final `## Notes` footer from book-scope annotations. Cascade rule. Block-level markdown trigger escaping.
**Spec refs:** FR-B8, FR-B9

**Files:**
- Modify: `backend/app/services/export_service.py` (add escape helper + extend renderer; wire `_collect_book_annotations` into `export_book`)
- Modify: `backend/tests/unit/test_export_renderer.py`

**Steps:**

- [ ] Step 1: Write failing tests for highlights + notes + escaping
  ```python
  # Append to backend/tests/unit/test_export_renderer.py
  class TestRenderSummaryMarkdownAnnotations:
      def _section(self, id_, anns):
          return {"id": id_, "title": f"S{id_}", "order_index": id_, "depth": 0,
                  "has_summary": True, "summary_md": "body"}

      @pytest.mark.asyncio
      async def test_section_highlight_with_note(self, async_session):
          # section-scope annotations come from book_data["annotations"]
          ann = {"id": 1, "content_type": "section_summary", "content_id": 1,
                 "selected_text": "famous quote", "note": "interesting", "type": "highlight"}
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[self._section(1, [])]) | {"annotations": [ann]},
              ExportSelection(),
          )
          assert "### Highlights" in body
          assert "> famous quote" in body
          assert "> — Note: interesting" in body

      @pytest.mark.asyncio
      async def test_section_highlight_no_note(self, async_session):
          ann = {"id": 1, "content_type": "section_summary", "content_id": 1,
                 "selected_text": "just a passage", "note": "", "type": "highlight"}
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[self._section(1, [])]) | {"annotations": [ann]},
              ExportSelection(),
          )
          assert "> just a passage" in body
          assert "Note:" not in body

      @pytest.mark.asyncio
      async def test_section_annotation_empty_selected_text_skipped(self, async_session):
          # Defensive — section-scope with empty selected_text -> silently skipped
          ann = {"id": 1, "content_type": "section_summary", "content_id": 1,
                 "selected_text": "", "note": "stray note", "type": "note"}
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[self._section(1, [])]) | {"annotations": [ann]},
              ExportSelection(),
          )
          assert "### Highlights" not in body
          assert "stray note" not in body

      @pytest.mark.asyncio
      async def test_annotations_toggle_off(self, async_session):
          ann = {"id": 1, "content_type": "section_summary", "content_id": 1,
                 "selected_text": "x", "note": "y", "type": "highlight"}
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[self._section(1, [])]) | {"annotations": [ann]},
              ExportSelection(include_annotations=False),
          )
          assert "### Highlights" not in body

      @pytest.mark.asyncio
      async def test_excluded_section_drops_its_annotations(self, async_session):
          ann = {"id": 1, "content_type": "section_summary", "content_id": 5,
                 "selected_text": "should not appear", "note": "", "type": "highlight"}
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[
                  self._section(1, []),
                  {"id": 5, "title": "S5", "order_index": 5, "depth": 0,
                   "has_summary": True, "summary_md": "x"},
              ]) | {"annotations": [ann]},
              ExportSelection(exclude_section_ids=frozenset({5})),
          )
          assert "should not appear" not in body

      @pytest.mark.asyncio
      async def test_book_scope_note_in_notes_footer(self, async_session):
          # book_data carries section-scope annotations only; book-scope come via
          # a separate kwarg (the renderer accepts them in addition).
          # See implementation step for the parameter shape.
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(),
              ExportSelection(),
              book_annotations=[{"id": 1, "selected_text": "", "note": "freeform reader note", "type": "note"}],
          )
          assert "## Notes" in body
          assert "- freeform reader note" in body

      @pytest.mark.asyncio
      async def test_book_scope_highlight_with_and_without_note(self, async_session):
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(),
              ExportSelection(),
              book_annotations=[
                  {"id": 1, "selected_text": "great quote", "note": "with note", "type": "highlight"},
                  {"id": 2, "selected_text": "lone quote", "note": "", "type": "highlight"},
              ],
          )
          assert '- > "great quote"' in body
          assert "  — with note" in body
          assert '- > "lone quote"' in body

      @pytest.mark.asyncio
      async def test_notes_footer_omitted_when_no_book_anns(self, async_session):
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(), ExportSelection(), book_annotations=[]
          )
          assert "## Notes" not in body

      @pytest.mark.asyncio
      async def test_book_anns_survive_section_exclusion(self, async_session):
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[
                  {"id": 1, "title": "S1", "order_index": 0, "depth": 0,
                   "has_summary": True, "summary_md": "a"},
              ]),
              ExportSelection(exclude_section_ids=frozenset({1})),
              book_annotations=[{"id": 1, "selected_text": "", "note": "kept",
                                 "type": "note"}],
          )
          assert "kept" in body  # cascade does NOT apply to book-scope notes

      @pytest.mark.asyncio
      async def test_newlines_in_selected_text_collapse_to_space(self, async_session):
          ann = {"id": 1, "content_type": "section_summary", "content_id": 1,
                 "selected_text": "line1\nline2", "note": "", "type": "highlight"}
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[
                  {"id": 1, "title": "S", "order_index": 0, "depth": 0,
                   "has_summary": True, "summary_md": "x"},
              ]) | {"annotations": [ann]},
              ExportSelection(),
          )
          assert "> line1 line2" in body
          assert "> line1\nline2" not in body

      @pytest.mark.asyncio
      async def test_block_level_chars_escaped(self, async_session):
          # FR-B8: leading >, #, -, *, +, "1." escaped with backslash
          ann = {"id": 1, "content_type": "section_summary", "content_id": 1,
                 "selected_text": "> nested quote attempt", "note": "# heading attempt",
                 "type": "highlight"}
          svc = ExportService(async_session)
          body, _ = await svc._render_summary_markdown(
              _book_data(sections=[
                  {"id": 1, "title": "S", "order_index": 0, "depth": 0,
                   "has_summary": True, "summary_md": "x"},
              ]) | {"annotations": [ann]},
              ExportSelection(),
          )
          # selected_text starts with '>' AFTER blockquote prefix '> '
          assert r"> \> nested quote attempt" in body
          # note in continuation line — '# heading' must be escaped
          assert r"\# heading attempt" in body

      @pytest.mark.asyncio
      async def test_emptiness_with_only_book_notes(self, async_session):
          svc = ExportService(async_session)
          _, is_empty = await svc._render_summary_markdown(
              _book_data(),
              ExportSelection(include_book_summary=False, include_toc=False),
              book_annotations=[{"id": 1, "selected_text": "", "note": "x",
                                 "type": "note"}],
          )
          # Notes footer alone is enough to flip is_empty
          assert is_empty is False
  ```

- [ ] Step 2: Run; expect failures
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py::TestRenderSummaryMarkdownAnnotations -v`
  Expected: 12 failures

- [ ] Step 3: Implement escape helper + extend renderer signature with `book_annotations: list[dict] | None = None` + add the highlights and notes blocks
  ```python
  # backend/app/services/export_service.py — module level
  _BLOCK_TRIGGER_RE = re.compile(r'^(\s*)([>#\-*+]|\d+\.)', re.MULTILINE)


  def _escape_block_triggers(text: str) -> str:
      """Escape leading block-level markdown triggers in any line.

      FR-B8: Prevent annotation content from breaking out of its blockquote/bullet.
      Newlines collapse to a single space first.
      """
      collapsed = text.replace("\r\n", " ").replace("\n", " ")
      # Now there are no newlines — but the block-trigger rule applies to the
      # rendered position. Caller is responsible for escaping at insertion sites.
      return collapsed


  def _escape_at_line_start(s: str) -> str:
      """Escape if the string begins with a block-level markdown trigger."""
      return re.sub(r'^(\s*)([>#\-*+]|\d+\.)', r'\1\\\2', s)
  ```

  Extend `_render_summary_markdown` signature and body:
  ```python
  async def _render_summary_markdown(
      self,
      book_data: dict,
      selection: ExportSelection,
      book_annotations: list[dict] | None = None,
  ) -> tuple[str, bool]:
      # ... front matter, slug table, TOC, book summary unchanged ...

      # Sections + per-section highlights
      for s in rendered_sections:
          lines.append(f"## {s['title']}")
          lines.append(_sanitize_image_urls(s["summary_md"]))
          lines.append("")

          if selection.include_annotations:
              section_anns = [
                  a for a in (book_data.get("annotations") or [])
                  if a.get("content_type") in ("section_content", "section_summary")
                  and a.get("content_id") == s["id"]
                  and (a.get("selected_text") or "").strip()
              ]
              if section_anns:
                  lines.append("### Highlights")
                  for a in section_anns:
                      sel = _escape_block_triggers(a.get("selected_text") or "")
                      sel = _escape_at_line_start(sel)
                      lines.append(f"> {sel}")
                      note = (a.get("note") or "").strip()
                      if note:
                          note = _escape_block_triggers(note)
                          note = _escape_at_line_start(note)
                          lines.append(f"> — Note: {note}")
                      lines.append("")
          any_section_emitted = True

      # Notes footer
      if selection.include_annotations and book_annotations:
          rendered_notes: list[str] = []
          for a in book_annotations:
              sel = (a.get("selected_text") or "").strip()
              note = (a.get("note") or "").strip()
              if sel and note:
                  sel_e = _escape_at_line_start(_escape_block_triggers(sel))
                  note_e = _escape_at_line_start(_escape_block_triggers(note))
                  rendered_notes.append(f'- > "{sel_e}"\n  — {note_e}')
              elif note:
                  note_e = _escape_at_line_start(_escape_block_triggers(note))
                  rendered_notes.append(f"- {note_e}")
              elif sel:
                  sel_e = _escape_at_line_start(_escape_block_triggers(sel))
                  rendered_notes.append(f'- > "{sel_e}"')
              # both empty -> silently skip
          if rendered_notes:
              lines.append("## Notes")
              lines.extend(rendered_notes)
              lines.append("")
              notes_emitted = True

      body = "\n".join(lines)
      is_empty = not (
          toc_emitted or book_summary_emitted or any_section_emitted or notes_emitted
      )
      return body, is_empty
  ```

- [ ] Step 4: Wire `book_annotations` into `export_book` so service callers don't need to know
  ```python
  # In ExportService.export_book — markdown branch
  elif fmt == "markdown":
      book_anns = await self._collect_book_annotations(book)
      body, _is_empty = await self._render_summary_markdown(
          book_data, ExportSelection(), book_annotations=book_anns
      )
      content = body
  ```

- [ ] Step 4b: Add a public orchestrator method on `ExportService` so route + CLI share one call site
  ```python
  # backend/app/services/export_service.py — new public method on ExportService
  async def export_book_markdown(
      self, book_id: int, selection: ExportSelection
  ) -> tuple[str, bool]:
      """Public orchestrator for the new Markdown shape.

      Single call site for HTTP route handler AND CLI command — eliminates
      duplication of the (collect → collect_book_annotations → render) sequence.
      Returns (body, is_empty) so callers can set the X-Empty-Export header.

      Raises ExportError when book is not found (callers translate to 404).
      """
      book = await self.book_repo.get_by_id(book_id)
      if not book:
          raise ExportError(f"Book {book_id} not found.")
      book_data = await self._collect_book_data(book)
      book_anns = await self._collect_book_annotations(book)
      return await self._render_summary_markdown(
          book_data, selection, book_annotations=book_anns
      )
  ```
  Add a unit test:
  ```python
  # Append to backend/tests/unit/test_export_renderer.py
  class TestExportBookMarkdownPublic:
      @pytest.mark.asyncio
      async def test_returns_body_and_is_empty(self, async_session):
          # Seed minimal book
          from app.db.models import Book, BookStatus
          book = Book(
              title="Pub Test", file_data=b"", file_hash="pub-hash",
              file_format="epub", file_size_bytes=0, status=BookStatus.COMPLETED,
          )
          async_session.add(book)
          await async_session.commit()
          svc = ExportService(async_session)
          body, is_empty = await svc.export_book_markdown(book.id, ExportSelection())
          assert body.startswith("# Pub Test\n")
          assert is_empty is True  # no summaries, no annotations

      @pytest.mark.asyncio
      async def test_raises_export_error_for_missing_book(self, async_session):
          from app.services.export_service import ExportError
          svc = ExportService(async_session)
          with pytest.raises(ExportError, match="not found"):
              await svc.export_book_markdown(99999, ExportSelection())
  ```

- [ ] Step 5: Run all renderer tests
  Run: `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py -v`
  Expected: 44 passed (30 + 12 + 2)

- [ ] Step 6: Verify the existing JSON test still passes
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py -v`
  Expected: `test_export_library_markdown` FAILS (the assertion `"# Book Companion Library Export" in resp.text` is no longer true — service now raises `ExportError`); other tests pass. This is expected and will be fixed in T7.

- [ ] Step 7: Commit
  ```bash
  git add backend/app/services/export_service.py backend/tests/unit/test_export_renderer.py
  git commit -m "feat(backend): add per-section highlights and book-scope Notes footer with escaping"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/export_service.py` — no errors
- `cd backend && uv run python -m pytest tests/unit/test_export_renderer.py -v` — 42 passed

---

### T7: API route extension — selection params + headers + 400 + library 410

**Goal:** Extend `GET /api/v1/export/book/{id}` with selection querystring + slug filename + `Cache-Control` + `X-Empty-Export` headers + 400 on invalid `exclude_section`. Replace library-Markdown branch with 410 Gone.
**Spec refs:** FR-A1, FR-A2, FR-A3, FR-A4, FR-A5, FR-A6

**Files:**
- Modify: `backend/app/api/routes/export.py`
- Modify: `backend/tests/integration/test_api/test_export_api.py` (update `test_export_library_markdown`)
- Create: `backend/tests/integration/test_api/test_export_book_markdown.py`

**Steps:**

- [ ] Step 1: Update existing test for the deprecated library Markdown route
  ```python
  # Modify backend/tests/integration/test_api/test_export_api.py
  # Replace test_export_library_markdown body with:
  @pytest.mark.asyncio
  async def test_export_library_markdown_returns_410(client):
      """Library Markdown export was removed in v1.6 — returns 410 Gone."""
      resp = await client.get("/api/v1/export/library?format=markdown")
      assert resp.status_code == 410
      body = resp.json()
      assert "removed in v1.6" in body["detail"]
      assert "format=json" in body["detail"]
  ```

- [ ] Step 2: Write new test file for the extended GET book route
  ```python
  # Create backend/tests/integration/test_api/test_export_book_markdown.py
  import pytest
  from datetime import date

  pytestmark = pytest.mark.asyncio


  async def _seed_book_with_summary(client, async_session):
      """Helper: insert a Book + Author + BookSection + Summary via repos.
      Returns (book_id, section_id)."""
      from app.db.models import (
          Book, BookStatus, Author, BookAuthor, BookSection,
          Summary, SummaryContentType,
      )
      book = Book(
          title="Test Export Book",
          file_data=b"",
          file_hash="hash-export-test",
          file_format="epub",
          file_size_bytes=0,
          status=BookStatus.COMPLETED,
      )
      async_session.add(book)
      await async_session.flush()
      author = Author(name="Test Author")
      async_session.add(author)
      await async_session.flush()
      async_session.add(BookAuthor(book_id=book.id, author_id=author.id, order_index=0))
      section = BookSection(
          book_id=book.id, title="Chapter 1", order_index=0, depth=0,
          content_md="content", section_type="chapter",
      )
      async_session.add(section)
      await async_session.flush()
      sec_summary = Summary(
          content_type=SummaryContentType.SECTION,
          content_id=section.id, book_id=book.id,
          preset_name="test", summary_md="Section 1 summary content.",
      )
      async_session.add(sec_summary)
      await async_session.flush()
      section.default_summary_id = sec_summary.id
      await async_session.commit()
      return book.id, section.id


  async def test_filename_uses_slug(client, async_session):
      bid, _ = await _seed_book_with_summary(client, async_session)
      resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown")
      assert resp.status_code == 200
      cd = resp.headers["content-disposition"]
      today = date.today().strftime("%Y%m%d")
      assert f"test-export-book-summary-{today}.md" in cd

  async def test_cache_control_set(client, async_session):
      bid, _ = await _seed_book_with_summary(client, async_session)
      resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown")
      assert resp.headers.get("cache-control") == "private, max-age=0"

  async def test_x_empty_export_false_when_content(client, async_session):
      bid, _ = await _seed_book_with_summary(client, async_session)
      resp = await client.get(f"/api/v1/export/book/{bid}?format=markdown")
      # X-Empty-Export header omitted OR set to "false" when content exists
      assert resp.headers.get("x-empty-export", "false") == "false"

  async def test_x_empty_export_true_when_all_excluded(client, async_session):
      bid, sid = await _seed_book_with_summary(client, async_session)
      resp = await client.get(
          f"/api/v1/export/book/{bid}"
          f"?format=markdown"
          f"&include_book_summary=false"
          f"&include_toc=false"
          f"&include_annotations=false"
          f"&exclude_section={sid}"
      )
      assert resp.status_code == 200
      assert resp.headers.get("x-empty-export") == "true"

  async def test_invalid_exclude_section_returns_400(client, async_session):
      bid, _ = await _seed_book_with_summary(client, async_session)
      resp = await client.get(
          f"/api/v1/export/book/{bid}?format=markdown&exclude_section=99999"
      )
      assert resp.status_code == 400
      detail = resp.json()["detail"]
      assert "99999" in detail
      assert "does not belong to" in detail

  async def test_selection_querystring_filters_output(client, async_session):
      bid, _ = await _seed_book_with_summary(client, async_session)
      # No-toc -> no Table of Contents
      resp = await client.get(
          f"/api/v1/export/book/{bid}?format=markdown&include_toc=false"
      )
      assert resp.status_code == 200
      assert "## Table of Contents" not in resp.text

  async def test_json_format_unchanged_byte_equal(client, async_session):
      """G6: existing JSON export shape unaffected by selection params."""
      bid, _ = await _seed_book_with_summary(client, async_session)
      resp_a = await client.get(f"/api/v1/export/book/{bid}?format=json")
      resp_b = await client.get(
          f"/api/v1/export/book/{bid}?format=json&include_toc=false&exclude_section=99999"
      )
      assert resp_a.status_code == 200 and resp_b.status_code == 200
      # Selection params silently ignored on JSON
      assert resp_a.text == resp_b.text

  async def test_slug_falls_back_for_cjk_only_title(client, async_session):
      # Re-seed with a CJK-only title
      from app.db.models import Book, BookStatus
      book = Book(
          title="北京概要",
          file_data=b"",
          file_hash="hash-cjk-export",
          file_format="epub",
          file_size_bytes=0,
          status=BookStatus.COMPLETED,
      )
      async_session.add(book)
      await async_session.commit()
      resp = await client.get(f"/api/v1/export/book/{book.id}?format=markdown")
      cd = resp.headers["content-disposition"]
      today = date.today().strftime("%Y%m%d")
      assert f"book-{book.id}-summary-{today}.md" in cd

  async def test_image_urls_never_survive(client, async_session):
      """G4: zero `/api/v1/images/` substrings in any exported markdown."""
      from app.db.models import Book, BookStatus, BookSection, Summary, SummaryContentType
      book = Book(
          title="Imagey", file_data=b"", file_hash="hash-img",
          file_format="epub", file_size_bytes=0, status=BookStatus.COMPLETED,
      )
      async_session.add(book)
      await async_session.flush()
      sec = BookSection(book_id=book.id, title="C", order_index=0, depth=0,
                        content_md="x", section_type="chapter")
      async_session.add(sec)
      await async_session.flush()
      summ = Summary(
          content_type=SummaryContentType.SECTION, content_id=sec.id,
          book_id=book.id, preset_name="t",
          summary_md="See ![figure](/api/v1/images/3) and <img src=\"/api/v1/images/4\" />.",
      )
      async_session.add(summ)
      await async_session.flush()
      sec.default_summary_id = summ.id
      await async_session.commit()
      resp = await client.get(f"/api/v1/export/book/{book.id}?format=markdown")
      assert resp.status_code == 200
      assert "/api/v1/images/" not in resp.text
      assert "[Image: figure]" in resp.text
  ```

- [ ] Step 3: Run; expect failures (route doesn't yet honor selection / headers / 400 / 410)
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_export_book_markdown.py tests/integration/test_api/test_export_api.py::test_export_library_markdown_returns_410 -v`
  Expected: most fail

- [ ] Step 4: Implement the new route handler
  ```python
  # backend/app/api/routes/export.py — replace existing handler bodies
  from datetime import date
  from app.services.export_service import ExportSelection
  from app.services.slug import filename_slug
  from app.db.models import BookSection
  from sqlalchemy import select


  @router.get("/book/{book_id}")
  async def export_book(
      book_id: int,
      format: str = Query("json", pattern="^(json|markdown)$"),
      include_book_summary: bool = Query(True),
      include_toc: bool = Query(True),
      include_annotations: bool = Query(True),
      exclude_section: list[int] = Query(default_factory=list),
      export_service: ExportService = Depends(get_export_service),
  ):
      try:
          book = await export_service.book_repo.get_by_id(book_id)
          if not book:
              raise HTTPException(status_code=404, detail=f"Book {book_id} not found.")

          if format == "json":
              # JSON path unchanged. Selection params silently ignored.
              content = await export_service.export_book(book_id, fmt="json")
              return JSONResponse(
                  content=json.loads(content),
                  headers={
                      "Content-Disposition": f'attachment; filename="book_{book_id}.json"'
                  },
              )

          # Markdown path
          # Validate exclude_section IDs belong to this book
          if exclude_section:
              result = await export_service.session.execute(
                  select(BookSection.id).where(BookSection.book_id == book_id)
              )
              valid_ids = {row[0] for row in result.all()}
              invalid = [sid for sid in exclude_section if sid not in valid_ids]
              if invalid:
                  raise HTTPException(
                      status_code=400,
                      detail=f"section {invalid[0]} does not belong to book {book_id}",
                  )

          selection = ExportSelection(
              include_book_summary=include_book_summary,
              include_toc=include_toc,
              include_annotations=include_annotations,
              exclude_section_ids=frozenset(exclude_section),
          )
          # Single call site shared with CLI (T9)
          body, is_empty = await export_service.export_book_markdown(book_id, selection)

          slug = filename_slug(book.title) or f"book-{book_id}"
          today = date.today().strftime("%Y%m%d")
          filename = f"{slug}-summary-{today}.md"

          headers = {
              "Content-Disposition": f'attachment; filename="{filename}"',
              "Cache-Control": "private, max-age=0",
              "X-Empty-Export": "true" if is_empty else "false",
          }
          return PlainTextResponse(body, media_type="text/markdown", headers=headers)
      except ExportError as e:
          raise HTTPException(status_code=404, detail=str(e)) from None


  @router.get("/library")
  async def export_library(
      format: str = Query("json", pattern="^(json|markdown)$"),
      export_service: ExportService = Depends(get_export_service),
  ):
      if format == "markdown":
          raise HTTPException(
              status_code=410,
              detail=(
                  "Library Markdown export was removed in v1.6 — use format=json "
                  "for full-library backups, or use /api/v1/export/book/{id}"
                  "?format=markdown per book."
              ),
          )
      content = await export_service.export_library(fmt="json")
      return JSONResponse(
          content=json.loads(content),
          headers={
              "Content-Disposition": "attachment; filename=library_export.json"
          },
      )
  ```

- [ ] Step 5: Run all integration tests; ensure new pass + old library-markdown is now 410
  Run: `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py tests/integration/test_api/test_export_book_markdown.py -v`
  Expected: all pass; the previously-failing `test_export_book_markdown_has_sections` may need the seed helper used in other tests — verify it skips cleanly when no books are seeded.

- [ ] Step 6: Run the full backend test suite — ensure nothing else regressed
  Run: `cd backend && uv run python -m pytest tests/ -x --ignore=tests/e2e 2>&1 | tail -20`
  Expected: all pass (or only known-skip tests)

- [ ] Step 7: Commit
  ```bash
  git add backend/app/api/routes/export.py backend/tests/integration/test_api/test_export_api.py backend/tests/integration/test_api/test_export_book_markdown.py
  git commit -m "feat(api): extend book export with selection params + slug filename + 410 library markdown"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/api/routes/export.py tests/integration/test_api/` — no errors
- `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py tests/integration/test_api/test_export_book_markdown.py -v` — all pass

---

### T9: CLI — book flags + help text + strict --format json combo error + library exit 2

**Goal:** Extend `bookcompanion export book` with four flags + grouped help text + flag-combination guard against `--format json`. Also handle the library subcommand: `--format markdown` exits 2 with the v1.6 deprecation message.
**Spec refs:** FR-C1, FR-C2, FR-C3, FR-C4, FR-C5, FR-C6

**Files:**
- Modify: `backend/app/cli/commands/export_cmd.py`
- Create: `backend/tests/e2e/test_export_cli.py`

**Steps:**

- [ ] Step 1: Write failing CLI tests using Typer's `CliRunner`
  ```python
  # Create backend/tests/e2e/test_export_cli.py
  import pytest
  from typer.testing import CliRunner
  from app.cli.main import app

  runner = CliRunner()

  pytestmark = pytest.mark.asyncio


  def test_help_lists_new_flags():
      result = runner.invoke(app, ["export", "book", "--help"])
      assert result.exit_code == 0
      assert "--no-book-summary" in result.stdout
      assert "--no-toc" in result.stdout
      assert "--no-annotations" in result.stdout
      assert "--exclude-section" in result.stdout
      assert "Flags only valid with --format markdown" in result.stdout

  def test_format_json_with_no_toc_exits_2():
      result = runner.invoke(app, ["export", "book", "1", "--format", "json", "--no-toc"])
      assert result.exit_code == 2
      assert "only valid with --format markdown" in (result.stdout + result.stderr)

  def test_format_json_with_exclude_section_exits_2():
      result = runner.invoke(app, ["export", "book", "1", "--format", "json", "--exclude-section", "5"])
      assert result.exit_code == 2

  def test_library_markdown_subcommand_exits_2():
      result = runner.invoke(app, ["export", "library", "--format", "markdown"])
      assert result.exit_code == 2
      out = result.stdout + result.stderr
      assert "removed in v1.6" in out

  def test_library_json_still_works():
      # We won't seed; just confirm the command doesn't fail on the format check
      result = runner.invoke(app, ["export", "library", "--format", "json"])
      # Exit code may be 0 (works on empty DB) or 1 if no DB yet — must not be 2
      assert result.exit_code != 2
  ```

- [ ] Step 2: Run; expect failures
  Run: `cd backend && uv run python -m pytest tests/e2e/test_export_cli.py -v`
  Expected: most fail

- [ ] Step 3: Implement the CLI changes
  ```python
  # backend/app/cli/commands/export_cmd.py — replace fully
  """CLI commands for export.

  bookcompanion export book <id> [--format {json,markdown}] [-o PATH]
                                 [--no-book-summary] [--no-toc] [--no-annotations]
                                 [--exclude-section ID]...

  Flags only valid with --format markdown:
    --no-book-summary    Exclude the book-level summary block from the export.
    --no-toc             Exclude the Table of Contents.
    --no-annotations     Exclude all highlights and notes.
    --exclude-section    Exclude one or more sections by ID (repeatable).

  Library Markdown export was removed in v1.6. Use --format json for
  full-library backups, or run 'export book' per book.
  """
  import typer

  from app.cli.deps import async_command, get_services
  from app.cli.formatting import console, print_error, print_success
  from app.services.export_service import ExportError, ExportSelection

  export_app = typer.Typer(help="Export commands.")


  @export_app.command("book")
  @async_command
  async def export_book(
      book_id: int = typer.Argument(..., help="Book ID to export."),
      fmt: str = typer.Option("json", "--format", "-f", help="Export format: json or markdown."),
      output: str = typer.Option(None, "--output", "-o", help="Output file path."),
      no_book_summary: bool = typer.Option(
          False, "--no-book-summary",
          help="Exclude the book-level summary block (markdown only).",
      ),
      no_toc: bool = typer.Option(
          False, "--no-toc",
          help="Exclude the Table of Contents (markdown only).",
      ),
      no_annotations: bool = typer.Option(
          False, "--no-annotations",
          help="Exclude all highlights and notes (markdown only).",
      ),
      exclude_section: list[int] = typer.Option(
          None, "--exclude-section",
          help="Exclude a section by ID (repeatable; markdown only).",
      ),
  ):
      """Export a single book's data.

      Flags only valid with --format markdown:
        --no-book-summary, --no-toc, --no-annotations, --exclude-section
      """
      # FR-C5: strict combo error
      selection_flags_used = (
          no_book_summary or no_toc or no_annotations or bool(exclude_section)
      )
      if fmt == "json" and selection_flags_used:
          print_error(
              "--no-* and --exclude-section flags are only valid with "
              "--format markdown. JSON exports are full-fidelity."
          )
          raise typer.Exit(2)

      async with get_services() as svc:
          try:
              if fmt == "markdown":
                  # FR-C3: validate exclude_section IDs against this book's sections
                  if exclude_section:
                      from sqlalchemy import select
                      from app.db.models import BookSection
                      result = await svc["export"].session.execute(
                          select(BookSection.id).where(BookSection.book_id == book_id)
                      )
                      valid_ids = {row[0] for row in result.all()}
                      for sid in exclude_section:
                          if sid not in valid_ids:
                              print_error(
                                  f"section {sid} does not belong to book {book_id}."
                              )
                              raise typer.Exit(1)
                  selection = ExportSelection(
                      include_book_summary=not no_book_summary,
                      include_toc=not no_toc,
                      include_annotations=not no_annotations,
                      exclude_section_ids=frozenset(exclude_section or []),
                  )
                  # Shared orchestrator with the HTTP route handler (T7)
                  body, _is_empty = await svc["export"].export_book_markdown(
                      book_id, selection
                  )
                  if output:
                      from pathlib import Path
                      Path(output).write_text(body, encoding="utf-8")
                      print_success(f"Book exported to {output}")
                  else:
                      console.print(body)
              else:
                  # JSON path unchanged
                  content = await svc["export"].export_book(
                      book_id, fmt="json", output_path=output
                  )
                  if output:
                      print_success(f"Book exported to {output}")
                  else:
                      console.print(content)
          except ExportError as e:
              print_error(str(e))
              raise typer.Exit(1)
          except typer.Exit:
              raise
          except Exception as e:
              print_error(str(e))
              raise typer.Exit(1)


  @export_app.command("library")
  @async_command
  async def export_library(
      fmt: str = typer.Option("json", "--format", "-f", help="Export format: json (markdown removed in v1.6)."),
      output: str = typer.Option(None, "--output", "-o", help="Output file path."),
  ):
      """Export the entire library.

      Note: --format markdown was removed in v1.6. Use --format json.
      """
      if fmt == "markdown":
          print_error(
              "Library Markdown export was removed in v1.6 — use --format json "
              "for full-library backups, or run 'export book' per book."
          )
          raise typer.Exit(2)
      async with get_services() as svc:
          try:
              content = await svc["export"].export_library(fmt=fmt, output_path=output)
              if output:
                  print_success(f"Library exported to {output}")
              else:
                  console.print(content)
          except Exception as e:
              print_error(str(e))
              raise typer.Exit(1)
  ```

- [ ] Step 4: Run CLI tests
  Run: `cd backend && uv run python -m pytest tests/e2e/test_export_cli.py -v`
  Expected: 5 passed

- [ ] Step 5: Commit
  ```bash
  git add backend/app/cli/commands/export_cmd.py backend/tests/e2e/test_export_cli.py
  git commit -m "feat(cli): add markdown export flags + library markdown removal"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/cli/commands/export_cmd.py tests/e2e/test_export_cli.py` — no errors
- `cd backend && uv run python -m pytest tests/e2e/test_export_cli.py -v` — 5 passed

---

### T11: Frontend API client — `exportBookSummary` + types

**Goal:** Add the new export helper to `frontend/src/api/export.ts` returning `{ blob, filename, text, isEmpty }`. Constrain `exportLibrary` to JSON only.
**Spec refs:** FR-F9, FR-F10, FR-F11 (the helper-side change)

**Files:**
- Modify: `frontend/src/api/export.ts`
- Create: `frontend/src/api/__tests__/export.spec.ts` (new)

**Steps:**

- [ ] Step 1: Write failing tests
  ```typescript
  // Create frontend/src/api/__tests__/export.spec.ts
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { exportBookSummary, exportLibrary } from '@/api/export'

  describe('exportBookSummary', () => {
    beforeEach(() => {
      vi.restoreAllMocks()
    })

    it('builds default URL with format=markdown only', async () => {
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response('# X', {
          status: 200,
          headers: {
            'content-disposition': 'attachment; filename="x-summary-20260425.md"',
            'x-empty-export': 'false',
          },
        })
      )
      const r = await exportBookSummary(3)
      expect(fetchMock).toHaveBeenCalledOnce()
      const url = fetchMock.mock.calls[0][0] as string
      expect(url).toBe('/api/v1/export/book/3?format=markdown')
      expect(r.filename).toBe('x-summary-20260425.md')
      expect(r.isEmpty).toBe(false)
      expect(r.text).toBe('# X')
    })

    it('builds URL with selection params', async () => {
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response('# x', { status: 200, headers: { 'x-empty-export': 'true' } })
      )
      await exportBookSummary(7, {
        include_toc: false,
        include_annotations: false,
        exclude_section_ids: [14, 15],
      })
      const url = fetchMock.mock.calls[0][0] as string
      expect(url).toContain('format=markdown')
      expect(url).toContain('include_toc=false')
      expect(url).toContain('include_annotations=false')
      expect(url).toMatch(/exclude_section=14/)
      expect(url).toMatch(/exclude_section=15/)
    })

    it('returns isEmpty=true when header is "true"', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response('# t', { status: 200, headers: { 'x-empty-export': 'true' } })
      )
      const r = await exportBookSummary(1)
      expect(r.isEmpty).toBe(true)
    })

    it('falls back to book-{id}-summary-{YYYYMMDD}.md when content-disposition is missing', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('# t', { status: 200 }))
      const r = await exportBookSummary(42)
      expect(r.filename).toMatch(/^book-42-summary-\d{8}\.md$/)
    })

    it('throws on non-OK response', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 400 }))
      await expect(exportBookSummary(1)).rejects.toThrow()
    })
  })

  describe('exportLibrary', () => {
    it('rejects format=markdown at compile time and runtime', async () => {
      // TS would flag this; runtime guard:
      // @ts-expect-error — markdown is no longer a valid format
      await expect(exportLibrary({ format: 'markdown' })).rejects.toThrow(/json/i)
    })
  })
  ```

- [ ] Step 2: Run — expect failures
  Run: `cd frontend && npm run test:unit -- src/api/__tests__/export.spec.ts`
  Expected: failures (functions not yet implemented as expected)

- [ ] Step 3: Update `frontend/src/api/export.ts`
  ```typescript
  // frontend/src/api/export.ts
  export interface SummaryExportSelection {
    include_book_summary?: boolean
    include_toc?: boolean
    include_annotations?: boolean
    exclude_section_ids?: number[]
  }

  export interface SummaryExportResult {
    blob: Blob
    filename: string
    text: string
    isEmpty: boolean
  }

  export async function exportBookSummary(
    bookId: number,
    selection?: SummaryExportSelection
  ): Promise<SummaryExportResult> {
    const params = new URLSearchParams({ format: 'markdown' })
    if (selection?.include_book_summary === false)
      params.set('include_book_summary', 'false')
    if (selection?.include_toc === false) params.set('include_toc', 'false')
    if (selection?.include_annotations === false)
      params.set('include_annotations', 'false')
    for (const id of selection?.exclude_section_ids ?? []) {
      params.append('exclude_section', String(id))
    }
    const url = `/api/v1/export/book/${bookId}?${params}`
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Export failed: ${response.status}`)

    const cd = response.headers.get('content-disposition') || ''
    const m = cd.match(/filename="([^"]+)"/)
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    const filename = m ? m[1] : `book-${bookId}-summary-${today}.md`
    const isEmpty = response.headers.get('x-empty-export') === 'true'

    const blob = await response.blob()
    const text = await blob.text()
    return { blob, filename, text, isEmpty }
  }

  // EXISTING — KEEP exportBook + ExportOptions for the json path (used elsewhere)
  export interface ExportOptions {
    format: 'json' | 'markdown'
    include_summaries?: boolean
    include_annotations?: boolean
    include_concepts?: boolean
    include_eval?: boolean
  }

  export async function exportBook(bookId: number, options: ExportOptions) {
    const params = new URLSearchParams({ format: options.format })
    const response = await fetch(`/api/v1/export/book/${bookId}?${params}`)
    if (!response.ok) throw new Error('Export failed')
    return triggerDownload(
      response,
      `book_${bookId}.${options.format === 'json' ? 'json' : 'md'}`
    )
  }

  // EXISTING — constrain to json
  export async function exportLibrary(options: { format: 'json' }) {
    if ((options.format as string) !== 'json') {
      throw new Error('Library Markdown export was removed in v1.6 — use format: "json".')
    }
    const params = new URLSearchParams({ format: 'json' })
    const response = await fetch(`/api/v1/export/library?${params}`)
    if (!response.ok) throw new Error('Export failed')
    return triggerDownload(response, 'library_export.json')
  }

  export async function triggerDownload(response: Response, fallbackFilename: string) {
    const blob = await response.blob()
    const cd = response.headers.get('content-disposition') || ''
    const m = cd.match(/filename="([^"]+)"/)
    const filename = m ? m[1] : fallbackFilename
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }
  ```
  (Note: `triggerDownload` is now exported and accepts a fallback filename so `BookOverviewView` can reuse it in T12.)

- [ ] Step 4: Run unit tests
  Run: `cd frontend && npm run test:unit -- src/api/__tests__/export.spec.ts`
  Expected: all pass

- [ ] Step 5: Run TS type-check
  Run: `cd frontend && npm run type-check`
  Expected: no errors

- [ ] Step 6: Commit
  ```bash
  git add frontend/src/api/export.ts frontend/src/api/__tests__/export.spec.ts
  git commit -m "feat(frontend): add exportBookSummary helper + constrain library export to json"
  ```

**Inline verification:**
- `cd frontend && npm run lint -- src/api/` — no errors
- `cd frontend && npm run test:unit -- src/api/__tests__/export.spec.ts` — all pass
- `cd frontend && npm run type-check` — clean

---

### T12: BookOverviewView — buttons + click handlers + clipboard + toasts + in-flight

**Goal:** Add `Export summary`, `Copy as Markdown`, `Customize…` to `.actions`. Wire FR-F2/F3/F4/F5/F12/F14.
**Spec refs:** FR-F1, FR-F2, FR-F3, FR-F4, FR-F5, FR-F8 (default-path), FR-F12, FR-F14

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue`
- Create: `frontend/src/views/__tests__/BookOverviewView.export.spec.ts` (new — focused on the new export wiring; existing component tests remain in their own files)

**Steps:**

- [ ] Step 1: Write failing tests for the new export wiring
  ```typescript
  // Create frontend/src/views/__tests__/BookOverviewView.export.spec.ts
  // Note: the view is route-driven; tests use shallow mount with a stub store
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { mount } from '@vue/test-utils'
  import { createPinia, setActivePinia } from 'pinia'
  import { createRouter, createMemoryHistory } from 'vue-router'
  import BookOverviewView from '@/views/BookOverviewView.vue'

  function buildRouter() {
    return createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/books/:id', name: 'book-overview', component: BookOverviewView }],
    })
  }

  describe('BookOverviewView export buttons', () => {
    beforeEach(() => {
      setActivePinia(createPinia())
    })

    it('disables Export and Copy when book has no summaries', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
        const u = String(url)
        if (u.includes('/api/v1/books/1') && !u.endsWith('/tags') && !u.endsWith('/summary'))
          return Promise.resolve(new Response(JSON.stringify({
            id: 1, title: 'X', authors: [], status: 'COMPLETED',
            sections: [{ id: 1, title: 'C1', has_summary: false, section_type: 'chapter' }],
            default_summary_id: null,
          })))
        if (u.endsWith('/tags')) return Promise.resolve(new Response(JSON.stringify({ tags: [] })))
        return Promise.resolve(new Response(JSON.stringify({})))
      })
      const router = buildRouter()
      router.push('/books/1')
      await router.isReady()
      const wrapper = mount(BookOverviewView, { global: { plugins: [router] } })
      // Allow onMounted+fetch to settle
      await new Promise((r) => setTimeout(r, 50))
      const btnExport = wrapper.find('[data-testid="export-summary-btn"]')
      const btnCopy = wrapper.find('[data-testid="copy-markdown-btn"]')
      expect(btnExport.attributes('disabled')).toBeDefined()
      expect(btnCopy.attributes('disabled')).toBeDefined()
      expect(btnExport.attributes('title')).toMatch(/Generate a summary/i)
    })

    it('disables all three when book is UPLOADING', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({
          id: 1, title: 'X', authors: [], status: 'UPLOADING',
          sections: [], default_summary_id: null,
        }))
      )
      const router = buildRouter()
      router.push('/books/1')
      await router.isReady()
      const wrapper = mount(BookOverviewView, { global: { plugins: [router] } })
      await new Promise((r) => setTimeout(r, 50))
      const btnExport = wrapper.find('[data-testid="export-summary-btn"]')
      expect(btnExport.attributes('disabled')).toBeDefined()
      expect(btnExport.attributes('title')).toMatch(/processed/i)
    })
  })
  ```

- [ ] Step 2: Run — expect failures
  Run: `cd frontend && npm run test:unit -- src/views/__tests__/BookOverviewView.export.spec.ts`
  Expected: failures

- [ ] Step 3: Update `BookOverviewView.vue`
  Read `frontend/src/types/index.ts` first to confirm `Book.default_summary_id` is in the type (it should be per recon). If absent, compute the empty signal from `(book.sections || []).every((s) => !s.has_summary)`.
  ```vue
  <!-- Inside <script setup> after existing refs -->
  import { exportBookSummary } from '@/api/export'
  import { useUiStore } from '@/stores/ui'
  import ExportCustomizeModal from '@/components/book/ExportCustomizeModal.vue'

  const showModal = ref(false)
  const exporting = ref(false)
  const ui = useUiStore()

  const isProcessingStatus = computed(() =>
    book.value && (book.value.status === 'UPLOADING' || book.value.status === 'PARSING')
  )
  const hasNoSummaries = computed(() => {
    if (!book.value) return true
    if (book.value.default_summary_id) return false
    return !((book.value.sections || []).some((s: any) => s.has_summary))
  })
  const exportDisabled = computed(() => isProcessingStatus.value || hasNoSummaries.value || exporting.value)
  const customizeDisabled = computed(() => isProcessingStatus.value)

  function disabledTooltip(): string {
    if (isProcessingStatus.value) return 'Book is still being processed.'
    if (hasNoSummaries.value) return 'Generate a summary first.'
    return ''
  }

  async function onExportClick() {
    if (exportDisabled.value) return
    exporting.value = true
    try {
      const r = await exportBookSummary(bookId.value)
      // Use existing triggerDownload-like flow
      const url = URL.createObjectURL(r.blob)
      const a = document.createElement('a')
      a.href = url
      a.download = r.filename
      a.click()
      URL.revokeObjectURL(url)
      ui.showToast(
        r.isEmpty ? 'Summary exported (empty)' : `Summary exported as ${r.filename}`,
        'success'
      )
    } catch {
      ui.showToast('Export failed — check your connection.', 'error')
    } finally {
      exporting.value = false
    }
  }

  async function onCopyClick() {
    if (exportDisabled.value) return
    exporting.value = true
    const url = `/api/v1/export/book/${bookId.value}?format=markdown`
    try {
      if ((navigator as any).clipboard?.write && (window as any).ClipboardItem) {
        // ClipboardItem path — preserves user-gesture chain on Safari.
        // Capture the X-Empty-Export header inside the fetch promise's .then;
        // by the time `clipboard.write` resolves, the side-channel ref is set.
        let isEmpty = false
        const fetchPromise = fetch(url).then((r) => {
          if (!r.ok) throw new Error('fetch failed')
          isEmpty = r.headers.get('x-empty-export') === 'true'
          return r.blob()
        })
        try {
          await (navigator as any).clipboard.write([
            new (window as any).ClipboardItem({ 'text/plain': fetchPromise }),
          ])
          ui.showToast(
            isEmpty ? 'Summary copied (empty)' : 'Summary copied to clipboard',
            'success'
          )
        } catch (err: any) {
          if (err?.message === 'fetch failed') {
            ui.showToast('Export failed — check your connection.', 'error')
          } else {
            ui.showToast("Couldn't copy — try Export instead.", 'error')
          }
        }
      } else {
        // Legacy path
        const resp = await fetch(url)
        if (!resp.ok) {
          ui.showToast('Export failed — check your connection.', 'error')
          return
        }
        const isEmpty = resp.headers.get('x-empty-export') === 'true'
        const text = await resp.text()
        try {
          await navigator.clipboard.writeText(text)
          ui.showToast(
            isEmpty ? 'Summary copied (empty)' : 'Summary copied to clipboard',
            'success'
          )
        } catch {
          ui.showToast("Couldn't copy — try Export instead.", 'error')
        }
      }
    } finally {
      exporting.value = false
    }
  }
  ```

  Inside the template, replace the existing `.actions` block:
  ```vue
  <div class="actions">
    <router-link
      v-if="firstSection"
      class="cta resume"
      :to="{ name: 'section-detail', params: { id: String(book.id), sectionId: String(firstSection.id) } }"
    >
      Read
    </router-link>
    <button
      class="cta primary"
      data-testid="export-summary-btn"
      :disabled="exportDisabled"
      :title="disabledTooltip()"
      :aria-disabled="exportDisabled"
      @click="onExportClick"
    >
      {{ exporting ? 'Exporting…' : 'Export summary' }}
    </button>
    <button
      class="cta primary"
      data-testid="copy-markdown-btn"
      :disabled="exportDisabled"
      :title="disabledTooltip()"
      :aria-disabled="exportDisabled"
      @click="onCopyClick"
    >
      {{ exporting ? 'Copying…' : 'Copy as Markdown' }}
    </button>
    <a
      class="customize-link"
      data-testid="customize-export-link"
      :class="{ disabled: customizeDisabled }"
      :aria-disabled="customizeDisabled"
      @click.prevent="if (!customizeDisabled) showModal = true"
    >
      Customize…
    </a>
    <SummarizationProgress
      v-if="book.summary_progress && book.summary_progress.summarizable > 0"
      :book-id="book.id"
      :summarized="book.summary_progress.summarized"
      :total="book.summary_progress.summarizable"
      :failed-and-pending="book.summary_progress.failed_and_pending"
    />
  </div>

  <ExportCustomizeModal
    v-if="showModal && book"
    :book-id="bookId"
    :book="book"
    @close="showModal = false"
  />
  ```

  Append CSS rules for the new buttons and link:
  ```css
  .actions .cta.primary {
    background: var(--color-bg-muted, #f3f4f6);
    color: var(--color-text-primary, #111);
    border: 1px solid var(--color-border, #d1d5db);
    cursor: pointer;
  }
  .actions .cta.primary:disabled,
  .actions .cta.primary[disabled] {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .customize-link {
    font-size: 0.85rem;
    text-decoration: underline;
    color: #4f46e5;
    cursor: pointer;
  }
  .customize-link.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  ```

- [ ] Step 4: Run unit tests
  Run: `cd frontend && npm run test:unit -- src/views/__tests__/BookOverviewView.export.spec.ts`
  Expected: 2 passed

- [ ] Step 5: Type-check + lint
  Run: `cd frontend && npm run type-check && npm run lint -- src/views/BookOverviewView.vue`
  Expected: clean

- [ ] Step 6: Commit
  ```bash
  git add frontend/src/views/BookOverviewView.vue frontend/src/views/__tests__/BookOverviewView.export.spec.ts
  git commit -m "feat(frontend): add Export/Copy/Customize buttons to book detail page"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- src/views/__tests__/BookOverviewView.export.spec.ts` — 2 passed
- `cd frontend && npm run type-check` — clean

---

### T13: ExportCustomizeModal.vue + tests

**Goal:** Build the modal: refresh-on-open, four toggles (Sections is tri-state), section list, count footer, Cancel/Export/Copy footer + in-flight UX. Reuse PresetPickerModal styling.
**Spec refs:** FR-F6, FR-F7, FR-F8, FR-F12, FR-F14

**Files:**
- Create: `frontend/src/components/book/ExportCustomizeModal.vue`
- Create: `frontend/src/components/book/__tests__/ExportCustomizeModal.spec.ts`

**Steps:**

- [ ] Step 1: Write failing tests
  ```typescript
  // Create frontend/src/components/book/__tests__/ExportCustomizeModal.spec.ts
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { mount, flushPromises } from '@vue/test-utils'
  import { createPinia, setActivePinia } from 'pinia'
  import ExportCustomizeModal from '@/components/book/ExportCustomizeModal.vue'

  const sampleBook = {
    id: 3,
    title: 'Sample',
    default_summary_id: 1,
    sections: [
      { id: 10, title: 'Ch 1', has_summary: true, section_type: 'chapter' },
      { id: 11, title: 'Ch 2', has_summary: true, section_type: 'chapter' },
      { id: 12, title: 'Pending', has_summary: false, section_type: 'chapter' },
    ],
  }

  describe('ExportCustomizeModal', () => {
    beforeEach(() => {
      setActivePinia(createPinia())
      vi.spyOn(globalThis, 'fetch').mockImplementation((url: any) => {
        const u = String(url)
        if (u.includes('/api/v1/books/3'))
          return Promise.resolve(new Response(JSON.stringify(sampleBook)))
        // Export endpoint
        return Promise.resolve(new Response('# X', {
          status: 200,
          headers: {
            'content-disposition': 'attachment; filename="x.md"',
            'x-empty-export': 'false',
          },
        }))
      })
    })

    it('lists only sections with summaries and shows hidden count', async () => {
      const wrapper = mount(ExportCustomizeModal, {
        props: { bookId: 3, book: sampleBook },
      })
      await flushPromises()
      const items = wrapper.findAll('[data-testid="section-checkbox-row"]')
      expect(items.length).toBe(2)
      expect(wrapper.text()).toContain('2 of 3 sections summarized')
      expect(wrapper.text()).toContain('1 hidden')
    })

    it('omits the hidden-count clause when hidden = 0', async () => {
      const allSummed = {
        ...sampleBook,
        sections: sampleBook.sections.filter((s) => s.has_summary),
      }
      const wrapper = mount(ExportCustomizeModal, {
        props: { bookId: 3, book: allSummed },
      })
      await flushPromises()
      expect(wrapper.text()).toContain('2 of 2 sections summarized')
      expect(wrapper.text()).not.toContain('hidden')
    })

    it('Sections master toggle is indeterminate when partial', async () => {
      const wrapper = mount(ExportCustomizeModal, {
        props: { bookId: 3, book: sampleBook },
      })
      await flushPromises()
      // Uncheck section 10 -> partial
      await wrapper.find('[data-testid="section-checkbox-10"]').setValue(false)
      const master = wrapper.find('[data-testid="sections-master"]')
        .element as HTMLInputElement
      expect(master.indeterminate).toBe(true)
      expect(master.checked).toBe(false)
    })

    it('Sections master click flips indeterminate -> checked -> unchecked', async () => {
      const wrapper = mount(ExportCustomizeModal, {
        props: { bookId: 3, book: sampleBook },
      })
      await flushPromises()
      await wrapper.find('[data-testid="section-checkbox-10"]').setValue(false)
      const master = wrapper.find('[data-testid="sections-master"]')
      // indeterminate -> checked
      await master.trigger('click')
      expect((wrapper.find('[data-testid="section-checkbox-10"]').element as HTMLInputElement).checked).toBe(true)
      expect((wrapper.find('[data-testid="section-checkbox-11"]').element as HTMLInputElement).checked).toBe(true)
      // checked -> unchecked
      await master.trigger('click')
      expect((wrapper.find('[data-testid="section-checkbox-10"]').element as HTMLInputElement).checked).toBe(false)
      expect((wrapper.find('[data-testid="section-checkbox-11"]').element as HTMLInputElement).checked).toBe(false)
    })

    it('Export click calls exportBookSummary with selection', async () => {
      const wrapper = mount(ExportCustomizeModal, {
        props: { bookId: 3, book: sampleBook },
      })
      await flushPromises()
      // Uncheck TOC and section 10
      await wrapper.find('[data-testid="toggle-toc"]').setValue(false)
      await wrapper.find('[data-testid="section-checkbox-10"]').setValue(false)
      const fetchSpy = vi.spyOn(globalThis, 'fetch')
      await wrapper.find('[data-testid="modal-export-btn"]').trigger('click')
      await flushPromises()
      const exportCall = fetchSpy.mock.calls.find(
        (c) => String(c[0]).includes('/api/v1/export/book/3')
      )
      expect(exportCall).toBeDefined()
      const url = String(exportCall![0])
      expect(url).toContain('include_toc=false')
      expect(url).toMatch(/exclude_section=10/)
    })

    it('falls back to cached sections on refresh-fetch failure', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation((url: any) => {
        const u = String(url)
        if (u.includes('/api/v1/books/3'))
          return Promise.reject(new Error('network'))
        return Promise.resolve(new Response('# X', { status: 200 }))
      })
      const wrapper = mount(ExportCustomizeModal, {
        props: { bookId: 3, book: sampleBook },
      })
      await flushPromises()
      expect(wrapper.text()).toContain('Could not refresh')
      // Cached sections still rendered
      expect(wrapper.findAll('[data-testid="section-checkbox-row"]').length).toBe(2)
    })

    it('disables Book summary checkbox when book has no default_summary_id', async () => {
      const noSummary = { ...sampleBook, default_summary_id: null }
      const wrapper = mount(ExportCustomizeModal, {
        props: { bookId: 3, book: noSummary },
      })
      await flushPromises()
      const cb = wrapper.find('[data-testid="toggle-book-summary"]')
        .element as HTMLInputElement
      expect(cb.disabled).toBe(true)
    })
  })
  ```

- [ ] Step 2: Run — expect failures
  Run: `cd frontend && npm run test:unit -- src/components/book/__tests__/ExportCustomizeModal.spec.ts`
  Expected: failures

- [ ] Step 3: Implement the modal
  ```vue
  <!-- frontend/src/components/book/ExportCustomizeModal.vue -->
  <script setup lang="ts">
  import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
  import { useUiStore } from '@/stores/ui'
  import { exportBookSummary, type SummaryExportSelection } from '@/api/export'

  interface SectionLite {
    id: number
    title: string
    has_summary: boolean
  }

  const props = defineProps<{
    bookId: number
    book: { id: number; default_summary_id: number | null; sections: SectionLite[] }
  }>()
  const emit = defineEmits<{ close: [] }>()

  const ui = useUiStore()
  const refreshing = ref(true)
  const refreshFailed = ref(false)
  const sections = ref<SectionLite[]>(props.book.sections || [])
  const totalCount = computed(() => sections.value.length)
  const summarized = computed(() =>
    sections.value.filter((s) => s.has_summary)
  )
  const summarizedCount = computed(() => summarized.value.length)
  const hiddenCount = computed(() => totalCount.value - summarizedCount.value)

  const includeBookSummary = ref(props.book.default_summary_id !== null)
  const includeToc = ref(true)
  const includeAnnotations = ref(true)
  const checkedSectionIds = ref<Set<number>>(
    new Set(summarized.value.map((s) => s.id))
  )

  const masterChecked = computed(() =>
    summarizedCount.value > 0 && checkedSectionIds.value.size === summarizedCount.value
  )
  const masterIndeterminate = computed(() =>
    checkedSectionIds.value.size > 0 && !masterChecked.value
  )

  const masterEl = ref<HTMLInputElement | null>(null)
  watch([masterIndeterminate, masterEl], () => {
    if (masterEl.value) masterEl.value.indeterminate = masterIndeterminate.value
  })

  function toggleMaster() {
    if (masterChecked.value) {
      checkedSectionIds.value = new Set()
    } else {
      checkedSectionIds.value = new Set(summarized.value.map((s) => s.id))
    }
  }

  function isChecked(id: number) { return checkedSectionIds.value.has(id) }
  function setChecked(id: number, val: boolean | Event) {
    const v = typeof val === 'boolean' ? val : (val.target as HTMLInputElement).checked
    const next = new Set(checkedSectionIds.value)
    if (v) next.add(id); else next.delete(id)
    checkedSectionIds.value = next
  }

  const exporting = ref(false)
  const submitDisabled = computed(() => exporting.value)

  function buildSelection(): SummaryExportSelection {
    const excluded = summarized.value
      .filter((s) => !checkedSectionIds.value.has(s.id))
      .map((s) => s.id)
    return {
      include_book_summary: includeBookSummary.value,
      include_toc: includeToc.value,
      include_annotations: includeAnnotations.value,
      exclude_section_ids: excluded,
    }
  }

  async function onExport() {
    exporting.value = true
    try {
      const r = await exportBookSummary(props.bookId, buildSelection())
      const url = URL.createObjectURL(r.blob)
      const a = document.createElement('a')
      a.href = url
      a.download = r.filename
      a.click()
      URL.revokeObjectURL(url)
      ui.showToast(
        r.isEmpty ? 'Summary exported (empty)' : `Summary exported as ${r.filename}`,
        'success'
      )
      emit('close')
    } catch {
      ui.showToast('Export failed — check your connection.', 'error')
    } finally {
      exporting.value = false
    }
  }

  async function onCopy() {
    exporting.value = true
    try {
      const r = await exportBookSummary(props.bookId, buildSelection())
      try {
        await navigator.clipboard.writeText(r.text)
        ui.showToast(
          r.isEmpty ? 'Summary copied (empty)' : 'Summary copied to clipboard',
          'success'
        )
        emit('close')
      } catch {
        ui.showToast("Couldn't copy — try Export instead.", 'error')
      }
    } catch {
      ui.showToast('Export failed — check your connection.', 'error')
    } finally {
      exporting.value = false
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') emit('close')
  }

  onMounted(async () => {
    document.addEventListener('keydown', onKeydown)
    refreshing.value = true
    try {
      const r = await fetch(`/api/v1/books/${props.bookId}`)
      if (!r.ok) throw new Error('refresh failed')
      const fresh = await r.json()
      sections.value = fresh.sections || []
      checkedSectionIds.value = new Set(
        (fresh.sections || []).filter((s: SectionLite) => s.has_summary).map((s: SectionLite) => s.id)
      )
    } catch {
      refreshFailed.value = true
    } finally {
      refreshing.value = false
    }
  })
  onUnmounted(() => document.removeEventListener('keydown', onKeydown))
  </script>

  <template>
    <div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="export-modal-title" @click.self="emit('close')">
      <div class="modal-body">
        <h3 id="export-modal-title" class="modal-title">Export summary</h3>

        <div v-if="refreshing" class="loading">Refreshing sections…</div>
        <p v-if="refreshFailed" class="refresh-warning">Could not refresh — showing cached sections.</p>

        <fieldset class="toggles" :disabled="refreshing">
          <label>
            <input
              type="checkbox"
              data-testid="toggle-book-summary"
              v-model="includeBookSummary"
              :disabled="book.default_summary_id === null"
            />
            Book summary
            <span v-if="book.default_summary_id === null" class="muted"> — no book summary yet</span>
          </label>
          <label>
            <input type="checkbox" data-testid="toggle-toc" v-model="includeToc" />
            Table of contents
          </label>
          <label>
            <input type="checkbox" data-testid="toggle-annotations" v-model="includeAnnotations" />
            Highlights &amp; notes
          </label>
          <label class="sections-master">
            <input
              ref="masterEl"
              type="checkbox"
              data-testid="sections-master"
              :checked="masterChecked"
              @click.prevent="toggleMaster"
            />
            Sections
          </label>
        </fieldset>

        <ul class="section-list">
          <li v-for="s in summarized" :key="s.id" data-testid="section-checkbox-row">
            <label>
              <input
                type="checkbox"
                :data-testid="`section-checkbox-${s.id}`"
                :checked="isChecked(s.id)"
                @change="setChecked(s.id, $event)"
              />
              {{ s.title }}
            </label>
          </li>
          <li v-if="summarized.length === 0" class="muted">No sections found in this book.</li>
        </ul>
        <p class="count-footer">
          {{ summarizedCount }} of {{ totalCount }} sections summarized<span v-if="hiddenCount > 0"> — {{ hiddenCount }} hidden because they have no summary</span>
        </p>

        <div class="modal-actions">
          <button type="button" class="secondary-btn" @click="emit('close')" :disabled="exporting">Cancel</button>
          <button
            type="button"
            class="primary-btn"
            data-testid="modal-export-btn"
            :disabled="submitDisabled"
            @click="onExport"
          >
            {{ exporting ? 'Exporting…' : 'Export' }}
          </button>
          <button
            type="button"
            class="primary-btn"
            data-testid="modal-copy-btn"
            :disabled="submitDisabled"
            @click="onCopy"
          >
            {{ exporting ? 'Copying…' : 'Copy as Markdown' }}
          </button>
        </div>
      </div>
    </div>
  </template>

  <style scoped>
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 50; }
  .modal-body { width: min(560px, 92vw); max-height: 90vh; overflow: auto; background: var(--color-bg-primary, #fff); color: var(--color-text-primary, #111); border-radius: 0.75rem; padding: 1.25rem; box-shadow: 0 16px 40px rgba(0,0,0,0.25); display: flex; flex-direction: column; gap: 1rem; }
  .modal-title { margin: 0; font-size: 1.1rem; font-weight: 600; }
  .toggles { border: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.4rem; }
  .toggles label { display: flex; align-items: center; gap: 0.4rem; font-size: 0.9rem; }
  .sections-master { font-weight: 600; }
  .section-list { list-style: none; padding: 0 0 0 1.25rem; margin: 0; max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.9rem; }
  .count-footer { font-size: 0.8rem; color: #6b7280; margin: 0; }
  .muted { color: #6b7280; font-size: 0.85rem; }
  .refresh-warning { background: #fff7ed; border: 1px solid #fdba74; padding: 0.4rem 0.6rem; border-radius: 0.25rem; font-size: 0.8rem; }
  .loading { font-size: 0.85rem; color: #6b7280; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
  .primary-btn { padding: 0.5rem 1rem; background: var(--color-primary, #3b82f6); color: white; border: none; border-radius: 0.375rem; cursor: pointer; }
  .primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .secondary-btn { padding: 0.5rem 1rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; color: inherit; cursor: pointer; }
  .secondary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  </style>
  ```

- [ ] Step 4: Run modal tests
  Run: `cd frontend && npm run test:unit -- src/components/book/__tests__/ExportCustomizeModal.spec.ts`
  Expected: 7 passed

- [ ] Step 5: Type-check + lint
  Run: `cd frontend && npm run type-check && npm run lint -- src/components/book/`
  Expected: clean

- [ ] Step 6: Commit
  ```bash
  git add frontend/src/components/book/ExportCustomizeModal.vue frontend/src/components/book/__tests__/ExportCustomizeModal.spec.ts
  git commit -m "feat(frontend): add ExportCustomizeModal with refresh-on-open and tri-state toggle"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- src/components/book/__tests__/ExportCustomizeModal.spec.ts` — 7 passed
- `cd frontend && npm run type-check` — clean

---

### T14: BackupSettings cleanup — dropdown → single button

**Goal:** Replace the format selector + button with a single `Export library (JSON)` button. Drop the `exportFormat` ref.
**Spec refs:** FR-F11

**Files:**
- Modify: `frontend/src/components/settings/BackupSettings.vue`

**Steps:**

- [ ] Step 1: Add a regression assertion to existing tests if any (or skip if none — visual change confirmed in T15 manual smoke)
  Run: `cd frontend && find . -path ./node_modules -prune -o -name "*BackupSettings*" -print 2>/dev/null`
  If a spec exists, modify it to assert single-button shape. If none, this task has no automated test addition (the manual smoke in TN covers it).

- [ ] Step 2: Modify the component
  Apply via `Edit` tool to `frontend/src/components/settings/BackupSettings.vue:122-140`:
  ```vue
  <!-- Replace the entire 'Export Library' setting-group block -->
  <div class="setting-group">
    <h3 class="group-title">Export Library</h3>
    <p class="group-description">Export your entire library as JSON.</p>
    <div class="export-controls">
      <button
        class="btn-primary"
        :disabled="exporting"
        data-testid="export-library-btn"
        @click="handleExportLibrary"
      >
        {{ exporting ? 'Exporting...' : 'Export library (JSON)' }}
      </button>
    </div>
  </div>
  ```
  And in the `<script>`:
  ```typescript
  // REMOVE this line:
  // const exportFormat = ref<'json' | 'markdown'>('json')

  // UPDATE handleExportLibrary signature:
  async function handleExportLibrary() {
    exporting.value = true
    try {
      await exportApi.exportLibrary({ format: 'json' })
    } catch (e: unknown) {
      useUiStore().showToast(`Export failed: ${errorText(e, 'unknown error')}`, 'error')
    } finally {
      exporting.value = false
    }
  }
  ```

- [ ] Step 3: Type-check + lint
  Run: `cd frontend && npm run type-check && npm run lint -- src/components/settings/BackupSettings.vue`
  Expected: clean

- [ ] Step 4: Verify the component still mounts (smoke test)
  Run: `cd frontend && npm run test:unit 2>&1 | tail -20`
  Expected: existing test count preserved; no new failures

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/settings/BackupSettings.vue
  git commit -m "refactor(frontend): replace library export dropdown with single JSON button"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — clean
- `cd frontend && npm run lint -- src/components/settings/BackupSettings.vue` — clean

---

### T15: ToastContainer regression test (FR-F13 verification)

**Goal:** Verify the existing `ToastContainer` (already mounted in `AppShell`) renders toasts emitted by `showToast` with the spec-required attributes.
**Spec refs:** FR-F13 (P8 — verification only)

**Files:**
- Modify: `frontend/src/components/common/__tests__/ToastContainer.spec.ts`

**Steps:**

- [ ] Step 1: Read the existing test file to see what it covers
  Run: `cat frontend/src/components/common/__tests__/ToastContainer.spec.ts`

- [ ] Step 2: Add a regression assertion (only if not already present)
  Append (or merge into existing test) — assert:
  - `aria-live="polite"` on the container
  - Per-type CSS class (`toast--success`, `toast--error`)
  - 5-toast FIFO cap (already shipped by commit `764b7d0`; assert here so a regression would be caught)
  ```typescript
  import { describe, it, expect, beforeEach } from 'vitest'
  import { mount, flushPromises } from '@vue/test-utils'
  import { createPinia, setActivePinia } from 'pinia'
  import ToastContainer from '@/components/common/ToastContainer.vue'
  import { useUiStore } from '@/stores/ui'

  describe('ToastContainer (FR-F13 regression)', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('renders aria-live=polite region', async () => {
      const wrapper = mount(ToastContainer)
      const region = wrapper.find('.toast-stack')
      expect(region.attributes('aria-live')).toBe('polite')
    })

    it('renders each toast with type-specific class', async () => {
      const ui = useUiStore()
      const wrapper = mount(ToastContainer)
      ui.showToast('hello', 'success')
      ui.showToast('boom', 'error')
      await flushPromises()
      expect(wrapper.find('.toast--success').exists()).toBe(true)
      expect(wrapper.find('.toast--error').exists()).toBe(true)
    })
  })
  ```

- [ ] Step 3: Run
  Run: `cd frontend && npm run test:unit -- src/components/common/__tests__/ToastContainer.spec.ts`
  Expected: all pass

- [ ] Step 4: Commit (only if a real change was needed — otherwise skip)
  ```bash
  git add frontend/src/components/common/__tests__/ToastContainer.spec.ts
  git commit -m "test(frontend): add ToastContainer FR-F13 regression assertions"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- src/components/common/__tests__/ToastContainer.spec.ts` — passes

---

### T16: CLAUDE.md updates (FR-D1)

**Goal:** Three precise edits to `CLAUDE.md` per FR-D1.
**Spec refs:** FR-D1

**Files:**
- Modify: `CLAUDE.md`

**Steps:**

- [ ] Step 1: Update the "Running a book through the full pipeline" workflow example to show one of the new flags
  Find: `bookcompanion export book <book_id> --format markdown`
  Replace with: `bookcompanion export book <book_id> --format markdown --no-toc -o ~/notes/<slug>.md`

- [ ] Step 2: Add a "Markdown export" entry under the "CLI — Core" command listing
  Insert after the existing `bookcompanion list` line:
  ```markdown
  uv run bookcompanion export book <id> --format markdown [--no-book-summary] [--no-toc] [--no-annotations] [--exclude-section <id>] -o file.md   # Summaries-focused Markdown export
  ```

- [ ] Step 3: Add a deprecation callout under "CLI — Core"
  Insert near the export commands listing:
  ```markdown
  > **v1.6 deprecation:** `bookcompanion export library --format markdown` was removed. Use `--format json` for full-library backups, or run `export book` per book.
  ```

- [ ] Step 4: Verify the file still renders (no broken markdown)
  Run: `head -260 CLAUDE.md | tail -80`

- [ ] Step 5: Commit
  ```bash
  git add CLAUDE.md
  git commit -m "docs(claude.md): document markdown export flags and library deprecation"
  ```

**Inline verification:**
- `git diff HEAD~1 CLAUDE.md` shows only the three intended edits

---

### TN: Final verification

**Goal:** Verify the entire implementation works end-to-end.

- [ ] **Lint & format:**
  - `cd backend && uv run ruff check . && uv run ruff format --check .` — no errors (or only pre-existing baseline drift documented in Prerequisites)
  - `cd frontend && npm run lint && npm run format` — clean

- [ ] **Type check:**
  - `cd frontend && npm run type-check` — 0 errors

- [ ] **Unit tests (backend):**
  - `cd backend && uv run python -m pytest tests/unit/test_slug.py tests/unit/test_export_renderer.py -v` — all pass (~50 tests)

- [ ] **Integration tests (backend):**
  - `cd backend && uv run python -m pytest tests/integration/test_api/test_export_api.py tests/integration/test_api/test_export_book_markdown.py -v` — all pass

- [ ] **E2E CLI tests:**
  - `cd backend && uv run python -m pytest tests/e2e/test_export_cli.py -v` — all pass (5 tests)

- [ ] **Full backend test suite (regression check):**
  - `cd backend && uv run python -m pytest -m "not integration_llm"` — no regressions vs. Prerequisites baseline

- [ ] **Frontend unit tests:**
  - `cd frontend && npm run test:unit` — all pass; new specs added

- [ ] **Image-URL sanitization gate (G4):**
  ```bash
  cd backend && uv run python -m pytest tests/integration/test_api/test_export_book_markdown.py::test_image_urls_never_survive -v
  ```
  Expected: 1 passed; assertion `"/api/v1/images/" not in resp.text` is the gate

- [ ] **JSON regression gate (G6):**
  ```bash
  cd backend && uv run python -m pytest tests/integration/test_api/test_export_book_markdown.py::test_json_format_unchanged_byte_equal -v
  ```
  Expected: 1 passed

- [ ] **FR-ID coverage gate** (per `~/.pmos/learnings.md` /plan entry):
  ```bash
  grep -oE "FR-[A-Z][0-9.a-z]+" docs/specs/2026-04-25-summary-markdown-export-spec.md | sort -u > /tmp/spec-frs.txt
  grep -oE "FR-[A-Z][0-9.a-z]+" docs/plans/2026-04-25-summary-markdown-export-implementation-plan.md | sort -u > /tmp/plan-frs.txt
  comm -23 /tmp/spec-frs.txt /tmp/plan-frs.txt
  ```
  Expected: empty output (every FR-ID in the spec appears in the plan)

- [ ] **API smoke test (CLI):**
  ```bash
  cd backend && uv run bookcompanion export book 1 --format markdown -o /tmp/sm.md
  head -10 /tmp/sm.md
  grep -c "/api/v1/images/" /tmp/sm.md   # Expect 0
  ```
  Expected: file written, contains `# {title}`, `**Author:**`, `**Exported:**`; zero image-URL substrings

- [ ] **API smoke test (HTTP):**
  ```bash
  cd backend && uv run bookcompanion serve --port 8765 &
  SERVER_PID=$!
  sleep 3
  curl -sf 'http://localhost:8765/api/v1/export/book/1?format=markdown&include_toc=false' | head -5
  curl -sI 'http://localhost:8765/api/v1/export/library?format=markdown' | head -1
  kill $SERVER_PID
  ```
  Expected: book endpoint returns markdown body without TOC; library markdown returns `HTTP/1.1 410 Gone`

- [ ] **Frontend smoke (Playwright MCP — manual /verify):**
  1. `cd frontend && npm run build && rm -rf ../backend/app/static && cp -R dist ../backend/app/static`
  2. `cd backend && uv run bookcompanion serve --port 8765 &`
  3. Navigate via Playwright MCP to `http://localhost:8765/books/1`
  4. Verify `[data-testid="export-summary-btn"]`, `[data-testid="copy-markdown-btn"]`, `[data-testid="customize-export-link"]` render
  5. Click `Export summary` → verify download triggers + toast appears
  6. Click `Customize…` → verify modal opens, refreshes section list
  7. Open downloaded `.md` in VS Code preview and Obsidian — confirm TOC links scroll to sections
  8. `kill $SERVER_PID`

- [ ] **Cleanup:**
  - Remove `/tmp/sm.md`, `/tmp/spec-frs.txt`, `/tmp/plan-frs.txt`
  - Stop any background servers: `lsof -ti:8765 | xargs -r kill`
  - Confirm no debug logging or `console.log` remains in `BookOverviewView.vue` or `ExportCustomizeModal.vue`: `grep -n "console.log" frontend/src/views/BookOverviewView.vue frontend/src/components/book/ExportCustomizeModal.vue`
  - `cd frontend && rm -rf node_modules/.vite` (clears cached build)
  - **Run `/changelog` after merge to land FR-D2** (user-facing changelog entry describing the new shape, the new UI affordances on the book detail page, and the library Markdown deprecation). FR-D2 is intentionally deferred to the post-merge `/changelog` skill workflow per spec.

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | (a) FR-ID coverage gate (`grep -oE "FR-[A-Z][0-9]+[a-z]?" spec.md \| sort -u \| comm -23 - plan-frs.txt`) flagged 2 misses: FR-C4 (cited nowhere) and FR-D2 (changelog, deferred to post-merge `/changelog`). (b) T8 and T10 were empty fold-stub headings — confusing for a fresh executor. (c) CLI markdown branch (T9) duplicated the route handler's render orchestration: build ExportSelection, call `_collect_book_data` + `_collect_book_annotations` + `_render_summary_markdown` → drift risk. (d) T12's `onCopyClick` issued a separate HEAD request to read `X-Empty-Export` after the ClipboardItem call — wasteful and timing-flaky. | (a) FR-C4 added to T9 spec refs; FR-D2 documented as a Cleanup item in TN ("Run /changelog after merge"). (b) T8 and T10 stub headings deleted; execution-order diagram tightened to fold lib-410 into T7 and lib-exit-2 into T9; explanatory note added under the diagram. (c) New `ExportService.export_book_markdown(book_id, selection) → tuple[str, bool]` public orchestrator added to T6 (step 4b) with two unit tests; T7 route handler and T9 CLI both call it instead of inlining the four-step orchestration. (d) T12 onCopyClick rewritten: capture `isEmpty` inside the fetch promise's `.then` callback; `clipboard.write` resolution then guarantees the side-channel ref is set; HEAD request removed. |
