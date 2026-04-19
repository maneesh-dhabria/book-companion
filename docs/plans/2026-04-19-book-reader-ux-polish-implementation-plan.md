# Book Reader UX Polish — Implementation Plan

**Date:** 2026-04-19
**Spec:** `docs/specs/2026-04-18-book-reader-ux-polish-spec.md`
**Requirements:** `docs/requirements/2026-04-18-book-reader-ux-polish.md`

---

## Overview

This plan implements the five concerns of the UX-polish spec in dependency order: (1) a shared section classifier module with new front-matter types, (2) two Alembic data migrations that repair legacy books on next startup, (3) API extensions surfacing summary markdown + a book-level progress counter + a `scope` parameter on the summarize endpoint + richer SSE events, (4) frontend reader polish (landing-section precedence, TOC accordion, Summary tab empty-states, a `summarizationJob` store, a book-header progress component), and (5) a post-DOMPurify link-policy pass in the reader. Tasks are strictly TDD (red → green → commit), each under ~1 hour of focused work.

**Done when:** Reopening *Understanding Michael Porter* lands on "1. Competition: The Right Mind-Set"; Copyright/Acknowledgments sit under a collapsed Front Matter accordion; the book header reads "N of 12 summarized" with only summarizable types in the denominator; clicking *Summarize pending sections* fills the remainder over SSE, skipping front-matter; the Summary tab renders `summary_md` for completed sections and a typed empty-state for everything else; heading/footnote anchors render as non-clickable spans; `SELECT count(*) FROM book_sections WHERE content_md LIKE '%__IMG_PLACEHOLDER__:%__ENDIMG__%'` returns 0; `uv run python -m pytest` is green (~455 tests); `npm run test:unit` and `npm run build` pass.

**Execution order:**

```
T1 (section_classifier module)
 ├─ T2 (wire EPUB parser)
 ├─ T3 (wire PDF parser)
 ├─ T5 (Migration B: reclassify)
 ├─ T7 (book response summary_progress)
 └─ T9 (summarizer scope + type gate)
T4 (Migration A: image backfill)          [P — independent]
T6 (section response summary_md + is_summarizable)  [P after T1 for is_summarizable]
T8 (ProcessingStartRequest + route validation)       [P after T1]
T9 ─┬─ T10 (SSE: section_id + processing_started + section_started)
    │
    ▼
T11 (frontend processing.ts + reader.ts constants)
 ├─ T12 (reader store: landing + updateSection)
 ├─ T13 (TOCDropdown Front Matter accordion)
 └─ T14 (summarizationJob store)
      ├─ T15 (SummaryEmptyState component)
      └─ T16 (SummarizationProgress component)
           └─ T17 (BookDetailView: Summary tab flow + route guard)
T18 (link-policy.ts utility)       [P — independent]
 └─ T19 (ReadingArea post-DOMPurify rewrite)
T20 (cross-layer contract guard test)  [P after T1 + T11]
T21 (final verification)
```

T4 is fully independent and can ship first. T6, T18, T20 are parallelizable after their named predecessors. Everything else is serial by the arrows shown.

---

## Decision Log

> Inherits architecture decisions D1–D13 from the spec. Entries below are implementation-specific planning decisions.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| P1 | Ship classifier module (T1) before both migrations | (a) Migration B first, (b) Classifier first (chosen) | Migration B's `upgrade()` imports `detect_section_type` + `SUMMARIZABLE_TYPES` from the new module. Without T1 the migration would vendor its own copy and invite drift. |
| P2 | Migration A (image backfill) runs in parallel, first if convenient | (a) Sequence after classifier, (b) Parallel (chosen) | Migration A is entirely self-contained — reuses the existing `from_placeholder` helper and has no touchpoint with the classifier. Landing it first also gives us a low-risk proof that the migration-on-startup path still works before Migration B (which is higher-risk) ships. |
| P3 | Every task commits independently after its own test passes | — | TDD discipline. Matches prior plan conventions (2026-04-13 plan T1–T6). Makes `git bisect` trivial if a later task regresses an earlier one. |
| P4 | Backend SSE event changes (T10) split from summarizer scope filter (T9) | (a) Single task, (b) Split (chosen) | The summarizer filter is pure Python list-filtering with one-file scope; the SSE change touches two files (`summarizer_service.py` callback signatures + `processing.py` handlers) and adds three new event types. Keeping them separate means each commit has one reason to fail its test. |
| P5 | Frontend constants duplicated as literals (not fetched from backend) | (a) New API endpoint returning the sets, (b) Duplicated with cross-layer test guard (chosen, per spec FR-06a) | Sets are tiny and stable; fetching them at runtime adds a request + a loading state for zero user benefit. T20's contract test reads both files and fails on drift — same protection at a fraction of the cost. |
| P6 | `SummarizationProgress` mount added directly in `BookDetailView.vue` header block, not a new `BookHeader.vue` split | (a) Extract BookHeader component first, (b) Mount inline (chosen) | Scope creep avoidance — the existing file already has the book title/authors row. If that region grows a third component later, extract then. |
| P7 | `summarizationJob` store lives at `frontend/src/stores/summarizationJob.ts` as a plain Pinia singleton; lifecycle reset via `onBeforeRouteLeave` in BookDetailView | (a) Scoped provide/inject, (b) Plain Pinia with view-owned reset (chosen) | Matches the existing `reader` + `readerSettings` + `annotations` patterns in `frontend/src/stores/`. Consistency with neighbors trumps theoretical purity. |
| P8 | `link-policy.ts` is a pure utility with zero Vue imports | — | Testable in Vitest without mounting a component. Composes cleanly when ReadingArea imports it. |
| P9 | Migration B uses SQLAlchemy Core (`sa.text` + `op.get_bind()`), no ORM | (a) ORM models, (b) Core SQL (chosen per spec D4) | Alembic migrations run sync; ORM models may evolve; Core SQL against the live schema is the standard Alembic pattern and matches the only existing revision `e152941ea209`. |
| P10 | Test fixtures for classifier use a table-test over `(title, content_md, expected_type)` tuples in a single parametrized test | (a) One test per pattern, (b) Parametrized table (chosen) | 20+ cases (each pattern + boundary + negative). Table-test keeps additions to new patterns a one-line change. |
| P11 | Per-section commit in Migration B (spec FR-18a) — commit after all sections for a given `book_id` are processed | — | Spec mandates this. Implementation: accumulate changes in-loop, `connection.commit()` at each book boundary. |
| P12 | `is_summarizable` on the section response is computed in `_build_section_response`, not stored | (a) Denormalized column, (b) Computed (chosen) | Classifier output is authoritative; denormalization would risk drift every time the set changes. One boolean compute per section response — free. |
| P13 | `summary_progress` queries run inline in `_book_to_response` (no new repo method) | (a) Extract to BookRepository, (b) Inline (chosen) | Two `SELECT count(*)` aggregates on an already-indexed column. Extraction adds indirection without reuse — no other caller needs this shape. |
| P14 | `summarizationJob.reset()` preserves `failedSections` across job completion; only `startJob({scope:'section', section_id})` clears that section's entry | (a) Strict FR-38 literal: clear everything, (b) Preserve failedSections (chosen) | Intent drift is acceptable here. Real UX: after a failed section the user scrolls away, comes back — the error banner should still be there with the Retry CTA. Literal FR-38 would lose that state on job completion. Call this out in the review log so future readers don't mistake it for a spec miss. |
| P15 | SSE recovery (E4/E4a) implemented inline in T14, not deferred | (a) Defer to accepted risk, (b) Separate follow-up task, (c) Inline (chosen) | User directive. The 30-second grace + 5-second poll window is a ~25-line addition in the store plus one test; deferring means a real-world network glitch leaves the button stuck. Inline keeps feature ownership in one PR. |

---

## Code Study Notes

- **`backend/app/services/parser/epub_parser.py:16-41`** — `SECTION_TYPE_PATTERNS` is a module-level dict; `_detect_section_type` is a `@staticmethod` on `EPUBParser`. Extracting both to `section_classifier.py` and re-exporting from `epub_parser.py` is a one-line import swap at callsites (`:313` and `:375`).
- **`backend/app/services/parser/epub_parser.py:317`** — `_merge_stub_sections` runs *after* `_walk_toc` has already assigned `section_type` via the old classifier. Stub merges preserve the successor's type, so merging happens downstream of classification. This matches spec D2 (the <1000-char threshold for `part_header` lands naturally).
- **`backend/app/services/parser/pdf_parser.py:87-115`** — `_pages_to_sections` creates `ParsedSection` *without* passing `section_type` (default `"chapter"`). `_chunk_by_pages` same. Both need a post-construction pass `section.section_type = detect_section_type(section.title, section.content_md)`.
- **`backend/app/services/parser/image_url_rewrite.py:14,45-55`** — `_PLACEHOLDER` regex requires both `__IMG_PLACEHOLDER__:` + `__ENDIMG__`. `from_placeholder(md, map)` is reusable verbatim for Migration A.
- **`backend/app/api/routes/sections.py:33-75`** — `_build_section_response` already fetches `Summary` when `default_summary_id` is set. Adding `summary_md` to the `SummaryBriefResponse` payload is a single field change + schema update. `is_summarizable` lands in the top-level dict, derived from `section.section_type in SUMMARIZABLE_TYPES`.
- **`backend/app/api/routes/books.py:60-88`** — `_book_to_response` builds a sections list + metadata. `summary_progress` = two `func.count(BookSection.id)` queries filtered by `section_type.in_(SUMMARIZABLE_TYPES)` and `default_summary_id.isnot(None)`. Computed once per GET.
- **`backend/app/api/schemas.py:179-183`** — `ProcessingStartRequest` is simple pydantic. Adding `scope: Literal["all","pending","section"] = "all"` + `section_id: int | None = None` is additive and backward-compatible (`"all"` default preserves current behavior).
- **`backend/app/api/routes/processing.py:27-48`** — preset validation already runs before job creation; scope validation lands in the same block.
- **`backend/app/api/routes/processing.py:109-166`** — four callback sites (`on_section_complete`, `on_section_skip`, `on_section_fail`, `on_section_retry`) each publish to `event_bus`. Today's payloads omit `section_id` and there's no `section_started` event. T10 adds `section_id` to all four + a new `on_section_start` callback + a one-shot `processing_started` publish at the start of the job.
- **`backend/app/services/summarizer/summarizer_service.py:79-215`** — the main loop iterates `sections` sequentially. The skip-completed branch uses `get_latest_by_content_and_facets`; `scope="pending"` restricts to sections where `default_summary_id is None`; `scope="section"` restricts to a single section. Non-summarizable-type gate (FR-26) runs *before* the skip-completed check, and is bypassed only when `scope="section"` (user-intent override). The `on_section_start` callback fires immediately before the `await self._summarize_single_section(...)` call at line 124.
- **`backend/app/db/models.py:93-107,202-204`** — `SectionType` string enum exists but is *not bound* to the column (column is `String(50)`). Adding new string values needs no enum update (the enum is historical/reference only). The column has `index=True`, so count queries for `summary_progress` are already fast.
- **`backend/app/db/repositories/section_repo.py:24-31`** — `get_by_book_id` uses `selectinload(...).undefer(Image.data)`. The `scope="pending"` filter is a Python-level list comprehension on the returned list; no new query needed.
- **`backend/app/migrations/versions/e152941ea209_initial_sqlite_schema.py`** — sole existing revision, `revision = "e152941ea209"`, `down_revision = None`. New revisions must chain: `down_revision = "e152941ea209"` for the first new one, then chain off that for the second.
- **`backend/app/cli/commands/init_cmd.py:73-79`** — migrations run via `alembic.command.upgrade(cfg, "head")` on init. Both new revisions auto-apply. No code change needed to invoke them.
- **`frontend/src/stores/reader.ts:22-30,32-44`** — `loadBook` fetches book + sections; `loadSection` sets `contentMode` based on `has_summary`. The landing-section precedence (spec FR-31) lands in `loadBook` (compute target section) or the caller; the spec directs it to `loadBook`. Implementation: after fetching sections, compute the target section, store it on the store so BookDetailView can navigate to it.
- **`frontend/src/views/BookDetailView.vue:34-47,149-156`** — `loadFromRoute` already uses `route.params.sectionId ?? reader.sections[0]?.id`. Landing-section precedence replaces the `?? reader.sections[0]?.id` fallback with a computed target from `reader.loadBook`. The `<ReadingArea>` at :151 currently binds unconditionally to `content_md`; this is Issue #3's root (FR-32).
- **`frontend/src/api/processing.ts:4-9,25-63`** — `ProcessingOptions` lacks `scope`/`section_id`; `SSEHandlers` already has `onSectionStarted` with `section_id` in the type (speculative), confirming FR-39b. Adding `onProcessingStarted/onSectionFailed/onSectionSkipped/onSectionRetrying` + wiring in `connectSSE` is additive (T11).
- **`frontend/src/components/reader/ReadingArea.vue:16-24`** — `renderedHtml` is a `computed` that pipes `md.render(content)` through `DOMPurify.sanitize`. Adding a post-DOMPurify DOM walk is a one-place change in that `computed` body (T19).
- **`frontend/src/components/reader/TOCDropdown.vue:32-47`** — flat `v-for` over `sections.filter(...)`. Accordion refactor wraps the filtered result in a partition (body + frontMatter) and renders the front-matter bucket inside `<details>` (T13).
- **Existing test scaffold** — `backend/tests/unit/test_*.py` + `tests/integration/test_*.py`. Integration tests generally seed a book via fixtures in `tests/conftest.py`. Reuse `tmp_path`-scoped fixtures for migrations.
- **Frontend test scaffold** — `frontend/src/**/__tests__/*.spec.ts` or `frontend/src/**/*.spec.ts`. `npm run test:unit` runs Vitest.

---

## Prerequisites

- On `main` branch, working tree clean (currently one untracked `test.sh` + `.playwright-mcp/` — unrelated).
- `cd backend && uv sync --dev` already run — verified in CLAUDE.md `uv run pytest` path.
- `cd frontend && npm install` already run.
- Sister spec `2026-04-13-post-install-runtime-quality-spec.md` has already shipped (confirmed by `git log` showing `e052f4e docs: add SQLAlchemy rollback + identity-map learning to CLAUDE.md` post-implementation). Per-section commit + skip-completed already work; this plan consumes that behavior.
- Claude or Codex CLI on `$PATH` for any manual end-to-end test (not required for unit/integration tests, which stub the LLM).

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/app/services/parser/section_classifier.py` | Shared regex patterns + `detect_section_type(title, content_md)` + `FRONT_MATTER_TYPES`, `SUMMARIZABLE_TYPES` sets |
| Create | `backend/tests/unit/test_section_classifier.py` | Parametrized table test over (title, content_md, expected) tuples; FR-01/02/03/07 |
| Modify | `backend/app/services/parser/epub_parser.py` | Remove local `SECTION_TYPE_PATTERNS` + `_detect_section_type`; import from classifier; callsites at `:313` + `:375` pass `content_md` |
| Modify | `backend/app/services/parser/pdf_parser.py` | Classify each `ParsedSection` via `detect_section_type(title, content_md)` in both `_pages_to_sections` and `_chunk_by_pages` |
| Create | `backend/tests/unit/test_pdf_parser_section_types.py` | PDF fixture has `Copyright`/`Introduction`/generic chapter titles → asserts classifier output |
| Create | `backend/app/migrations/versions/<hash>_backfill_image_placeholders.py` | Migration A: substitute `__IMG_PLACEHOLDER__:…__ENDIMG__` tokens via `from_placeholder` |
| Create | `backend/tests/integration/test_migration_image_placeholders.py` | Seed + upgrade + re-upgrade + assertions |
| Create | `backend/app/migrations/versions/<hash>_reclassify_sections_and_prune_frontmatter.py` | Migration B: reclassify + prune auto summaries + preserve user-curated + re-point `default_summary_id`; per-book commit |
| Create | `backend/tests/integration/test_migration_reclassify_sections.py` | Seed 5-section book + upgrade + re-upgrade + assertions |
| Modify | `backend/app/api/routes/sections.py:33-75` (`_build_section_response`) | Add `summary_md` to default_summary payload; add top-level `is_summarizable` |
| Modify | `backend/app/api/schemas.py` (`SummaryBriefResponse`, `SectionResponse`) | Add `summary_md: str \| None = None`; add `is_summarizable: bool = True` |
| Create | `backend/tests/unit/test_sections_route_summary_md.py` | Assert `summary_md` populated when default summary exists; `is_summarizable` correct for `chapter` vs `copyright` |
| Modify | `backend/app/api/routes/books.py:60-88` (`_book_to_response`) | Compute `summary_progress` = `{summarized, total}`; add to response dict |
| Modify | `backend/app/api/schemas.py` (`BookResponse`) | Add `summary_progress: dict[str, int] \| None = None` |
| Create | `backend/tests/unit/test_books_route_summary_progress.py` | Seed a book with mixed types + some summarized → assert counts |
| Modify | `backend/app/api/schemas.py` (`ProcessingStartRequest`) | Add `scope: Literal["all","pending","section"] = "all"`, `section_id: int \| None = None` |
| Modify | `backend/app/api/routes/processing.py:27-60` | Validate scope/section_id combinations (422 / 400); pass through to summarizer |
| Create | `backend/tests/unit/test_summarize_scope_validation.py` | Scope/section_id 422 + 400 error cases |
| Modify | `backend/app/services/summarizer/summarizer_service.py:40-239` (`summarize_book`) | Accept `scope`, `section_id`; filter iteration set; gate non-summarizable types (except scope="section"); call new `on_section_start` callback; mutually-exclusive `scope="pending"` + `force=True` |
| Create | `backend/tests/integration/test_summarize_scope_pending.py` | 5-section book with 2 summarized → `scope="pending"` summarizes only 3 |
| Create | `backend/tests/integration/test_summarize_scope_section.py` | Single-section summary; wrong-book section_id → ValueError |
| Create | `backend/tests/integration/test_summarize_nonsummarizable_skipped.py` | Mixed book → non-summarizable types never summarized on `scope="all"` |
| Modify | `backend/app/api/routes/processing.py:109-231` | New `on_section_start` callback wiring; emit `processing_started` + `section_started` events; add `section_id` to all four existing event payloads |
| Create | `backend/tests/integration/test_summarize_sse_events.py` | Subscribe test client; assert event sequence incl. `section_id` in every payload |
| Modify | `frontend/src/api/processing.ts` | `ProcessingOptions` gains `scope?`, `section_id?`; `SSEHandlers` gains 4 new handler slots; `connectSSE` wires them |
| Modify | `frontend/src/stores/reader.ts` | Export `FRONT_MATTER_TYPES`, `SUMMARIZABLE_TYPES`; `loadBook` computes landing section per precedence rules; new `updateSection(section)` action |
| Create | `frontend/src/stores/__tests__/reader.spec.ts` | Landing-section precedence test: URL → saved → first summarizable → sections[0] |
| Modify | `frontend/src/components/reader/TOCDropdown.vue` | Partition sections into `body` + `frontMatter`; render front-matter bucket inside `<details>` |
| Create | `frontend/src/components/reader/__tests__/TOCDropdown.spec.ts` | Front Matter accordion rendering + partitioning |
| Create | `frontend/src/stores/summarizationJob.ts` | Pinia store: `{bookId, jobId, activeJobSectionId, scope, failedSections}`; `startJob`, on-*, `reset`, computeds |
| Create | `frontend/src/stores/__tests__/summarizationJob.spec.ts` | State transitions on SSE events; retry clears failedSections entry |
| Create | `frontend/src/components/reader/SummaryEmptyState.vue` | 4-state empty UI: not-applicable / not-yet / generating / failed (with retry) |
| Create | `frontend/src/components/reader/__tests__/SummaryEmptyState.spec.ts` | Renders correct state per prop combo |
| Create | `frontend/src/components/book/SummarizationProgress.vue` | "{N} of {M} summarized" + *Summarize pending* button |
| Create | `frontend/src/components/book/__tests__/SummarizationProgress.spec.ts` | Hidden when total=0; button disabled during active job |
| Modify | `frontend/src/views/BookDetailView.vue` | Mount `<SummarizationProgress>`; Summary tab routing (SummaryEmptyState vs ReadingArea); `onBeforeRouteLeave` → `summarizationJob.reset()` |
| Create | `frontend/src/utils/link-policy.ts` | `classifyLink(href)` returns `'internal-anchor' \| 'external' \| 'other'` |
| Create | `frontend/src/utils/__tests__/link-policy.spec.ts` | Table test over 12 href shapes |
| Modify | `frontend/src/components/reader/ReadingArea.vue:22-25` | Post-DOMPurify DOMParser walk: relative/other → `<span>`, external → `target=_blank rel=noopener noreferrer` |
| Create | `backend/tests/unit/test_section_type_sets_contract.py` | Parse both backend `section_classifier.py` + `frontend/src/stores/reader.ts`; assert set literals equal (FR-06a) |
| Modify | `docs/changelog.md` | User-facing entry: reclassification + pruning + image backfill + reader UX polish |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Migration B's summary-preservation heuristic (>1 summaries ⇒ user-curated) misidentifies a rare edge case where the user generated two auto-batches with different presets on the same section | Low | Spec §E1 accepts this — preservation is the defensive default. Worst case: one auto summary survives that could have been pruned. No data loss. |
| Per-book commit in Migration B allows a crash mid-book → retry produces no changes (idempotency). But if the classifier itself raises inside the loop, the partial book's in-memory changes are lost | Low | Both migrations are idempotent (FR-11, FR-17). Wrap the per-section work in try/except that logs + re-raises; the per-book commit boundary plus idempotency means re-run resumes correctly from the next book. |
| Frontend `section_id` wiring breaks on a backend regression that drops the field | Medium | T20's contract test catches drift in the type-set constants but NOT in event payloads. Mitigation: T10's integration test asserts every section event carries a non-null `section_id`. |
| `linking-policy` rewriting + `v-html` together produce a re-render flicker | Low | Post-DOMPurify DOM walk + re-serialization runs once inside the `computed`, so Vue sees a single stable HTML string. No double render. |
| `scope="pending"` concurrent double-click races two LLM invocations | Low | FR-36 disables the button during active job. Cross-tab edge case accepted (spec §12 "accepted risks"). |
| Content-aware `part_header` detection (<1000 chars) changes classification of borderline sections between re-imports | Low | Stub-merge already runs before the 1000-char gate; the band is 500–1000 chars where a "Part N" title with no real prose almost certainly *is* a divider. Boundary documented in E10. |
| Migration B runs while a user-owned default_summary_id points to an auto-batch summary (count>1 case with user-curated among batch rows) | Medium | FR-14 Python-side cutoff computation + re-point to newest non-batch row. Integration test T5 seeds this exact case with a 2-summary section to cover it. |
| SSE backward-compat: existing tests that parse event payloads without `section_id` | Low | `section_id` is additive; no existing test asserts *absence* of fields. Verified by running `uv run pytest -q` after T10 with no code changes downstream. |

---

## Rollback

Two Alembic revisions and no runtime schema changes. Standard downgrade chain:

- If T4 (Migration A) misbehaves post-deploy: `uv run alembic -c backend/app/migrations/alembic.ini downgrade <initial>` (no-op downgrade per FR-10 — data cannot be reconstructed; rolling back the code plus leaving the rewritten URLs is acceptable since they are still valid resolvable URLs).
- If T5 (Migration B) misbehaves: `alembic downgrade <migration-A-hash>` (no-op per FR-16; auto-summaries that were pruned remain pruned; the next `upgrade head` on corrected code re-classifies any still-miscategorized rows).
- If T9/T10 ships with a scope bug that corrupts `default_summary_id`: revert the offending commit; data is preserved because `summarize_book` only INSERTs summaries + UPDATEs `default_summary_id` (no DELETEs).
- Frontend-only regressions (T11–T19): `git revert` the specific commit; SPA is stateless, no migration concerns.

---

## Tasks

### T1: Create `section_classifier` module

**Goal:** Extract classification patterns + sets to a shared module that both parsers and Migration B will import.
**Spec refs:** FR-01, FR-02, FR-03, FR-06, FR-07, D3, D13

**Files:**
- Create: `backend/app/services/parser/section_classifier.py`
- Create: `backend/tests/unit/test_section_classifier.py`

**Steps:**

- [ ] Step 1: Write the failing test file
  ```python
  # backend/tests/unit/test_section_classifier.py
  import pytest
  from app.services.parser.section_classifier import (
      FRONT_MATTER_TYPES,
      SUMMARIZABLE_TYPES,
      detect_section_type,
  )

  @pytest.mark.parametrize("title,content_md,expected", [
      # New front-matter patterns (FR-02)
      ("Copyright", "", "copyright"),
      ("© 2021 ...", "", "copyright"),
      ("Acknowledgments", "", "acknowledgments"),
      ("Acknowledgements", "", "acknowledgments"),
      ("Dedication", "", "dedication"),
      ("Title Page", "", "title_page"),
      ("Table of Contents", "", "table_of_contents"),
      ("Contents", "", "table_of_contents"),
      ("Contents of Chapter 1", "", "chapter"),      # anchored — negative
      ("What This Book Contains", "", "chapter"),    # negative
      ("Colophon", "", "colophon"),
      ("Cover", "", "cover"),
      ("Book Cover", "", "cover"),
      ("Discover", "", "chapter"),                    # negative (anchored)
      # Part header content-aware (FR-03)
      ("Part One", "short intro", "part_header"),
      ("Part 3", "", "part_header"),
      ("Part One: Foundations", "x" * 1500, "chapter"),
      ("Part One", "x" * 1000, "chapter"),            # E10 boundary: 1000 strict
      ("Part One", "x" * 999, "part_header"),
      # Pre-existing patterns still work, and front-matter wins order (FR-07)
      ("Introduction to Copyright", "", "copyright"),
      ("Introduction", "", "introduction"),
      ("Glossary", "", "glossary"),
      # Default fallback
      ("Chapter 1: The Right Mindset", "", "chapter"),
      ("Random Title", "", "chapter"),
      ("", "", "chapter"),
  ])
  def test_detect_section_type(title, content_md, expected):
      assert detect_section_type(title, content_md) == expected

  def test_front_matter_types_set():
      assert FRONT_MATTER_TYPES == {
          "copyright", "acknowledgments", "dedication", "title_page",
          "table_of_contents", "colophon", "cover", "part_header",
      }

  def test_summarizable_types_set():
      assert SUMMARIZABLE_TYPES == {
          "chapter", "introduction", "preface", "foreword", "epilogue", "conclusion",
      }

  def test_front_matter_and_summarizable_disjoint():
      assert FRONT_MATTER_TYPES.isdisjoint(SUMMARIZABLE_TYPES)

  def test_none_content_md_treated_as_empty():
      assert detect_section_type("Part One", None) == "part_header"
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/unit/test_section_classifier.py -v`
  Expected: `ModuleNotFoundError: No module named 'app.services.parser.section_classifier'`

- [ ] Step 3: Implement the module
  ```python
  # backend/app/services/parser/section_classifier.py
  """Shared section-type classifier used by all parsers and Migration B.

  Pattern-order contract (FR-07, D13): front-matter patterns are evaluated
  before content-body patterns. First match wins. Python 3.7+ dict ordering
  is insertion-ordered by guarantee.

  Content-aware note (FR-03): `part_header` requires BOTH a title match
  AND `len(content_md or "") < 1000`. `len(content_md)` counts markdown
  syntax; the ±50-char overhead does not flip the 1000-char decision
  in realistic content.

  Frontend mirror: `frontend/src/stores/reader.ts` exports the same two
  set constants. A cross-layer contract test in
  `tests/unit/test_section_type_sets_contract.py` enforces equality.
  """
  from __future__ import annotations
  import re

  # Order matters. Front-matter first, then body content types.
  SECTION_TYPE_PATTERNS: dict[str, re.Pattern] = {
      "copyright":         re.compile(r"\bcopyright\b|©", re.IGNORECASE),
      "acknowledgments":   re.compile(r"\backnowledg(e)?ments?\b", re.IGNORECASE),
      "dedication":        re.compile(r"\bdedication\b", re.IGNORECASE),
      "title_page":        re.compile(r"\btitle\s*page\b", re.IGNORECASE),
      "table_of_contents": re.compile(r"^(table\s+of\s+contents|contents)\s*$", re.IGNORECASE),
      "colophon":          re.compile(r"\bcolophon\b", re.IGNORECASE),
      "cover":             re.compile(r"^cover$|^book\s*cover$", re.IGNORECASE),
      "part_header":       re.compile(
          r"^part\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b",
          re.IGNORECASE,
      ),
      # Pre-existing body patterns (unchanged)
      "glossary":      re.compile(r"\bglossary\b", re.IGNORECASE),
      "notes":         re.compile(r"\b(end\s*notes?|chapter\s*notes?|notes?)\b", re.IGNORECASE),
      "appendix":      re.compile(r"\bappendix\b", re.IGNORECASE),
      "bibliography":  re.compile(r"\b(bibliography|works?\s+cited|references)\b", re.IGNORECASE),
      "index":         re.compile(r"\bindex\b", re.IGNORECASE),
      "about_author":  re.compile(r"\babout\s+the\s+author\b", re.IGNORECASE),
      "foreword":      re.compile(r"\bforeword\b", re.IGNORECASE),
      "preface":       re.compile(r"\bpreface\b", re.IGNORECASE),
      "introduction": re.compile(r"\bintroduction\b", re.IGNORECASE),
      "epilogue":      re.compile(r"\bepilogue\b", re.IGNORECASE),
      "conclusion":    re.compile(r"\bconclusion\b", re.IGNORECASE),
  }

  FRONT_MATTER_TYPES: frozenset[str] = frozenset({
      "copyright", "acknowledgments", "dedication", "title_page",
      "table_of_contents", "colophon", "cover", "part_header",
  })

  SUMMARIZABLE_TYPES: frozenset[str] = frozenset({
      "chapter", "introduction", "preface", "foreword", "epilogue", "conclusion",
  })


  def detect_section_type(title: str, content_md: str | None = None) -> str:
      """Classify a section by its title, with content-aware gate for part_header.

      Returns the first matching pattern's key, else "chapter". If a title
      matches `part_header` but `len(content_md or "") >= 1000`, returns
      "chapter" instead (content-aware override per FR-03).
      """
      if not title:
          return "chapter"
      for section_type, pattern in SECTION_TYPE_PATTERNS.items():
          if pattern.search(title):
              if section_type == "part_header" and len(content_md or "") >= 1000:
                  return "chapter"
              return section_type
      return "chapter"
  ```

  Change assertions in step 1 to match: replace `set(...)` with `frozenset(...)` OR leave as-is (frozenset equals set under `==`). Keep as `==` on plain set literals — `frozenset == set` is True in Python.

- [ ] Step 4: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_section_classifier.py -v`
  Expected: 27+ passed (count = parametrize rows + 4 standalone tests)

- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/parser/section_classifier.py backend/tests/unit/test_section_classifier.py
  git commit -m "feat(parser): shared section_classifier module with front-matter types"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/parser/section_classifier.py tests/unit/test_section_classifier.py` — 0 errors
- `cd backend && uv run python -m pytest tests/unit/test_section_classifier.py -v` — all passed
- `cd backend && uv run python -c "from app.services.parser.section_classifier import detect_section_type; print(detect_section_type('Copyright', ''))"` → `copyright`

---

### T2: Wire EPUB parser to shared classifier

**Goal:** Replace `EPUBParser._detect_section_type` with imports from the new module; pass `content_md` to the classifier at both call sites.
**Spec refs:** FR-01, FR-04, D3

**Files:**
- Modify: `backend/app/services/parser/epub_parser.py` (remove lines 16-41 + :313, :375 callsites)
- Modify: `backend/tests/unit/test_epub_parser.py` (or create a new focused test if none exists)

**Steps:**

- [ ] Step 1: Check whether `test_epub_parser.py` exists and how classification is currently exercised
  Run: `ls backend/tests/unit/ | grep epub`
  If exists: we will add; if not: create.

- [ ] Step 2: Write a failing test asserting EPUB parser delegates to the shared classifier
  ```python
  # backend/tests/unit/test_epub_parser_classifier_wiring.py
  from app.services.parser.epub_parser import EPUBParser

  def test_epub_parser_no_longer_defines_local_classifier():
      """EPUBParser._detect_section_type should be gone; module-level
      SECTION_TYPE_PATTERNS should be gone. Both are imported from
      section_classifier now."""
      import app.services.parser.epub_parser as mod
      assert not hasattr(EPUBParser, "_detect_section_type"), (
          "EPUBParser still defines _detect_section_type — must delegate to "
          "section_classifier.detect_section_type"
      )
      # SECTION_TYPE_PATTERNS may be re-exported or removed; what matters is
      # that the shared module is the source.
      from app.services.parser.section_classifier import SECTION_TYPE_PATTERNS as shared
      local = getattr(mod, "SECTION_TYPE_PATTERNS", None)
      if local is not None:
          assert local is shared, "local SECTION_TYPE_PATTERNS must be a re-export"

  def test_epub_parser_add_section_passes_content_md_to_classifier(monkeypatch):
      """_add_section must call detect_section_type(title, content_md), not just title."""
      captured = []

      def fake_detect(title, content_md=None):
          captured.append((title, content_md))
          return "chapter"

      monkeypatch.setattr(
          "app.services.parser.epub_parser.detect_section_type", fake_detect
      )
      parser = EPUBParser()

      class FakeEntry:
          href = "part-1.xhtml"
          title = "Part One"

      sections = []
      order = [0]
      parser._add_section(
          FakeEntry(),
          content_map={"part-1.xhtml": "short content"},
          image_map={},
          sections=sections,
          order_counter=order,
          depth=0,
      )
      assert captured, "detect_section_type was not called"
      title, content_md = captured[0]
      assert title == "Part One"
      assert content_md == "short content"
  ```

- [ ] Step 3: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/unit/test_epub_parser_classifier_wiring.py -v`
  Expected: FAIL — `_detect_section_type` still defined on EPUBParser + wrong arg to classifier.

- [ ] Step 4: Modify `backend/app/services/parser/epub_parser.py`
  - Delete lines 16–28 (the local `SECTION_TYPE_PATTERNS`).
  - Delete the `_detect_section_type` @staticmethod (lines 35–41).
  - Add import at top: `from app.services.parser.section_classifier import detect_section_type`.
  - Replace the `self._detect_section_type(spine_title)` call at line 313 with `detect_section_type(spine_title, content)`.
  - Replace the `self._detect_section_type(effective_title)` call at line 375 with `detect_section_type(effective_title, content)` (the local `content` variable is available from line 355 in `_add_section`).

- [ ] Step 5: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_epub_parser_classifier_wiring.py tests/unit/test_section_classifier.py -v`
  Then run the full epub parser test file to check no regressions: `uv run python -m pytest tests/unit/ -k "epub" -v`
  Expected: all passed.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/services/parser/epub_parser.py backend/tests/unit/test_epub_parser_classifier_wiring.py
  git commit -m "refactor(parser): EPUB parser delegates to shared section_classifier"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/services/parser/epub_parser.py` — 0 errors
- `cd backend && uv run python -m pytest tests/unit/ -k "epub or classifier" -v` — all passed

---

### T3: Wire PDF parser to shared classifier

**Goal:** PDF-derived sections get classified via `detect_section_type(title, content_md)` instead of defaulting to `"chapter"`.
**Spec refs:** FR-05, D3, D12

**Files:**
- Modify: `backend/app/services/parser/pdf_parser.py` (both `_pages_to_sections` and `_chunk_by_pages`)
- Create: `backend/tests/unit/test_pdf_parser_section_types.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  # backend/tests/unit/test_pdf_parser_section_types.py
  from app.services.parser.pdf_parser import PDFParser

  def test_pdf_parser_pages_to_sections_classifies_titles():
      parser = PDFParser()
      pages = [
          {"text": "# Copyright\n© 2023 ...", "images": []},
          {"text": "# Introduction\nThis book explores ...", "images": []},
          {"text": "# The Mindset Shift\nchapter body", "images": []},
      ]
      sections = parser._pages_to_sections(pages)
      titles_to_types = {s.title: s.section_type for s in sections}
      assert titles_to_types.get("Copyright") == "copyright"
      assert titles_to_types.get("Introduction") == "introduction"
      assert titles_to_types.get("The Mindset Shift") == "chapter"

  def test_pdf_parser_chunk_by_pages_classifies_default_to_chapter():
      parser = PDFParser()
      pages = [{"text": "body text " * 20, "images": []} for _ in range(12)]
      sections = parser._chunk_by_pages(pages, pages_per_section=5)
      # Default titles like "Pages 1-5" contain no classifier keywords → chapter
      assert all(s.section_type == "chapter" for s in sections)
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/unit/test_pdf_parser_section_types.py -v`
  Expected: `AttributeError` or default `"chapter"` (existing), with the `Introduction` assertion failing.

- [ ] Step 3: Modify `backend/app/services/parser/pdf_parser.py`
  - Import: `from app.services.parser.section_classifier import detect_section_type`
  - In `_pages_to_sections`, when a `ParsedSection` is appended (two places — the mid-loop append at line 87 and the tail append at line 107), pass `section_type=detect_section_type(current_title, content)`.
  - In `_chunk_by_pages`, same: `section_type=detect_section_type(f"Pages {i+1}-...", content)` at line 170.

- [ ] Step 4: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_pdf_parser_section_types.py -v`
  Expected: 2 passed.

- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/parser/pdf_parser.py backend/tests/unit/test_pdf_parser_section_types.py
  git commit -m "feat(parser): PDF parser delegates to shared section_classifier"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/ -k "parser" -v` — all passed
- `cd backend && uv run ruff check app/services/parser/pdf_parser.py` — clean

---

### T4: Migration A — backfill image placeholders

**Goal:** Rewrite legacy `__IMG_PLACEHOLDER__:…__ENDIMG__` tokens in `book_sections.content_md` to `/api/v1/images/{id}` URLs on next startup.
**Spec refs:** FR-08, FR-09, FR-10, FR-11, FR-12

**Files:**
- Create: `backend/app/migrations/versions/<hash>_backfill_image_placeholders.py`
- Create: `backend/tests/integration/test_migration_image_placeholders.py`

**Steps:**

- [ ] Step 1: Generate revision skeleton
  Run: `cd backend && uv run alembic -c app/migrations/alembic.ini revision -m "backfill image placeholders"`
  Expected: new file in `backend/app/migrations/versions/` with a fresh hash. Note the filename; rename the file to `<hash>_backfill_image_placeholders.py` for readability.

- [ ] Step 2: Write the integration test first
  ```python
  # backend/tests/integration/test_migration_image_placeholders.py
  import subprocess
  from pathlib import Path
  import pytest
  import sqlalchemy as sa
  from sqlalchemy.orm import Session

  def test_migration_rewrites_placeholders(tmp_path, monkeypatch):
      """Seed a pre-migration DB, run `alembic upgrade head`, assert rewrites."""
      # Use a fresh file-based sqlite for migration testing
      db_path = tmp_path / "library.db"
      db_url = f"sqlite:///{db_path}"
      monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", db_url)

      # Run migrations up to the revision BEFORE Migration A
      from alembic.command import upgrade, downgrade
      from alembic.config import Config
      cfg = Config(str(Path(__file__).parent.parent.parent / "app/migrations/alembic.ini"))
      upgrade(cfg, "head")  # Get full schema

      # Seed: insert a book + section + image with legacy placeholder
      engine = sa.create_engine(db_url)
      with engine.begin() as conn:
          conn.execute(sa.text("""
              INSERT INTO books (id, title, file_data, file_hash, file_format,
                                 file_size_bytes, status)
              VALUES (1, 'Test', x'00', 'hash1', 'epub', 1, 'COMPLETED')
          """))
          conn.execute(sa.text("""
              INSERT INTO book_sections (id, book_id, title, order_index, section_type,
                                         content_md)
              VALUES (1, 1, 'Ch1', 0, 'chapter',
                      '![alt](__IMG_PLACEHOLDER__:foo.jpg__ENDIMG__)
                       and ![](__IMG_PLACEHOLDER__:bar.png__ENDIMG__)')
          """))
          conn.execute(sa.text("""
              INSERT INTO images (id, section_id, data, mime_type, filename)
              VALUES (10, 1, x'00', 'image/jpeg', 'foo.jpg'),
                     (11, 1, x'00', 'image/png',  'bar.png')
          """))

      # Simulate the migration having NOT run for these rows: downgrade this
      # revision only, then re-upgrade head to apply it.
      downgrade(cfg, "-1")
      upgrade(cfg, "head")

      with engine.begin() as conn:
          row = conn.execute(
              sa.text("SELECT content_md FROM book_sections WHERE id=1")
          ).scalar_one()
      assert "__IMG_PLACEHOLDER__" not in row
      assert "/api/v1/images/10" in row
      assert "/api/v1/images/11" in row

      # Idempotent: re-upgrade produces no further changes
      upgrade(cfg, "head")
      with engine.begin() as conn:
          row2 = conn.execute(
              sa.text("SELECT content_md FROM book_sections WHERE id=1")
          ).scalar_one()
      assert row2 == row

  def test_migration_skips_section_without_images(tmp_path, monkeypatch):
      """FR-12 false-positive safety: section without matching images untouched."""
      db_path = tmp_path / "library.db"
      monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite:///{db_path}")
      from alembic.command import upgrade
      from alembic.config import Config
      cfg = Config(str(Path(__file__).parent.parent.parent / "app/migrations/alembic.ini"))
      upgrade(cfg, "head")
      engine = sa.create_engine(f"sqlite:///{db_path}")
      with engine.begin() as conn:
          conn.execute(sa.text("""
              INSERT INTO books (id, title, file_data, file_hash, file_format,
                                 file_size_bytes, status)
              VALUES (1, 'Test', x'00', 'hash1', 'epub', 1, 'COMPLETED')
          """))
          conn.execute(sa.text("""
              INSERT INTO book_sections (id, book_id, title, order_index, section_type,
                                         content_md)
              VALUES (1, 1, 'Ch1', 0, 'chapter',
                      '![](__IMG_PLACEHOLDER__:missing.jpg__ENDIMG__)')
          """))
      # Re-run head (already at head — should be no-op for Migration A too)
      upgrade(cfg, "head")
      with engine.begin() as conn:
          row = conn.execute(
              sa.text("SELECT content_md FROM book_sections WHERE id=1")
          ).scalar_one()
      # Placeholder untouched because no image row matches filename
      assert "__IMG_PLACEHOLDER__:missing.jpg__ENDIMG__" in row
  ```

- [ ] Step 3: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/integration/test_migration_image_placeholders.py -v`
  Expected: FAIL (no rewrites because migration body is empty skeleton).

- [ ] Step 4: Implement the migration body
  ```python
  # backend/app/migrations/versions/<hash>_backfill_image_placeholders.py
  """backfill image placeholders

  Revision ID: <new-hash>
  Revises: e152941ea209
  Create Date: 2026-04-19 ...
  """
  from collections.abc import Sequence
  import structlog
  import sqlalchemy as sa
  from alembic import op

  from app.services.parser.image_url_rewrite import from_placeholder

  revision: str = "<new-hash>"
  down_revision: str | None = "e152941ea209"
  branch_labels: str | Sequence[str] | None = None
  depends_on: str | Sequence[str] | None = None

  log = structlog.get_logger()


  def upgrade() -> None:
      conn = op.get_bind()

      # FR-08: only process rows containing both ends of the placeholder token.
      rows = conn.execute(sa.text("""
          SELECT id, book_id, content_md
            FROM book_sections
           WHERE content_md LIKE '%\\_\\_IMG\\_PLACEHOLDER\\_\\_:%\\_\\_ENDIMG\\_\\_' ESCAPE '\\'
      """)).fetchall()

      by_section = 0
      for row in rows:
          img_rows = conn.execute(
              sa.text("SELECT id, filename FROM images WHERE section_id = :sid"),
              {"sid": row.id},
          ).fetchall()
          fn_map = {ir.filename: ir.id for ir in img_rows if ir.filename}
          if not fn_map:
              continue  # FR-12: nothing to substitute; leave placeholder intact
          new_md = from_placeholder(row.content_md, fn_map)
          if new_md != row.content_md:
              conn.execute(
                  sa.text("UPDATE book_sections SET content_md = :md WHERE id = :id"),
                  {"md": new_md, "id": row.id},
              )
              by_section += 1
      log.info("migration_image_placeholders_complete", rewritten=by_section)


  def downgrade() -> None:
      log.info("migration_image_placeholders_downgrade_noop")
  ```

  Note on the LIKE pattern: SQLite's default LIKE has no escape char; the
  `ESCAPE '\'` clause makes `\_` match a literal underscore instead of
  "any single character", so the filter only catches strings containing
  the actual token pair — not unrelated double-underscore content.

- [ ] Step 5: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/integration/test_migration_image_placeholders.py -v`
  Expected: 2 passed.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/migrations/versions/*backfill_image_placeholders.py \
           backend/tests/integration/test_migration_image_placeholders.py
  git commit -m "feat(migration): backfill legacy image placeholders on startup"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/integration/test_migration_image_placeholders.py -v` — 2 passed
- `cd backend && uv run alembic -c app/migrations/alembic.ini heads` — shows the new hash as head (or co-head temporarily, which is OK)

---

### T5: Migration B — reclassify sections + prune auto summaries

**Goal:** Re-run the classifier against every existing section and, for sections that became front-matter, prune auto-generated summaries while preserving user-curated ones.
**Spec refs:** FR-13, FR-14, FR-15, FR-16, FR-17, FR-18, FR-18a, D5, E1, E8

**Files:**
- Create: `backend/app/migrations/versions/<hash>_reclassify_sections_and_prune_frontmatter.py`
- Create: `backend/tests/integration/test_migration_reclassify_sections.py`

**Steps:**

- [ ] Step 1: Generate revision skeleton
  Run: `cd backend && uv run alembic -c app/migrations/alembic.ini revision -m "reclassify sections and prune frontmatter"`
  Update `down_revision` to the T4 revision hash.

- [ ] Step 2: Write failing integration test
  ```python
  # backend/tests/integration/test_migration_reclassify_sections.py
  from pathlib import Path
  from datetime import datetime, timedelta
  import sqlalchemy as sa
  from alembic.command import upgrade, downgrade
  from alembic.config import Config

  def _seed(conn):
      # Book 1: 5 sections with mixed types
      conn.execute(sa.text("""
          INSERT INTO books (id, title, file_data, file_hash, file_format,
                             file_size_bytes, status)
          VALUES (1, 'T', x'00', 'h1', 'epub', 1, 'COMPLETED')
      """))
      conn.execute(sa.text("""
          INSERT INTO book_sections (id, book_id, title, order_index,
                                     section_type, content_md)
          VALUES
            (1, 1, 'Copyright', 0, 'chapter', '© 2024 ...'),
            (2, 1, 'Acknowledgments', 1, 'chapter', 'Thanks to ...'),
            (3, 1, 'Part One', 2, 'chapter', 'short'),
            (4, 1, 'Chapter 1: Right Mindset', 3, 'chapter', 'real chapter body...'),
            (5, 1, 'Glossary', 4, 'chapter', 'terms and defs ...')
      """))
      now = datetime.utcnow()
      # Auto-batch of 5 summaries created within a ~1-second window
      for sid, offset in [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4)]:
          conn.execute(sa.text("""
              INSERT INTO summaries (id, content_type, content_id, book_id,
                                     facets_used, prompt_text_sent, model_used,
                                     input_char_count, summary_char_count, summary_md,
                                     created_at)
              VALUES (:id, 'section', :cid, 1, '{}', 'p', 'm',
                      10, 5, 's', :ts)
          """), {"id": 100 + sid, "cid": sid, "ts": now + timedelta(seconds=offset)})
      # User-curated extra summary for Acknowledgments (section 2), older by 2 minutes
      conn.execute(sa.text("""
          INSERT INTO summaries (id, content_type, content_id, book_id,
                                 facets_used, prompt_text_sent, model_used,
                                 input_char_count, summary_char_count, summary_md,
                                 created_at)
          VALUES (999, 'section', 2, 1, '{}', 'p', 'm',
                  10, 5, 's', :ts)
      """), {"ts": now - timedelta(minutes=2)})
      # default_summary_id set for all sections
      for sid, did in [(1, 101), (2, 102), (3, 103), (4, 104), (5, 105)]:
          conn.execute(sa.text(
              "UPDATE book_sections SET default_summary_id = :d WHERE id = :s"
          ), {"d": did, "s": sid})

  def test_migration_reclassifies_and_prunes(tmp_path, monkeypatch):
      db_path = tmp_path / "library.db"
      monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite:///{db_path}")
      cfg = Config(str(Path(__file__).parent.parent.parent / "app/migrations/alembic.ini"))
      upgrade(cfg, "head")  # full schema

      engine = sa.create_engine(f"sqlite:///{db_path}")
      with engine.begin() as conn:
          _seed(conn)

      # Roll Migration B back, then re-apply on the seeded data
      downgrade(cfg, "-1")
      upgrade(cfg, "head")

      with engine.begin() as conn:
          types = {
              r.id: r.section_type
              for r in conn.execute(sa.text(
                  "SELECT id, section_type FROM book_sections ORDER BY id"
              ))
          }
          defaults = {
              r.id: r.default_summary_id
              for r in conn.execute(sa.text(
                  "SELECT id, default_summary_id FROM book_sections ORDER BY id"
              ))
          }
          summary_count = conn.execute(sa.text(
              "SELECT content_id, count(*) c FROM summaries "
              "WHERE content_type='section' GROUP BY content_id"
          )).fetchall()
          by_section = {r.content_id: r.c for r in summary_count}

      # FR-13: reclassified
      assert types == {
          1: "copyright",
          2: "acknowledgments",
          3: "part_header",
          4: "chapter",
          5: "glossary",
      }

      # FR-14: Copyright (1 auto summary) → summary deleted + default null
      assert by_section.get(1, 0) == 0
      assert defaults[1] is None

      # Acknowledgments (2 summaries, user-curated) → both preserved;
      # default re-pointed to the older (pre-batch) user-curated row 999
      assert by_section.get(2, 0) == 2
      assert defaults[2] == 999

      # Part One (part_header, 1 auto summary) → pruned
      assert by_section.get(3, 0) == 0
      assert defaults[3] is None

      # Chapter 1 (chapter, 1 summary) → unchanged
      assert types[4] == "chapter"
      assert defaults[4] == 104

      # Glossary → summary preserved (not front-matter)
      assert by_section.get(5, 0) == 1
      assert defaults[5] == 105

      # FR-17: re-running produces zero changes
      upgrade(cfg, "head")
      with engine.begin() as conn:
          types2 = {
              r.id: r.section_type
              for r in conn.execute(sa.text(
                  "SELECT id, section_type FROM book_sections ORDER BY id"
              ))
          }
      assert types2 == types
  ```

- [ ] Step 3: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/integration/test_migration_reclassify_sections.py -v`
  Expected: FAIL.

- [ ] Step 4: Implement migration body
  ```python
  # backend/app/migrations/versions/<hash>_reclassify_sections_and_prune_frontmatter.py
  """reclassify sections and prune frontmatter

  Revision ID: <new-hash>
  Revises: <T4-hash>
  """
  from collections.abc import Sequence
  from datetime import timedelta
  import structlog
  import sqlalchemy as sa
  from alembic import op

  from app.services.parser.section_classifier import (
      FRONT_MATTER_TYPES,
      detect_section_type,
  )

  revision: str = "<new-hash>"
  down_revision: str | None = "<T4-hash>"
  branch_labels: str | Sequence[str] | None = None
  depends_on: str | Sequence[str] | None = None

  log = structlog.get_logger()


  def upgrade() -> None:
      conn = op.get_bind()
      totals = {
          "reclassified": 0,
          "auto_summaries_pruned": 0,
          "user_summaries_preserved": 0,
          "books_affected": 0,
      }

      book_ids = [
          r.id for r in conn.execute(sa.text("SELECT id FROM books ORDER BY id"))
      ]

      for book_id in book_ids:
          rows = conn.execute(
              sa.text(
                  "SELECT id, title, content_md, section_type "
                  "FROM book_sections WHERE book_id = :b ORDER BY order_index"
              ),
              {"b": book_id},
          ).fetchall()

          per_book = {
              "reclassified": 0,
              "pruned": 0,
              "preserved": 0,
          }

          # Pre-compute batch cutoff for this book (FR-14)
          batch_end = conn.execute(
              sa.text(
                  "SELECT max(s.created_at) FROM summaries s "
                  "JOIN book_sections bs ON bs.id = s.content_id "
                  "WHERE s.content_type='section' AND bs.book_id = :b"
              ),
              {"b": book_id},
          ).scalar()
          cutoff = None
          if batch_end is not None:
              batch_end_dt = (
                  batch_end
                  if hasattr(batch_end, "timestamp")
                  else _parse_sqlite_timestamp(batch_end)
              )
              cutoff = batch_end_dt - timedelta(seconds=60)

          for row in rows:
              new_type = detect_section_type(row.title or "", row.content_md)
              if new_type == row.section_type:
                  continue

              conn.execute(
                  sa.text(
                      "UPDATE book_sections "
                      "SET section_type = :t, updated_at = CURRENT_TIMESTAMP "
                      "WHERE id = :id"
                  ),
                  {"t": new_type, "id": row.id},
              )
              per_book["reclassified"] += 1

              # FR-14: if NEW type is front-matter and OLD wasn't, apply summary rules
              if new_type in FRONT_MATTER_TYPES and row.section_type not in FRONT_MATTER_TYPES:
                  count = conn.execute(
                      sa.text(
                          "SELECT count(*) FROM summaries "
                          "WHERE content_type='section' AND content_id = :sid"
                      ),
                      {"sid": row.id},
                  ).scalar() or 0

                  if count == 1:
                      conn.execute(
                          sa.text(
                              "DELETE FROM summaries "
                              "WHERE content_type='section' AND content_id = :sid"
                          ),
                          {"sid": row.id},
                      )
                      conn.execute(
                          sa.text(
                              "UPDATE book_sections "
                              "SET default_summary_id = NULL WHERE id = :sid"
                          ),
                          {"sid": row.id},
                      )
                      per_book["pruned"] += 1
                  elif count > 1 and cutoff is not None:
                      newest_non_batch = conn.execute(
                          sa.text(
                              "SELECT id FROM summaries "
                              "WHERE content_type='section' AND content_id = :sid "
                              "  AND created_at < :cutoff "
                              "ORDER BY created_at DESC LIMIT 1"
                          ),
                          {"sid": row.id, "cutoff": cutoff},
                      ).scalar()
                      conn.execute(
                          sa.text(
                              "UPDATE book_sections "
                              "SET default_summary_id = :new "
                              "WHERE id = :sid"
                          ),
                          {"new": newest_non_batch, "sid": row.id},
                      )
                      per_book["preserved"] += 1

          if per_book["reclassified"] > 0:
              totals["books_affected"] += 1
              totals["reclassified"] += per_book["reclassified"]
              totals["auto_summaries_pruned"] += per_book["pruned"]
              totals["user_summaries_preserved"] += per_book["preserved"]
              log.info("migration_reclassify_book", book_id=book_id, **per_book)

      log.info("migration_reclassify_complete", **totals)


  def downgrade() -> None:
      log.info("migration_reclassify_downgrade_noop")


  def _parse_sqlite_timestamp(value):
      """SQLite returns timestamps as strings under some drivers."""
      from datetime import datetime
      if isinstance(value, str):
          # Try the two common SQLite formats
          for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
              try:
                  return datetime.strptime(value, fmt)
              except ValueError:
                  continue
          raise ValueError(f"Unrecognized SQLite timestamp format: {value!r}")
      return value
  ```

- [ ] Step 5: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/integration/test_migration_reclassify_sections.py -v`
  Expected: 1 passed. If the timestamp format differs on your SQLite, adjust `_parse_sqlite_timestamp`.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/migrations/versions/*reclassify*.py \
           backend/tests/integration/test_migration_reclassify_sections.py
  git commit -m "feat(migration): reclassify sections and prune front-matter summaries"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/integration/test_migration_reclassify_sections.py -v` — passed
- `cd backend && uv run alembic -c app/migrations/alembic.ini history | head -20` — shows the T5 revision at head, chained off T4

---

### T6: Section response — `summary_md` + `is_summarizable`

**Goal:** `_build_section_response` returns `default_summary.summary_md` and a top-level `is_summarizable` boolean.
**Spec refs:** FR-19, FR-20, FR-21, FR-22

**Files:**
- Modify: `backend/app/api/schemas.py` (`SummaryBriefResponse`, `SectionResponse`)
- Modify: `backend/app/api/routes/sections.py` (`_build_section_response`)
- Create: `backend/tests/unit/test_sections_route_summary_md.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  # backend/tests/unit/test_sections_route_summary_md.py
  import pytest
  from httpx import AsyncClient

  @pytest.mark.asyncio
  async def test_section_response_includes_summary_md(client: AsyncClient, seeded_book_with_summary):
      book_id, section_id = seeded_book_with_summary
      r = await client.get(f"/api/v1/books/{book_id}/sections/{section_id}?include_content=true")
      assert r.status_code == 200
      body = r.json()
      assert body["default_summary"] is not None
      assert body["default_summary"]["summary_md"]
      assert isinstance(body["default_summary"]["summary_md"], str)
      assert len(body["default_summary"]["summary_md"]) > 0
      assert body["is_summarizable"] is True   # seeded as 'chapter'

  @pytest.mark.asyncio
  async def test_section_response_is_summarizable_false_for_copyright(client, seeded_copyright_section):
      book_id, section_id = seeded_copyright_section
      r = await client.get(f"/api/v1/books/{book_id}/sections/{section_id}")
      assert r.status_code == 200
      assert r.json()["is_summarizable"] is False

  @pytest.mark.asyncio
  async def test_section_response_handles_dangling_default_summary_id(client, seeded_dangling_summary):
      """FR-22: 404 summary row yields default_summary=null, not an error."""
      book_id, section_id = seeded_dangling_summary
      r = await client.get(f"/api/v1/books/{book_id}/sections/{section_id}")
      assert r.status_code == 200
      assert r.json()["default_summary"] is None
  ```

  Add fixtures to `tests/conftest.py` (or the nearest shared fixtures file) — follow the pattern of existing API test fixtures in `tests/unit/` for session + client setup.

- [ ] Step 2: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/unit/test_sections_route_summary_md.py -v`
  Expected: FAIL on missing `summary_md` / `is_summarizable` fields.

- [ ] Step 3: Update schemas
  ```python
  # schemas.py — SummaryBriefResponse
  class SummaryBriefResponse(BaseModel):
      model_config = ConfigDict(from_attributes=True)
      id: int
      preset_name: str | None = None
      model_used: str
      summary_char_count: int
      created_at: datetime
      summary_md: str | None = None   # NEW (FR-21)

  # schemas.py — SectionResponse add one field
  class SectionResponse(BaseModel):
      # ... existing fields ...
      is_summarizable: bool = True   # NEW (FR-20)
  ```

- [ ] Step 4: Update `_build_section_response`
  ```python
  # sections.py
  from app.services.parser.section_classifier import SUMMARIZABLE_TYPES
  # ...

  if has_summary:
      result = await db.execute(select(Summary).where(Summary.id == section.default_summary_id))
      summary = result.scalar_one_or_none()
      if summary:
          default_summary = SummaryBriefResponse(
              id=summary.id,
              preset_name=summary.preset_name,
              model_used=summary.model_used,
              summary_char_count=summary.summary_char_count,
              created_at=summary.created_at,
              summary_md=summary.summary_md,   # NEW
          ).model_dump()

  # ... before return, build is_summarizable
  is_summarizable = section.section_type in SUMMARIZABLE_TYPES

  return {
      # ... existing fields ...
      "is_summarizable": is_summarizable,
  }
  ```

- [ ] Step 5: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_sections_route_summary_md.py -v`
  Expected: 3 passed.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/api/schemas.py backend/app/api/routes/sections.py \
           backend/tests/unit/test_sections_route_summary_md.py
  git commit -m "feat(api): section response includes summary_md + is_summarizable"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/ -k "section" -v` — all passed
- `curl -s http://localhost:8000/api/v1/books/1/sections/4?include_content=true | jq '.default_summary.summary_md, .is_summarizable'` (manual, after backend restart) — non-null string + true/false

---

### T7: Book response — `summary_progress`

**Goal:** `GET /api/v1/books/{id}` returns `summary_progress = {summarized, total}` counting only summarizable-type sections.
**Spec refs:** FR-29, NFR-01a

**Files:**
- Modify: `backend/app/api/schemas.py` (`BookResponse`)
- Modify: `backend/app/api/routes/books.py` (`_book_to_response` + the one-off book GET at `:150`)
- Create: `backend/tests/unit/test_books_route_summary_progress.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  # backend/tests/unit/test_books_route_summary_progress.py
  import pytest
  from httpx import AsyncClient

  @pytest.mark.asyncio
  async def test_summary_progress_counts_only_summarizable_types(client: AsyncClient, seeded_mixed_book):
      """book has 5 sections: 1 copyright, 1 part_header, 3 chapter — of which 1 summarized."""
      book_id = seeded_mixed_book
      r = await client.get(f"/api/v1/books/{book_id}")
      assert r.status_code == 200
      sp = r.json()["summary_progress"]
      assert sp == {"summarized": 1, "total": 3}

  @pytest.mark.asyncio
  async def test_summary_progress_zero_when_no_summarizable_sections(client, seeded_reference_book):
      """Reference book with only glossary — total=0."""
      book_id = seeded_reference_book
      r = await client.get(f"/api/v1/books/{book_id}")
      assert r.status_code == 200
      assert r.json()["summary_progress"] == {"summarized": 0, "total": 0}
  ```

  Note: `glossary` is in neither `FRONT_MATTER_TYPES` nor `SUMMARIZABLE_TYPES` — it's a body-content type that's deliberately excluded from the progress denominator (spec §E2 rationale).

- [ ] Step 2: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/unit/test_books_route_summary_progress.py -v`
  Expected: FAIL — field missing.

- [ ] Step 3: Update schema
  ```python
  # schemas.py
  class BookResponse(BaseModel):
      # ... existing fields ...
      summary_progress: dict[str, int] | None = None
  ```

- [ ] Step 4: Update `_book_to_response` + the `get_book` route
  ```python
  # books.py
  from sqlalchemy import func
  from app.db.models import BookSection
  from app.services.parser.section_classifier import SUMMARIZABLE_TYPES

  async def _summary_progress(db, book_id: int) -> dict:
      summarizable_list = list(SUMMARIZABLE_TYPES)
      total = (await db.execute(
          select(func.count(BookSection.id))
          .where(BookSection.book_id == book_id)
          .where(BookSection.section_type.in_(summarizable_list))
      )).scalar() or 0
      summarized = (await db.execute(
          select(func.count(BookSection.id))
          .where(BookSection.book_id == book_id)
          .where(BookSection.section_type.in_(summarizable_list))
          .where(BookSection.default_summary_id.isnot(None))
      )).scalar() or 0
      return {"summarized": summarized, "total": total}

  # In get_book (line 150):
  book_dict = _book_to_response(book)
  book_dict["summary_progress"] = await _summary_progress(db, book_id)
  return BookResponse(**book_dict)
  ```

  Leave `list_books` untouched — `summary_progress` lives on the detail response only (book list already has `has_summary` for coarse indication, and FR-29 scopes the field to the detail shape).

- [ ] Step 5: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_books_route_summary_progress.py -v`
  Expected: 2 passed.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/api/schemas.py backend/app/api/routes/books.py \
           backend/tests/unit/test_books_route_summary_progress.py
  git commit -m "feat(api): book response includes summary_progress counter"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/ -k "book" -v` — all passed
- `curl -s http://localhost:8000/api/v1/books/1 | jq '.summary_progress'` (manual) → `{"summarized": N, "total": M}`

---

### T8: `ProcessingStartRequest` — `scope` + `section_id` + route validation

**Goal:** The request schema accepts `scope` and `section_id`; the route validates the combinations and rejects invalid requests.
**Spec refs:** FR-23, FR-24, FR-27

**Files:**
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes/processing.py:27-60`
- Create: `backend/tests/unit/test_summarize_scope_validation.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  # backend/tests/unit/test_summarize_scope_validation.py
  import pytest
  from httpx import AsyncClient

  @pytest.mark.asyncio
  async def test_scope_section_requires_section_id(client: AsyncClient, seeded_book):
      r = await client.post(f"/api/v1/books/{seeded_book}/summarize",
                            json={"scope": "section"})
      assert r.status_code == 422
      assert "section_id" in r.json()["detail"]

  @pytest.mark.asyncio
  async def test_scope_section_wrong_book_returns_422(client, seeded_book, seeded_other_book_section_id):
      r = await client.post(f"/api/v1/books/{seeded_book}/summarize",
                            json={"scope": "section",
                                  "section_id": seeded_other_book_section_id})
      assert r.status_code == 422

  @pytest.mark.asyncio
  async def test_scope_pending_with_force_returns_400(client, seeded_book):
      """FR-27: mutually exclusive."""
      r = await client.post(f"/api/v1/books/{seeded_book}/summarize",
                            json={"scope": "pending", "force": True})
      assert r.status_code == 400

  @pytest.mark.asyncio
  async def test_scope_all_default_preserves_current_behavior(client, seeded_book):
      """Omitting scope is equivalent to scope='all' and must not 422."""
      r = await client.post(f"/api/v1/books/{seeded_book}/summarize", json={})
      assert r.status_code in (200, 202)
  ```

  Note the last test — the existing `start_processing` returns 200 with `{job_id}`. Don't change that.

- [ ] Step 2: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/unit/test_summarize_scope_validation.py -v`
  Expected: FAIL.

- [ ] Step 3: Update schema
  ```python
  # schemas.py
  from typing import Literal

  class ProcessingStartRequest(BaseModel):
      preset_name: str = "practitioner_bullets"
      run_eval: bool = True
      auto_retry: bool = True
      skip_eval: bool = False
      scope: Literal["all", "pending", "section"] = "all"
      section_id: int | None = None
      force: bool = False
  ```

  Note: if `force` doesn't currently exist on the schema (check the file), add it as `False` default. It's referenced by the summarizer but needs to be accepted at the route for FR-27 validation.

- [ ] Step 4: Update route validation in `processing.py`
  ```python
  # processing.py, after preset validation, before job creation
  if body.scope == "section":
      if body.section_id is None:
          raise HTTPException(status_code=422,
                              detail="scope='section' requires section_id")
      # Validate section_id belongs to this book
      section_row = (await db.execute(
          select(BookSection).where(
              BookSection.id == body.section_id,
              BookSection.book_id == book_id,
          )
      )).scalar_one_or_none()
      if section_row is None:
          raise HTTPException(
              status_code=422,
              detail=f"section_id={body.section_id} does not belong to book {book_id}",
          )
  if body.scope == "pending" and body.force:
      raise HTTPException(
          status_code=400,
          detail="scope='pending' is incompatible with force=true",
      )
  ```

  Import `BookSection` at the top.

- [ ] Step 5: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/unit/test_summarize_scope_validation.py -v`
  Expected: 4 passed.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/api/schemas.py backend/app/api/routes/processing.py \
           backend/tests/unit/test_summarize_scope_validation.py
  git commit -m "feat(api): summarize endpoint accepts scope + section_id"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/ -k "scope_validation" -v` — 4 passed
- `curl -sX POST http://localhost:8000/api/v1/books/1/summarize -d '{"scope":"section"}' -H 'content-type: application/json'` → 422

---

### T9: `SummarizerService.summarize_book` — scope filter + type gate

**Goal:** `summarize_book` accepts `scope` and `section_id`, filters the iteration set accordingly, and gates non-summarizable types (except when `scope="section"`).
**Spec refs:** FR-25, FR-26, FR-27, FR-27a

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py:40-239`
- Create: `backend/tests/integration/test_summarize_scope_pending.py`
- Create: `backend/tests/integration/test_summarize_scope_section.py`
- Create: `backend/tests/integration/test_summarize_nonsummarizable_skipped.py`

**Steps:**

- [ ] Step 1: Write failing tests (three files)
  ```python
  # test_summarize_scope_pending.py
  import pytest

  @pytest.mark.asyncio
  async def test_scope_pending_skips_already_summarized(summarizer, seeded_5_chapter_book_2_summarized, llm_stub):
      book_id = seeded_5_chapter_book_2_summarized
      result = await summarizer.summarize_book(book_id=book_id, scope="pending")
      assert result["completed"] == 3
      assert result["skipped"] == 2
      assert llm_stub.call_count == 3
  ```

  ```python
  # test_summarize_scope_section.py
  import pytest

  @pytest.mark.asyncio
  async def test_scope_section_summarizes_only_that_section(
      summarizer, seeded_5_chapter_book, llm_stub
  ):
      book_id, section_ids = seeded_5_chapter_book  # list of 5 ints
      target = section_ids[2]
      result = await summarizer.summarize_book(
          book_id=book_id, scope="section", section_id=target
      )
      assert result["completed"] == 1
      assert llm_stub.call_count == 1

  @pytest.mark.asyncio
  async def test_scope_section_wrong_book_raises(summarizer, seeded_two_books):
      book_a, (_, foreign_section_id) = seeded_two_books
      with pytest.raises(ValueError, match="does not belong"):
          await summarizer.summarize_book(
              book_id=book_a, scope="section", section_id=foreign_section_id
          )
  ```

  ```python
  # test_summarize_nonsummarizable_skipped.py
  import pytest

  @pytest.mark.asyncio
  async def test_all_scope_skips_frontmatter(
      summarizer, seeded_book_mixed_types, llm_stub
  ):
      """Book: 3 chapters + 2 copyright sections. scope='all' → only 3 summaries."""
      book_id = seeded_book_mixed_types
      result = await summarizer.summarize_book(book_id=book_id, scope="all")
      assert result["completed"] == 3
      assert llm_stub.call_count == 3

  @pytest.mark.asyncio
  async def test_section_scope_bypasses_type_gate(
      summarizer, seeded_book_mixed_types_section_ids, llm_stub
  ):
      """User explicitly invokes on a copyright section → runs anyway."""
      book_id, copyright_section_id = seeded_book_mixed_types_section_ids
      result = await summarizer.summarize_book(
          book_id=book_id, scope="section", section_id=copyright_section_id
      )
      assert result["completed"] == 1
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/integration/test_summarize_scope_pending.py tests/integration/test_summarize_scope_section.py tests/integration/test_summarize_nonsummarizable_skipped.py -v`
  Expected: FAIL (signature + filtering missing).

- [ ] Step 3: Update `summarize_book`
  ```python
  # summarizer_service.py
  from app.services.parser.section_classifier import SUMMARIZABLE_TYPES

  async def summarize_book(
      self,
      book_id: int,
      preset_name: str | None = None,
      facets: dict[str, str] | None = None,
      force: bool = False,
      model: str | None = None,
      skip_eval: bool = False,
      no_retry: bool = False,
      eval_service=None,
      on_section_start: Callable | None = None,   # NEW (used in T10)
      on_section_complete: Callable | None = None,
      on_section_skip: Callable | None = None,
      on_section_fail: Callable | None = None,
      on_section_retry: Callable | None = None,
      scope: str = "all",                          # NEW
      section_id: int | None = None,               # NEW
  ) -> dict:
      # ... existing facet-resolve block unchanged ...

      sections = await self._section_repo.get_by_book_id(book_id)

      # --- NEW: apply scope filter ---
      if scope == "section":
          if section_id is None:
              raise ValueError("scope='section' requires section_id")
          sections = [s for s in sections if s.id == section_id]
          if not sections:
              raise ValueError(
                  f"section_id={section_id} does not belong to book {book_id}"
              )
          # FR-26: user intent bypasses the summarizable-type gate
      elif scope == "pending":
          sections = [s for s in sections if s.default_summary_id is None]
          # FR-26: still filter out non-summarizable types
          sections = [s for s in sections if s.section_type in SUMMARIZABLE_TYPES]
      else:
          # scope == "all"
          sections = [s for s in sections if s.section_type in SUMMARIZABLE_TYPES]

      total = len(sections)

      # ... rest of existing loop unchanged ...
  ```

  Note: the existing skip-completed check (lines 80-95) still runs — it protects against facet-mismatched summaries and preserves cumulative-context semantics. The new filter just trims the candidate set earlier.

- [ ] Step 4: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/integration/test_summarize_scope_pending.py tests/integration/test_summarize_scope_section.py tests/integration/test_summarize_nonsummarizable_skipped.py -v`
  Expected: 5 passed.

- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/summarizer/summarizer_service.py \
           backend/tests/integration/test_summarize_scope_*.py \
           backend/tests/integration/test_summarize_nonsummarizable_skipped.py
  git commit -m "feat(summarizer): scope parameter + summarizable-type gate"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/integration/test_summarize_*.py -v` — all passed
- `cd backend && uv run python -m pytest -q` — no regressions vs baseline

---

### T10: SSE — `section_id` in payloads + `processing_started` + `section_started`

**Goal:** Backend emits `processing_started` and `section_started` events and includes `section_id` in every existing section event's payload.
**Spec refs:** FR-28, FR-28a, FR-28b

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py` (call `on_section_start` immediately before the LLM call)
- Modify: `backend/app/api/routes/processing.py:109-231`
- Create: `backend/tests/integration/test_summarize_sse_events.py`

**Steps:**

- [ ] Step 1: Write failing integration test
  ```python
  # backend/tests/integration/test_summarize_sse_events.py
  import asyncio
  import pytest

  @pytest.mark.asyncio
  async def test_sse_event_sequence_with_section_ids(
      client, seeded_2_chapter_book, llm_stub, event_bus_consumer
  ):
      book_id, section_ids = seeded_2_chapter_book
      # Start summarize
      r = await client.post(
          f"/api/v1/books/{book_id}/summarize", json={"scope": "all"}
      )
      assert r.status_code == 200
      job_id = r.json()["job_id"]

      events = []
      async with event_bus_consumer(job_id) as stream:
          async for ev in stream:
              events.append(ev)
              if ev["event"] == "processing_completed":
                  break
              if len(events) > 20:
                  break

      event_names = [e["event"] for e in events]
      assert event_names[0] == "processing_started"
      assert "processing_completed" == event_names[-1]

      # Every section event has a non-null section_id
      section_events = [e for e in events if e["event"].startswith("section_")]
      assert section_events  # at least one
      for ev in section_events:
          assert "section_id" in ev["data"], f"missing section_id in {ev}"
          assert ev["data"]["section_id"] in section_ids

      # Event ordering: processing_started → section_started → section_completed
      first_started = next(i for i, e in enumerate(events)
                           if e["event"] == "section_started")
      first_completed = next(i for i, e in enumerate(events)
                             if e["event"] == "section_completed")
      assert first_started < first_completed
  ```

  Note: `event_bus_consumer` is a new fixture that wraps `app.state.event_bus.subscribe()`. Add to `tests/conftest.py`:
  ```python
  @pytest.fixture
  async def event_bus_consumer(app):
      import contextlib
      @contextlib.asynccontextmanager
      async def _consumer(job_id: int):
          bus = app.state.event_bus
          queue = bus.subscribe(str(job_id))
          async def gen():
              while True:
                  ev = await queue.get()
                  if ev["event"] == "close":
                      return
                  yield ev
          try:
              yield gen()
          finally:
              bus.unsubscribe(str(job_id), queue)
      return _consumer
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd backend && uv run python -m pytest tests/integration/test_summarize_sse_events.py -v`
  Expected: FAIL — `processing_started` missing, `section_started` missing, `section_id` missing from completed payload.

- [ ] Step 3: Modify `summarizer_service.py` callback wiring
  In the loop inside `summarize_book`, before the `summary = await self._summarize_single_section(...)` call at line 124, add:
  ```python
  if on_section_start:
      on_section_start(section_id, i + 1, total, section_title)
  ```

  Also update all existing callback invocations (complete, skip, fail, retry) to pass `section_id` as the first positional argument. Edit each callback signature in the service if needed — but the cleanest approach is to leave the service callbacks with the richer signature and update the handlers in `processing.py` to accept both.

  The callbacks are local functions — match signatures like:
  ```python
  # complete
  if on_section_complete:
      on_section_complete(section.id, i + 1, total, section.title, elapsed, comp)
  # skip
  on_section_skip(section.id, i + 1, total, section.title, f"{char_count} chars < {min_chars} min")
  # fail
  on_section_fail(section_id, i + 1, total, section_title, error_msg)
  # retry
  on_section_retry(section.id, i + 1, total, section.title)
  ```

- [ ] Step 4: Modify `processing.py` event handlers
  ```python
  # processing.py — within _run_processing()
  def on_section_start(section_id, index, total, section_title):
      if event_bus:
          asyncio.create_task(event_bus.publish(str(job_id), "section_started", {
              "section_id": section_id,
              "title": section_title,
              "index": index,
              "total": total,
          }))

  def on_section_complete(section_id, index, total, section_title, elapsed=None, comp=None):
      if event_bus:
          asyncio.create_task(event_bus.publish(str(job_id), "section_completed", {
              "section_id": section_id,  # NEW
              "title": section_title,
              "index": index,
              "total": total,
              "elapsed_seconds": elapsed,
          }))

  def on_section_skip(section_id, index, total, section_title, reason):
      # ... add "section_id" key ...

  def on_section_fail(section_id, index, total, section_title, error):
      # ... add "section_id" key ...

  def on_section_retry(section_id, index, total, section_title):
      # ... add "section_id" key ...
  ```

  And emit `processing_started` once before calling `summarizer.summarize_book(...)`:
  ```python
  if event_bus:
      # Count total target sections now so UI can render a progress bar.
      # This is cheap — one filtered count aggregate.
      total_sections = len(await summarizer._section_repo.get_by_book_id(book_id))  # upper bound
      await event_bus.publish(str(job_id), "processing_started", {
          "book_id": book_id,
          "job_id": job_id,
          "total_sections": total_sections,
          "scope": body.scope,
      })
  ```

  Pass the new callback to the service:
  ```python
  result = await summarizer.summarize_book(
      book_id,
      preset_name=body.preset_name,
      scope=body.scope,
      section_id=body.section_id,
      skip_eval=skip_eval,
      no_retry=no_retry,
      eval_service=None if skip_eval else eval_svc,
      on_section_start=on_section_start,        # NEW
      on_section_complete=on_section_complete,
      on_section_skip=on_section_skip,
      on_section_fail=on_section_fail,
      on_section_retry=on_section_retry,
  )
  ```

- [ ] Step 5: Run and verify pass
  Run: `cd backend && uv run python -m pytest tests/integration/test_summarize_sse_events.py -v`
  Expected: 1 passed. Run the full suite to catch regressions on existing SSE tests: `uv run python -m pytest tests/ -k "sse or summarize or processing" -v` — expect none.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/services/summarizer/summarizer_service.py \
           backend/app/api/routes/processing.py \
           backend/tests/integration/test_summarize_sse_events.py
  git commit -m "feat(sse): section_id in all payloads + processing_started + section_started"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/ -k "sse" -v` — all passed
- `cd backend && uv run python -m pytest -q` — no regressions

---

### T11: Frontend — `processing.ts` extensions + `reader.ts` constants

**Goal:** TS API layer gains `scope`/`section_id` options + 4 new SSE handler slots; `reader.ts` exports the two set constants used by Front Matter partition + summarizability checks.
**Spec refs:** FR-30, FR-39a, FR-39b, FR-06a (mirror side)

**Files:**
- Modify: `frontend/src/api/processing.ts`
- Modify: `frontend/src/stores/reader.ts`
- Create: `frontend/src/api/__tests__/processing.spec.ts`
- Create: `frontend/src/stores/__tests__/reader.spec.ts` (landing-section tests land in T12; this file is created here for the constants test)

**Steps:**

- [ ] Step 1: Write failing test for `processing.ts`
  ```typescript
  // frontend/src/api/__tests__/processing.spec.ts
  import { describe, it, expect } from 'vitest'
  import type { ProcessingOptions, SSEHandlers } from '../processing'

  describe('ProcessingOptions', () => {
    it('accepts scope and section_id', () => {
      const opts: ProcessingOptions = {
        preset_name: 'practitioner_bullets',
        scope: 'section',
        section_id: 42,
      }
      expect(opts.scope).toBe('section')
    })
  })

  describe('SSEHandlers', () => {
    it('has four new handler slots', () => {
      const h: SSEHandlers = {
        onProcessingStarted: (d) => { void d.book_id },
        onSectionFailed: (d) => { void d.section_id; void d.error },
        onSectionSkipped: (d) => { void d.section_id; void d.reason },
        onSectionRetrying: (d) => { void d.section_id },
      }
      expect(h.onProcessingStarted).toBeDefined()
    })
  })
  ```

  (Type-only tests — they fail at compile time, which is what we want.)

- [ ] Step 2: Write failing test for `reader.ts` constants
  ```typescript
  // frontend/src/stores/__tests__/reader.spec.ts
  import { describe, it, expect } from 'vitest'
  import { FRONT_MATTER_TYPES, SUMMARIZABLE_TYPES } from '../reader'

  describe('reader constants', () => {
    it('exports FRONT_MATTER_TYPES matching backend', () => {
      expect(FRONT_MATTER_TYPES).toEqual(new Set([
        'copyright', 'acknowledgments', 'dedication', 'title_page',
        'table_of_contents', 'colophon', 'cover', 'part_header',
      ]))
    })
    it('exports SUMMARIZABLE_TYPES matching backend', () => {
      expect(SUMMARIZABLE_TYPES).toEqual(new Set([
        'chapter', 'introduction', 'preface', 'foreword', 'epilogue', 'conclusion',
      ]))
    })
    it('sets are disjoint', () => {
      for (const t of FRONT_MATTER_TYPES) {
        expect(SUMMARIZABLE_TYPES.has(t)).toBe(false)
      }
    })
  })
  ```

- [ ] Step 3: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run processing.spec.ts reader.spec.ts`
  Expected: FAIL (constants not exported; types missing).

- [ ] Step 4: Update `processing.ts`
  ```typescript
  // frontend/src/api/processing.ts
  export interface ProcessingOptions {
    preset_name?: string
    run_eval?: boolean
    auto_retry?: boolean
    skip_eval?: boolean
    force?: boolean
    scope?: 'all' | 'pending' | 'section'
    section_id?: number
  }

  export interface SSEHandlers {
    onProcessingStarted?: (data: { book_id: number; job_id: number; total_sections: number; scope: 'all' | 'pending' | 'section' }) => void
    onSectionStarted?:    (data: { section_id: number; title: string; index: number; total: number }) => void
    onSectionCompleted?:  (data: { section_id: number; title: string; index: number; total: number; elapsed_seconds?: number }) => void
    onSectionFailed?:     (data: { section_id: number; title: string; index: number; total: number; error: string }) => void
    onSectionSkipped?:    (data: { section_id: number; title: string; index: number; total: number; reason: string }) => void
    onSectionRetrying?:   (data: { section_id: number; title: string; index: number; total: number }) => void
    onProcessingCompleted?: (data: { book_id: number; completed: number; failed: number; skipped: number }) => void
    onProcessingFailed?:    (data: { book_id: number; error: string }) => void
    onError?: (error: Event) => void
  }

  export function connectSSE(jobId: number, handlers: SSEHandlers): EventSource {
    const source = new EventSource(`/api/v1/processing/${jobId}/stream`)
    const bind = <K extends keyof SSEHandlers>(event: string, key: K) => {
      const h = handlers[key] as ((d: unknown) => void) | undefined
      if (h) source.addEventListener(event, (e) => h(JSON.parse((e as MessageEvent).data)))
    }
    bind('processing_started',   'onProcessingStarted')
    bind('section_started',      'onSectionStarted')
    bind('section_completed',    'onSectionCompleted')
    bind('section_failed',       'onSectionFailed')
    bind('section_skipped',      'onSectionSkipped')
    bind('section_retrying',     'onSectionRetrying')
    if (handlers.onProcessingCompleted) {
      source.addEventListener('processing_completed', (e) => {
        handlers.onProcessingCompleted!(JSON.parse((e as MessageEvent).data))
        source.close()
      })
    }
    if (handlers.onProcessingFailed) {
      source.addEventListener('processing_failed', (e) => {
        handlers.onProcessingFailed!(JSON.parse((e as MessageEvent).data))
        source.close()
      })
    }
    if (handlers.onError) source.onerror = handlers.onError
    return source
  }
  ```

- [ ] Step 5: Update `reader.ts` constants
  ```typescript
  // frontend/src/stores/reader.ts — add near top, before the store definition:
  // NOTE: mirrors backend/app/services/parser/section_classifier.py:FRONT_MATTER_TYPES
  //       and :SUMMARIZABLE_TYPES. A contract test in
  //       backend/tests/unit/test_section_type_sets_contract.py fails if drift.
  export const FRONT_MATTER_TYPES: ReadonlySet<string> = new Set([
    'copyright', 'acknowledgments', 'dedication', 'title_page',
    'table_of_contents', 'colophon', 'cover', 'part_header',
  ])

  export const SUMMARIZABLE_TYPES: ReadonlySet<string> = new Set([
    'chapter', 'introduction', 'preface', 'foreword', 'epilogue', 'conclusion',
  ])
  ```

- [ ] Step 6: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run processing.spec.ts reader.spec.ts`
  Expected: all passed.

- [ ] Step 7: Commit
  ```bash
  git add frontend/src/api/processing.ts frontend/src/stores/reader.ts \
           frontend/src/api/__tests__/processing.spec.ts \
           frontend/src/stores/__tests__/reader.spec.ts
  git commit -m "feat(frontend): processing scope/section_id + reader classifier constants"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — clean
- `cd frontend && npm run test:unit -- --run processing reader` — all passed

---

### T12: Reader store — landing-section precedence + `updateSection`

**Goal:** `loadBook` computes the landing section per the 4-tier precedence; add `updateSection(section)` to splice updated sections into state on SSE `section_completed`.
**Spec refs:** FR-31, FR-39

**Files:**
- Modify: `frontend/src/stores/reader.ts`
- Modify: `frontend/src/stores/__tests__/reader.spec.ts` (extend the file created in T11)

**Steps:**

- [ ] Step 1: Extend failing test
  ```typescript
  // frontend/src/stores/__tests__/reader.spec.ts — append
  import { setActivePinia, createPinia } from 'pinia'
  import { useReaderStore } from '../reader'
  import { beforeEach, vi } from 'vitest'

  const mkSection = (id: number, order: number, type = 'chapter', has_summary = false) => ({
    id, order_index: order, title: `S${id}`, section_type: type, has_summary,
  })

  describe('loadBook landing precedence', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('picks URL section when routeSectionId is provided', async () => {
      vi.doMock('@/api/books', () => ({ getBook: async () => ({ id: 1, title: 'x' }) }))
      vi.doMock('@/api/sections', () => ({
        listSections: async () => [
          mkSection(10, 0, 'copyright'),
          mkSection(11, 1, 'chapter'),
          mkSection(12, 2, 'chapter'),
        ],
        getSection: async (_: number, id: number) => mkSection(id, id),
      }))
      const { useReaderStore: fresh } = await import('../reader')
      const s = fresh()
      await s.loadBook(1, { routeSectionId: 12 })
      expect(s.currentSection?.id).toBe(12)
      vi.doUnmock('@/api/books')
      vi.doUnmock('@/api/sections')
    })

    it('picks first summarizable when no URL and no saved state', async () => {
      // ... similar: 2 copyright, then chapter id=20 → expect 20
    })

    it('falls back to sections[0] when no summarizable type exists', async () => {
      // ... all glossary sections → expect first one
    })
  })

  describe('updateSection', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('splices updated section into sections array', () => {
      const s = useReaderStore()
      s.sections = [mkSection(1, 0), mkSection(2, 1)] as never
      s.updateSection({ ...mkSection(2, 1), has_summary: true } as never)
      expect(s.sections[1].has_summary).toBe(true)
    })

    it('updates currentSection if ID matches', () => {
      const s = useReaderStore()
      const target = mkSection(2, 1)
      s.sections = [mkSection(1, 0), target] as never
      s.currentSection = target as never
      s.updateSection({ ...target, has_summary: true } as never)
      expect(s.currentSection?.has_summary).toBe(true)
    })

    it('no-ops with console.warn when section id not found', () => {
      const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const s = useReaderStore()
      s.sections = [mkSection(1, 0)] as never
      s.updateSection({ ...mkSection(99, 99) } as never)
      expect(spy).toHaveBeenCalled()
      expect(s.sections.length).toBe(1)
    })
  })
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run reader.spec.ts`
  Expected: FAIL.

- [ ] Step 3: Update `reader.ts`
  ```typescript
  // loadBook — new signature
  async function loadBook(
    bookId: number,
    opts?: { routeSectionId?: number; savedSectionId?: number },
  ) {
    loading.value = true
    try {
      book.value = await getBook(bookId)
      sections.value = await listSections(bookId)

      const target =
        (opts?.routeSectionId && sections.value.find((s) => s.id === opts.routeSectionId)) ||
        (opts?.savedSectionId && sections.value.find((s) => s.id === opts.savedSectionId)) ||
        sections.value.find((s) => SUMMARIZABLE_TYPES.has(s.section_type)) ||
        sections.value[0] ||
        null

      if (target) {
        await loadSection(bookId, target.id)
      }
    } finally {
      loading.value = false
    }
  }

  function updateSection(updated: Section) {
    const idx = sections.value.findIndex((s) => s.id === updated.id)
    if (idx === -1) {
      console.warn(`updateSection: id ${updated.id} not found in book ${book.value?.id ?? '?'}`)
      return
    }
    sections.value[idx] = updated
    if (currentSection.value?.id === updated.id) {
      currentSection.value = updated
    }
  }

  // Expose updateSection in the returned object
  ```

  Update BookDetailView (T17) to pass `routeSectionId` + `savedSectionId`. For this task, only change the store; BookDetailView will be updated in T17.

- [ ] Step 4: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run reader.spec.ts`
  Expected: all passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/stores/reader.ts frontend/src/stores/__tests__/reader.spec.ts
  git commit -m "feat(reader): landing-section precedence + updateSection action"
  ```

**Inline verification:**
- `cd frontend && npm run type-check && npm run test:unit -- --run reader` — clean + passed

---

### T13: TOCDropdown — Front Matter accordion

**Goal:** Pre-body front-matter sections sit in a collapsed `<details>` group; body sections render at top level.
**Spec refs:** FR-34, FR-35, NFR-04

**Files:**
- Modify: `frontend/src/components/reader/TOCDropdown.vue`
- Create: `frontend/src/components/reader/__tests__/TOCDropdown.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  // frontend/src/components/reader/__tests__/TOCDropdown.spec.ts
  import { mount } from '@vue/test-utils'
  import { describe, it, expect } from 'vitest'
  import TOCDropdown from '../TOCDropdown.vue'

  const mkSections = () => ([
    { id: 1, order_index: 0, title: 'Copyright',        section_type: 'copyright',        has_summary: false },
    { id: 2, order_index: 1, title: 'Acknowledgments',  section_type: 'acknowledgments', has_summary: false },
    { id: 3, order_index: 2, title: 'Chapter 1',        section_type: 'chapter',          has_summary: true  },
    { id: 4, order_index: 3, title: 'Chapter 2',        section_type: 'chapter',          has_summary: false },
    { id: 5, order_index: 4, title: 'Glossary',         section_type: 'glossary',         has_summary: false },
  ])

  describe('TOCDropdown Front Matter accordion', () => {
    it('renders front-matter inside <details>', async () => {
      const wrapper = mount(TOCDropdown, {
        props: { sections: mkSections(), currentSectionId: 3, bookId: 1 },
        global: { stubs: { 'router-link': { template: '<a><slot /></a>' } } },
      })
      await wrapper.find('.toc-trigger').trigger('click')
      const details = wrapper.find('details')
      expect(details.exists()).toBe(true)
      expect(details.find('summary').text()).toMatch(/Front Matter \(2\)/)
      // Collapsed by default
      expect(details.attributes('open')).toBeUndefined()
    })

    it('places glossary (late) outside Front Matter bucket', async () => {
      const wrapper = mount(TOCDropdown, {
        props: { sections: mkSections(), currentSectionId: 3, bookId: 1 },
        global: { stubs: { 'router-link': { template: '<a><slot /></a>' } } },
      })
      await wrapper.find('.toc-trigger').trigger('click')
      const bodyItems = wrapper.findAll('.toc-list > .toc-item')
      const bodyTitles = bodyItems.map((i) => i.find('.toc-title').text())
      expect(bodyTitles).toContain('Glossary')
      expect(bodyTitles).not.toContain('Copyright')
    })
  })
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run TOCDropdown.spec.ts`
  Expected: FAIL — no `<details>` element.

- [ ] Step 3: Refactor `TOCDropdown.vue`
  ```vue
  <script setup lang="ts">
  import { FRONT_MATTER_TYPES, SUMMARIZABLE_TYPES } from '@/stores/reader'
  import type { Section } from '@/types'
  import { computed, ref } from 'vue'

  const props = defineProps<{
    sections: Section[]
    currentSectionId: number | null
    bookId: number
  }>()

  const isOpen = ref(false)
  const searchQuery = ref('')
  function toggle() { isOpen.value = !isOpen.value; if (isOpen.value) searchQuery.value = '' }

  const firstSummarizableIndex = computed(() => {
    const idx = props.sections.findIndex((s) => SUMMARIZABLE_TYPES.has(s.section_type))
    return idx === -1 ? props.sections.length : idx
  })
  const frontMatter = computed(() =>
    props.sections.filter(
      (s, i) => FRONT_MATTER_TYPES.has(s.section_type) && i < firstSummarizableIndex.value,
    ),
  )
  const body = computed(() =>
    props.sections.filter(
      (s, i) => !(FRONT_MATTER_TYPES.has(s.section_type) && i < firstSummarizableIndex.value),
    ),
  )
  function match(s: Section) {
    return !searchQuery.value || s.title.toLowerCase().includes(searchQuery.value.toLowerCase())
  }
  </script>

  <template>
    <div class="toc-dropdown" v-click-outside="() => isOpen = false">
      <button class="toc-trigger" @click="toggle">
        {{ sections.find(s => s.id === currentSectionId)?.title || 'Select Section' }}
        <span class="toc-arrow">{{ isOpen ? '▲' : '▼' }}</span>
      </button>
      <div v-if="isOpen" class="toc-panel">
        <input v-model="searchQuery" placeholder="Search sections..." class="toc-search" />
        <div class="toc-list">
          <router-link
            v-for="section in body.filter(match)"
            :key="section.id"
            :to="`/books/${bookId}/sections/${section.id}`"
            class="toc-item"
            :class="{ active: section.id === currentSectionId }"
            @click="isOpen = false"
          >
            <span class="toc-index">{{ section.order_index + 1 }}</span>
            <span class="toc-title">{{ section.title }}</span>
            <span v-if="section.has_summary" class="toc-summarized">S</span>
          </router-link>
          <details v-if="frontMatter.length" class="toc-frontmatter">
            <summary>Front Matter ({{ frontMatter.length }})</summary>
            <router-link
              v-for="section in frontMatter.filter(match)"
              :key="section.id"
              :to="`/books/${bookId}/sections/${section.id}`"
              class="toc-item"
              :class="{ active: section.id === currentSectionId }"
              @click="isOpen = false"
            >
              <span class="toc-index">{{ section.order_index + 1 }}</span>
              <span class="toc-title">{{ section.title }}</span>
            </router-link>
          </details>
        </div>
      </div>
    </div>
  </template>

  <style scoped>
  /* ... existing styles ... */
  .toc-frontmatter > summary {
    padding: 8px 12px;
    cursor: pointer;
    color: var(--color-text-muted);
    font-size: 12px;
  }
  </style>
  ```

- [ ] Step 4: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run TOCDropdown.spec.ts`
  Expected: 2 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/reader/TOCDropdown.vue \
           frontend/src/components/reader/__tests__/TOCDropdown.spec.ts
  git commit -m "feat(toc): Front Matter accordion groups pre-body sections"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- --run TOCDropdown` — 2 passed
- Manual: open a book in dev server, click TOC — Copyright sits inside collapsed Front Matter

---

### T14: `summarizationJob` Pinia store

**Goal:** A store that owns the SSE-subscribed job lifecycle, exposes `isActive`, `activeJobSectionId`, `getFailedError`, and handles all 8 event types.
**Spec refs:** FR-38

**Files:**
- Create: `frontend/src/stores/summarizationJob.ts`
- Create: `frontend/src/stores/__tests__/summarizationJob.spec.ts`

**Steps:**

- [ ] Step 1: Write failing tests
  ```typescript
  // frontend/src/stores/__tests__/summarizationJob.spec.ts
  import { setActivePinia, createPinia } from 'pinia'
  import { useSummarizationJobStore } from '../summarizationJob'
  import { describe, it, expect, beforeEach, vi } from 'vitest'

  describe('summarizationJob store', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('initial state is inactive', () => {
      const s = useSummarizationJobStore()
      expect(s.isActive).toBe(false)
      expect(s.activeJobSectionId).toBeNull()
      expect(s.getFailedError(1)).toBeUndefined()
    })

    it('onSectionStarted sets activeJobSectionId', () => {
      const s = useSummarizationJobStore()
      s.onSectionStarted({ section_id: 5 })
      expect(s.activeJobSectionId).toBe(5)
    })

    it('onSectionFailed records error + clears active', () => {
      const s = useSummarizationJobStore()
      s.onSectionStarted({ section_id: 5 })
      s.onSectionFailed({ section_id: 5, error: 'LLM timeout' })
      expect(s.activeJobSectionId).toBeNull()
      expect(s.getFailedError(5)).toBe('LLM timeout')
    })

    it('retry via startJob clears previous failedSections entry for that section', async () => {
      const s = useSummarizationJobStore()
      s.onSectionFailed({ section_id: 5, error: 'oops' })
      // Stub out API call
      vi.doMock('@/api/processing', () => ({
        startProcessing: async () => ({ job_id: 42 }),
        connectSSE: () => ({ close: () => {} }),
      }))
      await s.startJob(1, { scope: 'section', section_id: 5 })
      expect(s.getFailedError(5)).toBeUndefined()
    })

    it('reset clears job-session state but preserves failedSections', () => {
      // Per P14: failedSections persists so a user returning to the page after
      // a failed section still sees the error banner + Retry CTA.
      const s = useSummarizationJobStore()
      s.onSectionStarted({ section_id: 5 })
      s.onSectionFailed({ section_id: 5, error: 'x' })
      s.reset()
      expect(s.isActive).toBe(false)
      expect(s.activeJobSectionId).toBeNull()
      expect(s.getFailedError(5)).toBe('x')  // preserved
    })

    it('starts grace-polling when no SSE events arrive within 30s', async () => {
      // E4a: after POST + 30s silence, poll GET /books/{id} until summarized===total.
      vi.useFakeTimers()
      const getBookMock = vi.fn().mockResolvedValue({
        id: 1, title: 't', summary_progress: { summarized: 5, total: 5 },
      })
      vi.doMock('@/api/books', () => ({ getBook: getBookMock }))
      vi.doMock('@/api/processing', () => ({
        startProcessing: async () => ({ job_id: 42 }),
        connectSSE: () => ({ close: () => {} }),
      }))
      const { useSummarizationJobStore: fresh } = await import('../summarizationJob')
      const s = fresh()
      await s.startJob(1, { scope: 'pending' })
      // Advance past the grace window
      await vi.advanceTimersByTimeAsync(30_000)
      await vi.advanceTimersByTimeAsync(5_000)   // first poll
      expect(getBookMock).toHaveBeenCalled()
      vi.useRealTimers()
      vi.doUnmock('@/api/books')
      vi.doUnmock('@/api/processing')
    })

    it('grace-polling cancels when a real SSE event arrives', async () => {
      vi.useFakeTimers()
      const getBookMock = vi.fn()
      vi.doMock('@/api/books', () => ({ getBook: getBookMock }))
      vi.doMock('@/api/processing', () => ({
        startProcessing: async () => ({ job_id: 42 }),
        connectSSE: () => ({ close: () => {} }),
      }))
      const { useSummarizationJobStore: fresh } = await import('../summarizationJob')
      const s = fresh()
      await s.startJob(1, { scope: 'pending' })
      await vi.advanceTimersByTimeAsync(10_000)
      s.onSectionStarted({ section_id: 7 })   // real event before grace expires
      await vi.advanceTimersByTimeAsync(25_000)
      expect(getBookMock).not.toHaveBeenCalled()
      vi.useRealTimers()
    })
  })
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run summarizationJob.spec.ts`
  Expected: FAIL (module not found).

- [ ] Step 3: Implement `summarizationJob.ts`
  ```typescript
  // frontend/src/stores/summarizationJob.ts
  import { defineStore } from 'pinia'
  import { computed, ref } from 'vue'
  import { connectSSE, startProcessing, type ProcessingOptions } from '@/api/processing'
  import { useReaderStore } from '@/stores/reader'
  import { getBook } from '@/api/books'
  import { getSection } from '@/api/sections'

  const GRACE_MS = 30_000
  const POLL_MS = 5_000

  export const useSummarizationJobStore = defineStore('summarizationJob', () => {
    const bookId = ref<number | null>(null)
    const jobId = ref<number | null>(null)
    const activeJobSectionId = ref<number | null>(null)
    const scope = ref<'all' | 'pending' | 'section' | null>(null)
    const failedSections = ref<Map<number, string>>(new Map())
    const source = ref<EventSource | null>(null)
    let graceTimer: ReturnType<typeof setTimeout> | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let sawAnyEvent = false

    const isActive = computed(() => jobId.value !== null)
    const getFailedError = (id: number) => failedSections.value.get(id)

    function cancelGrace() {
      if (graceTimer) { clearTimeout(graceTimer); graceTimer = null }
    }
    function cancelPolling() {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }
    async function pollOnce() {
      if (!bookId.value) return
      try {
        const book = await getBook(bookId.value)
        useReaderStore().setBook(book)
        const sp = (book as { summary_progress?: { summarized: number; total: number } }).summary_progress
        if (sp && sp.summarized >= sp.total) {
          // Server-side job done — wind down
          reset(true)
        }
      } catch (e) {
        console.warn('summary_progress poll failed', e)
      }
    }
    function startGrace() {
      cancelGrace()
      graceTimer = setTimeout(() => {
        // E4a: no events seen — start polling
        if (sawAnyEvent) return
        pollTimer = setInterval(pollOnce, POLL_MS)
      }, GRACE_MS)
    }

    async function startJob(bookIdIn: number, opts: ProcessingOptions) {
      // Retry-clears-failure rule
      if (opts.scope === 'section' && opts.section_id !== undefined) {
        failedSections.value.delete(opts.section_id)
      }
      const { job_id } = await startProcessing(bookIdIn, opts)
      bookId.value = bookIdIn
      jobId.value = job_id
      scope.value = opts.scope ?? 'all'
      sawAnyEvent = false
      startGrace()
      source.value = connectSSE(job_id, {
        onProcessingStarted: () => { sawAnyEvent = true; cancelGrace() },
        onSectionStarted:    (d) => { sawAnyEvent = true; cancelGrace(); onSectionStarted(d) },
        onSectionCompleted:  (d) => { sawAnyEvent = true; onSectionCompleted(d) },
        onSectionFailed:     (d) => { sawAnyEvent = true; onSectionFailed(d) },
        onSectionSkipped:    (d) => { sawAnyEvent = true; onSectionSkipped(d) },
        onSectionRetrying:   (d) => { sawAnyEvent = true; onSectionRetrying(d) },
        onProcessingCompleted: () => onCompleted(),
        onProcessingFailed:    (d) => onFailed(d.error),
        // E4: SSE drop mid-job — clear active-section indicator + start polling fallback
        onError: () => {
          activeJobSectionId.value = null
          if (!pollTimer) pollTimer = setInterval(pollOnce, POLL_MS)
        },
      })
    }

    function onSectionStarted(d: { section_id: number }) {
      activeJobSectionId.value = d.section_id
    }
    async function onSectionCompleted(d: { section_id: number }) {
      activeJobSectionId.value = null
      if (!bookId.value) return
      try {
        const fresh = await getSection(bookId.value, d.section_id)
        useReaderStore().updateSection(fresh)
      } catch (e) {
        console.warn(`refetch section ${d.section_id} failed`, e)
      }
      // also refresh book-level summary_progress
      try {
        const book = await getBook(bookId.value)
        useReaderStore().book = book
      } catch { /* noop */ }
    }
    function onSectionFailed(d: { section_id: number; error: string }) {
      failedSections.value.set(d.section_id, d.error)
      activeJobSectionId.value = null
    }
    function onSectionSkipped(_d: { section_id: number }) {
      // no-op on section state; progress counter refreshes via onSectionCompleted path on next
    }
    function onSectionRetrying(d: { section_id: number }) {
      activeJobSectionId.value = d.section_id
    }
    function onCompleted() { reset(false) }
    function onFailed(_err: string) { reset(false) }

    function reset(closeSource = true) {
      cancelGrace()
      cancelPolling()
      if (closeSource && source.value) source.value.close()
      source.value = null
      jobId.value = null
      activeJobSectionId.value = null
      scope.value = null
      // P14: bookId + failedSections preserved across job completion.
      // failedSections clears per-section on startJob({scope:'section', section_id}).
    }

    return {
      bookId, jobId, activeJobSectionId, scope, failedSections,
      isActive, getFailedError,
      startJob, reset,
      onSectionStarted, onSectionCompleted, onSectionFailed,
      onSectionSkipped, onSectionRetrying, onCompleted, onFailed,
    }
  })
  ```

  Note on `useReaderStore().book = book`: if the reader store's `book` ref is not exposed for direct mutation, add a `setBook(book)` action there in this task — a 3-line addition. Prefer action over direct ref write.

- [ ] Step 4: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run summarizationJob.spec.ts`
  Expected: 5 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/stores/summarizationJob.ts \
           frontend/src/stores/__tests__/summarizationJob.spec.ts
  git commit -m "feat(frontend): summarizationJob Pinia store with SSE lifecycle"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — clean
- `cd frontend && npm run test:unit -- --run summarizationJob` — 5 passed

---

### T15: `SummaryEmptyState` component

**Goal:** 4-state component rendering correct UI per (section, activeJobSectionId, failedError) combination.
**Spec refs:** FR-33

**Files:**
- Create: `frontend/src/components/reader/SummaryEmptyState.vue`
- Create: `frontend/src/components/reader/__tests__/SummaryEmptyState.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  // frontend/src/components/reader/__tests__/SummaryEmptyState.spec.ts
  import { mount } from '@vue/test-utils'
  import { describe, it, expect } from 'vitest'
  import SummaryEmptyState from '../SummaryEmptyState.vue'

  const chapter = { id: 5, title: 'Chapter 1', section_type: 'chapter' }
  const copyright = { id: 6, title: 'Copyright', section_type: 'copyright' }

  describe('SummaryEmptyState', () => {
    it('front-matter renders "not applicable"', () => {
      const w = mount(SummaryEmptyState, {
        props: { section: copyright, activeJobSectionId: null, failedError: null },
      })
      expect(w.text()).toMatch(/Summary not applicable for Copyright/)
      expect(w.find('button').exists()).toBe(false)
    })

    it('summarizable without summary renders CTA', () => {
      const w = mount(SummaryEmptyState, {
        props: { section: chapter, activeJobSectionId: null, failedError: null },
      })
      expect(w.text()).toMatch(/Not yet summarized/)
      const btn = w.find('button')
      expect(btn.exists()).toBe(true)
      expect(btn.text()).toMatch(/Summarize this section/)
    })

    it('renders generating state when activeJobSectionId matches', () => {
      const w = mount(SummaryEmptyState, {
        props: { section: chapter, activeJobSectionId: 5, failedError: null },
      })
      expect(w.text()).toMatch(/Generating summary/)
      expect(w.find('button').exists()).toBe(false)
    })

    it('renders failure + Retry button when failedError present', () => {
      const w = mount(SummaryEmptyState, {
        props: { section: chapter, activeJobSectionId: null, failedError: 'LLM timeout' },
      })
      expect(w.text()).toMatch(/Summary generation failed: LLM timeout/)
      expect(w.find('button').text()).toMatch(/Retry/)
    })

    it('generating takes precedence over failure', () => {
      const w = mount(SummaryEmptyState, {
        props: { section: chapter, activeJobSectionId: 5, failedError: 'old error' },
      })
      expect(w.text()).toMatch(/Generating summary/)
    })

    it('CTA click emits summarize', async () => {
      const w = mount(SummaryEmptyState, {
        props: { section: chapter, activeJobSectionId: null, failedError: null },
      })
      await w.find('button').trigger('click')
      expect(w.emitted('summarize')).toBeTruthy()
    })
  })
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run SummaryEmptyState.spec.ts`
  Expected: FAIL (module missing).

- [ ] Step 3: Implement component
  ```vue
  <!-- frontend/src/components/reader/SummaryEmptyState.vue -->
  <script setup lang="ts">
  import { FRONT_MATTER_TYPES } from '@/stores/reader'
  import { computed } from 'vue'

  const props = defineProps<{
    section: { id: number; title: string; section_type: string }
    activeJobSectionId: number | null
    failedError: string | null
  }>()
  const emit = defineEmits<{ summarize: [] }>()

  const isFrontMatter = computed(() => FRONT_MATTER_TYPES.has(props.section.section_type))
  const isGenerating  = computed(() => props.activeJobSectionId === props.section.id)
  const hasFailed     = computed(() => !!props.failedError && !isGenerating.value)
  </script>

  <template>
    <div class="summary-empty">
      <template v-if="isFrontMatter">
        <p class="muted">Summary not applicable for {{ section.title }}</p>
      </template>
      <template v-else-if="isGenerating">
        <p class="muted">Generating summary… <span class="spinner" /></p>
      </template>
      <template v-else-if="hasFailed">
        <p class="error">Summary generation failed: {{ failedError }}</p>
        <button class="btn" @click="emit('summarize')">Retry</button>
      </template>
      <template v-else>
        <h3>Not yet summarized</h3>
        <p class="muted">This section doesn't have a summary yet.</p>
        <button class="btn primary" @click="emit('summarize')">Summarize this section</button>
      </template>
    </div>
  </template>

  <style scoped>
  .summary-empty { padding: 48px 24px; text-align: center; max-width: 480px; margin: 0 auto; }
  .muted { color: var(--color-text-muted); }
  .error { color: var(--color-danger, #c0392b); }
  .btn { padding: 8px 16px; border-radius: 6px; border: 1px solid var(--color-border); cursor: pointer; }
  .btn.primary { background: var(--color-accent); color: #fff; border-color: var(--color-accent); }
  .spinner { display: inline-block; width: 12px; height: 12px; border: 2px solid var(--color-border);
             border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  </style>
  ```

- [ ] Step 4: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run SummaryEmptyState.spec.ts`
  Expected: 6 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/reader/SummaryEmptyState.vue \
           frontend/src/components/reader/__tests__/SummaryEmptyState.spec.ts
  git commit -m "feat(reader): SummaryEmptyState 4-state component"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- --run SummaryEmptyState` — 6 passed

---

### T16: `SummarizationProgress` component

**Goal:** "N of M summarized" text + *Summarize pending sections* button; hidden when `total===0`; disabled during active job.
**Spec refs:** FR-36, FR-37, E2

**Files:**
- Create: `frontend/src/components/book/SummarizationProgress.vue`
- Create: `frontend/src/components/book/__tests__/SummarizationProgress.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  // frontend/src/components/book/__tests__/SummarizationProgress.spec.ts
  import { mount } from '@vue/test-utils'
  import { setActivePinia, createPinia } from 'pinia'
  import { describe, it, expect, beforeEach } from 'vitest'
  import SummarizationProgress from '../SummarizationProgress.vue'
  import { useSummarizationJobStore } from '@/stores/summarizationJob'

  describe('SummarizationProgress', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('renders N of M text', () => {
      const w = mount(SummarizationProgress, { props: { bookId: 1, summarized: 4, total: 12 } })
      expect(w.text()).toMatch(/4 of 12 sections summarized/)
    })

    it('shows Summarize pending button when summarized < total', () => {
      const w = mount(SummarizationProgress, { props: { bookId: 1, summarized: 4, total: 12 } })
      expect(w.find('button').text()).toMatch(/Summarize pending/)
    })

    it('hides when total=0', () => {
      const w = mount(SummarizationProgress, { props: { bookId: 1, summarized: 0, total: 0 } })
      expect(w.html()).toBe('<!--v-if-->')
    })

    it('button disabled + re-labeled during active job', async () => {
      const w = mount(SummarizationProgress, { props: { bookId: 1, summarized: 4, total: 12 } })
      const s = useSummarizationJobStore()
      s.jobId = 99
      await w.vm.$nextTick()
      const btn = w.find('button')
      expect(btn.attributes('disabled')).toBeDefined()
      expect(btn.text()).toMatch(/Summarizing…/)
    })
  })
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run SummarizationProgress.spec.ts`
  Expected: FAIL.

- [ ] Step 3: Implement
  ```vue
  <!-- frontend/src/components/book/SummarizationProgress.vue -->
  <script setup lang="ts">
  import { computed } from 'vue'
  import { useSummarizationJobStore } from '@/stores/summarizationJob'

  const props = defineProps<{ bookId: number; summarized: number; total: number }>()

  const job = useSummarizationJobStore()
  const isActive = computed(() => job.isActive)
  const showButton = computed(() => props.summarized < props.total)

  async function onClick() {
    // FR-36: omits preset_name so server default applies
    await job.startJob(props.bookId, { scope: 'pending' })
  }
  </script>

  <template>
    <div v-if="total > 0" class="summary-progress">
      <span>{{ summarized }} of {{ total }} sections summarized</span>
      <button
        v-if="showButton"
        class="btn"
        :disabled="isActive"
        @click="onClick"
      >
        {{ isActive ? `Summarizing… ${summarized}/${total}` : 'Summarize pending sections' }}
      </button>
    </div>
  </template>

  <style scoped>
  .summary-progress { display: flex; gap: 12px; align-items: center; font-size: 13px;
                      color: var(--color-text-muted); padding: 8px 0; }
  .btn { padding: 6px 12px; border: 1px solid var(--color-border); border-radius: 6px;
         background: var(--color-bg-primary); cursor: pointer; }
  .btn:disabled { opacity: 0.6; cursor: default; }
  </style>
  ```

- [ ] Step 4: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run SummarizationProgress.spec.ts`
  Expected: 4 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/book/SummarizationProgress.vue \
           frontend/src/components/book/__tests__/SummarizationProgress.spec.ts
  git commit -m "feat(book): SummarizationProgress component"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- --run SummarizationProgress` — 4 passed

---

### T17: BookDetailView — Summary tab flow + `SummarizationProgress` mount + route-leave guard

**Goal:** Tie everything together in BookDetailView: mount progress, route Summary tab through `SummaryEmptyState`, reset `summarizationJob` on route leave, pass saved reading state to `loadBook`.
**Spec refs:** FR-32, FR-37, FR-38 (lifecycle side)

**Files:**
- Modify: `frontend/src/views/BookDetailView.vue`

**Steps:**

- [ ] Step 1: Write failing component test
  ```typescript
  // frontend/src/views/__tests__/BookDetailView.summary-tab.spec.ts
  import { mount, flushPromises } from '@vue/test-utils'
  import { setActivePinia, createPinia } from 'pinia'
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import { createRouter, createMemoryHistory } from 'vue-router'
  import BookDetailView from '../BookDetailView.vue'
  import { useReaderStore } from '@/stores/reader'

  const stubRouter = () => createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/books/:id/sections/:sectionId?', component: BookDetailView }],
  })

  describe('BookDetailView Summary tab routing', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('renders SummaryEmptyState when contentMode=summary and no default_summary', async () => {
      const router = stubRouter()
      router.push('/books/1/sections/5')
      await router.isReady()

      const reader = useReaderStore()
      reader.book = { id: 1, title: 't', summary_progress: { summarized: 0, total: 1 } } as never
      reader.sections = [{ id: 5, title: 'Ch1', section_type: 'chapter', has_summary: false }] as never
      reader.currentSection = { id: 5, title: 'Ch1', section_type: 'chapter', content_md: 'body', default_summary: null, has_summary: false } as never
      reader.contentMode = 'summary'

      const w = mount(BookDetailView, { global: { plugins: [router] } })
      await flushPromises()
      expect(w.findComponent({ name: 'SummaryEmptyState' }).exists()).toBe(true)
      expect(w.text()).toMatch(/Not yet summarized/)
    })

    it('renders ReadingArea with summary_md when default_summary present', async () => {
      const router = stubRouter()
      router.push('/books/1/sections/5')
      await router.isReady()
      const reader = useReaderStore()
      reader.book = { id: 1, title: 't' } as never
      reader.sections = [{ id: 5, title: 'Ch1', section_type: 'chapter', has_summary: true }] as never
      reader.currentSection = {
        id: 5, title: 'Ch1', section_type: 'chapter', content_md: 'original',
        default_summary: { summary_md: '# Summary content' }, has_summary: true,
      } as never
      reader.contentMode = 'summary'
      const w = mount(BookDetailView, { global: { plugins: [router] } })
      await flushPromises()
      expect(w.html()).toContain('Summary content')
      expect(w.html()).not.toContain('original')
    })

    it('mounts SummarizationProgress in the book header when summary_progress present', async () => {
      const router = stubRouter()
      router.push('/books/1')
      await router.isReady()
      const reader = useReaderStore()
      reader.book = { id: 1, title: 't', summary_progress: { summarized: 2, total: 5 } } as never
      reader.sections = []
      const w = mount(BookDetailView, { global: { plugins: [router] } })
      await flushPromises()
      expect(w.findComponent({ name: 'SummarizationProgress' }).exists()).toBe(true)
    })
  })
  ```

  If the route-stub setup conflicts with the existing `loadFromRoute` behavior (reader triggers an API call), mock `@/api/books` and `@/api/sections` to return the seeded values before mount. Keep the test focused on render-conditional logic, not on the full store cycle.

- [ ] Step 1b: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run BookDetailView.summary-tab.spec.ts`
  Expected: FAIL (components not imported / Summary tab still unconditional).

- [ ] Step 2: Modify `BookDetailView.vue`
  - Import: `SummarizationProgress`, `SummaryEmptyState`, `useSummarizationJobStore`, `onBeforeRouteLeave`.
  - In `loadFromRoute`, pass `routeSectionId` + `savedSectionId` to `reader.loadBook(bookId, {...})`. Read saved section id from `useReadingState()` (existing composable).
  - Add `<SummarizationProgress>` under the book title row (inside the `<template v-else>` at line 110, above `<ReaderHeader>`). Mount conditional on `reader.book?.summary_progress`:
    ```vue
    <SummarizationProgress
      v-if="reader.book.summary_progress"
      :book-id="reader.book.id"
      :summarized="reader.book.summary_progress.summarized"
      :total="reader.book.summary_progress.total"
    />
    ```
  - Replace the `<ReadingArea :content="reader.currentSection.content_md || ''" />` block at :150-155 with:
    ```vue
    <template v-if="reader.currentSection">
      <template v-if="reader.contentMode === 'summary'">
        <ReadingArea
          v-if="reader.currentSection.default_summary?.summary_md"
          :content="reader.currentSection.default_summary.summary_md"
          :has-prev="reader.hasPrev"
          :has-next="reader.hasNext"
          @navigate="reader.navigateSection($event)"
        />
        <SummaryEmptyState
          v-else
          :section="reader.currentSection"
          :active-job-section-id="job.activeJobSectionId"
          :failed-error="job.getFailedError(reader.currentSection.id) ?? null"
          @summarize="onSummarizeThisSection"
        />
      </template>
      <ReadingArea
        v-else
        :content="reader.currentSection.content_md || ''"
        :has-prev="reader.hasPrev"
        :has-next="reader.hasNext"
        @navigate="reader.navigateSection($event)"
      />
    </template>
    ```
  - Add:
    ```typescript
    const job = useSummarizationJobStore()
    async function onSummarizeThisSection() {
      if (!reader.book || !reader.currentSection) return
      await job.startJob(reader.book.id, {
        scope: 'section',
        section_id: reader.currentSection.id,
      })
    }
    onBeforeRouteLeave(() => { job.reset() })
    ```

- [ ] Step 3: Manual smoke test
  ```bash
  cd backend && uv run bookcompanion serve &   # port 8000
  cd frontend && npm run dev                    # port 5173
  # In browser:
  # 1. Open library → click Porter book
  # 2. Verify lands on "1. Competition" not Copyright
  # 3. Click TOC → Front Matter bucket is collapsed; click → Copyright visible
  # 4. Click Copyright → Summary tab shows "Summary not applicable for Copyright"
  # 5. Click a chapter without summary → click "Summarize this section" → observe "Generating…"
  # 6. Observe summary renders; TOC S-marker appears; progress counter increments
  ```

- [ ] Step 4: Commit
  ```bash
  git add frontend/src/views/BookDetailView.vue
  git commit -m "feat(reader): wire Summary tab flow + SummarizationProgress in BookDetailView"
  ```

**Inline verification:**
- `cd frontend && npm run type-check` — clean
- `cd frontend && npm run build` — succeeds
- Manual (from Step 3) — all 6 checks pass

---

### T18: `link-policy.ts` utility

**Goal:** Pure `classifyLink(href)` function.
**Spec refs:** FR-45

**Files:**
- Create: `frontend/src/utils/link-policy.ts`
- Create: `frontend/src/utils/__tests__/link-policy.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test (full table from spec FR-45)
  ```typescript
  // frontend/src/utils/__tests__/link-policy.spec.ts
  import { describe, it, expect } from 'vitest'
  import { classifyLink } from '../link-policy'

  describe('classifyLink', () => {
    const cases: Array<[string, string]> = [
      ['#', 'internal-anchor'],
      ['#section-5', 'internal-anchor'],
      ['http://a.com', 'external'],
      ['https://a.com', 'external'],
      ['mailto:x@y', 'external'],
      ['//cdn.com/x', 'external'],
      ['./ch2.xhtml', 'other'],
      ['../appendix.xhtml', 'other'],
      ['javascript:alert(1)', 'other'],
      ['data:text/html,...', 'other'],
      ['', 'other'],
      ['   ', 'other'],
    ]
    it.each(cases)('classifies %s as %s', (href, expected) => {
      expect(classifyLink(href)).toBe(expected)
    })
  })
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run link-policy.spec.ts`
  Expected: FAIL (missing module).

- [ ] Step 3: Implement
  ```typescript
  // frontend/src/utils/link-policy.ts
  export type LinkClass = 'internal-anchor' | 'external' | 'other'

  export function classifyLink(href: string): LinkClass {
    const h = (href ?? '').trim()
    if (!h) return 'other'
    if (h.startsWith('#')) return 'internal-anchor'
    if (/^https?:\/\//i.test(h)) return 'external'
    if (h.toLowerCase().startsWith('mailto:')) return 'external'
    if (h.startsWith('//')) return 'external'
    return 'other'
  }
  ```

- [ ] Step 4: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run link-policy.spec.ts`
  Expected: 12 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/utils/link-policy.ts \
           frontend/src/utils/__tests__/link-policy.spec.ts
  git commit -m "feat(reader): link-policy classifyLink utility"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- --run link-policy` — 12 passed

---

### T19: `ReadingArea` — post-DOMPurify link rewriting

**Goal:** After DOMPurify sanitizes the rendered HTML, walk anchors and apply the link policy: relative/other → `<span>`; external → `target=_blank rel=noopener noreferrer`.
**Spec refs:** FR-40, FR-41, FR-42, FR-43, FR-44, NFR-03

**Files:**
- Modify: `frontend/src/components/reader/ReadingArea.vue:22-25`
- Create: `frontend/src/components/reader/__tests__/ReadingArea.link-policy.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  // frontend/src/components/reader/__tests__/ReadingArea.link-policy.spec.ts
  import { mount } from '@vue/test-utils'
  import { describe, it, expect } from 'vitest'
  import ReadingArea from '../ReadingArea.vue'

  const render = (md: string) => {
    const w = mount(ReadingArea, { props: { content: md, hasPrev: false, hasNext: false } })
    return w.html()
  }

  describe('ReadingArea link policy', () => {
    it('relative anchor → span', () => {
      const html = render('See [the intro](#intro) above.')
      expect(html).not.toMatch(/<a[^>]+href="#intro"/)
      expect(html).toMatch(/<span[^>]*>the intro<\/span>/)
    })

    it('external https → target=_blank rel=noopener noreferrer', () => {
      const html = render('Visit [site](https://example.com).')
      expect(html).toMatch(/<a[^>]+href="https:\/\/example\.com"[^>]+target="_blank"[^>]+rel="noopener noreferrer"/)
    })

    it('javascript: scheme → span', () => {
      const html = render('[click](javascript:alert(1))')
      expect(html).not.toMatch(/<a[^>]*href="javascript:/i)
      expect(html).toMatch(/<span[^>]*>click<\/span>/)
    })

    it('relative path (./ch2.xhtml) → span', () => {
      const html = render('[next](./ch2.xhtml)')
      expect(html).not.toMatch(/<a[^>]*href="\.\/ch2\.xhtml"/)
      expect(html).toMatch(/<span[^>]*>next<\/span>/)
    })
  })
  ```

- [ ] Step 2: Run and verify fail
  Run: `cd frontend && npm run test:unit -- --run ReadingArea.link-policy.spec.ts`
  Expected: FAIL (anchors still rendered as `<a>`).

- [ ] Step 3: Update `ReadingArea.vue`
  ```vue
  <script setup lang="ts">
  import MarkdownIt from 'markdown-it'
  import DOMPurify from 'dompurify'
  import { computed, onMounted, onUnmounted } from 'vue'
  import { classifyLink } from '@/utils/link-policy'

  // ... existing props/emit/md ...

  function applyLinkPolicy(sanitized: string): string {
    const doc = new DOMParser().parseFromString(sanitized, 'text/html')
    for (const a of Array.from(doc.querySelectorAll('a[href]'))) {
      const cls = classifyLink(a.getAttribute('href') || '')
      if (cls === 'external') {
        a.setAttribute('target', '_blank')
        a.setAttribute('rel', 'noopener noreferrer')
      } else {
        const span = doc.createElement('span')
        span.textContent = a.textContent || ''
        if (a.className) span.className = a.className
        a.replaceWith(span)
      }
    }
    return doc.body.innerHTML
  }

  const renderedHtml = computed(() => {
    const raw = md.render(props.content || '')
    const sanitized = DOMPurify.sanitize(raw)
    return applyLinkPolicy(sanitized)
  })
  </script>
  ```

- [ ] Step 4: Run and verify pass
  Run: `cd frontend && npm run test:unit -- --run ReadingArea.link-policy.spec.ts`
  Expected: 4 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/reader/ReadingArea.vue \
           frontend/src/components/reader/__tests__/ReadingArea.link-policy.spec.ts
  git commit -m "feat(reader): post-DOMPurify link policy rewriting"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- --run ReadingArea` — all passed
- Manual: open a chapter with footnote-link anchors — anchors render as plain text, no cursor change on hover

---

### T20: Cross-layer contract guard test

**Goal:** A backend unit test that parses both the backend classifier module and the frontend `reader.ts` and fails if the two set literals drift.
**Spec refs:** FR-06a

**Files:**
- Create: `backend/tests/unit/test_section_type_sets_contract.py`

**Steps:**

- [ ] Step 1: Write the test
  ```python
  # backend/tests/unit/test_section_type_sets_contract.py
  """Cross-layer guard: backend classifier sets must match frontend mirror."""
  import re
  from pathlib import Path
  from app.services.parser.section_classifier import FRONT_MATTER_TYPES, SUMMARIZABLE_TYPES

  REPO_ROOT = Path(__file__).resolve().parents[3]
  READER_TS = REPO_ROOT / "frontend" / "src" / "stores" / "reader.ts"


  def _extract_set_literal(name: str, source: str) -> set[str]:
      # Match `export const NAME: ... = new Set([ '...', '...', ])`
      m = re.search(
          rf"export const {re.escape(name)}[^=]+=\s*new Set\(\[(.*?)\]\)",
          source,
          re.DOTALL,
      )
      if not m:
          raise AssertionError(f"could not find {name} in reader.ts")
      body = m.group(1)
      return set(re.findall(r"'([^']+)'", body))


  def test_front_matter_types_match_frontend():
      src = READER_TS.read_text()
      frontend_set = _extract_set_literal("FRONT_MATTER_TYPES", src)
      assert frontend_set == set(FRONT_MATTER_TYPES), (
          f"drift: backend={set(FRONT_MATTER_TYPES)} frontend={frontend_set}"
      )


  def test_summarizable_types_match_frontend():
      src = READER_TS.read_text()
      frontend_set = _extract_set_literal("SUMMARIZABLE_TYPES", src)
      assert frontend_set == set(SUMMARIZABLE_TYPES), (
          f"drift: backend={set(SUMMARIZABLE_TYPES)} frontend={frontend_set}"
      )
  ```

- [ ] Step 2: Run — should pass because T1 + T11 set both sides consistently
  Run: `cd backend && uv run python -m pytest tests/unit/test_section_type_sets_contract.py -v`
  Expected: 2 passed.

- [ ] Step 3: Verify it catches drift by temporarily editing `reader.ts` to remove one value
  Run: edit `frontend/src/stores/reader.ts`, remove `'colophon'` from FRONT_MATTER_TYPES, re-run the test.
  Expected: FAIL with a clear `drift:` message. Restore the deletion.

- [ ] Step 4: Commit
  ```bash
  git add backend/tests/unit/test_section_type_sets_contract.py
  git commit -m "test: cross-layer contract guard for classifier type sets"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/test_section_type_sets_contract.py -v` — 2 passed

---

### T21: Final verification

**Goal:** Full verification that the implementation works end-to-end and no regressions were introduced.
**Spec refs:** §11.4 Regression

**Steps:**

- [ ] **Lint & format:** `cd backend && uv run ruff check . && uv run ruff format --check .` — 0 errors
- [ ] **Backend type check:** `cd backend && uv run python -c "import app.services.parser.section_classifier, app.api.routes.books, app.api.routes.sections, app.api.routes.processing, app.services.summarizer.summarizer_service"` — no import errors
- [ ] **Frontend type check:** `cd frontend && npm run type-check` — clean
- [ ] **Backend unit + integration:** `cd backend && uv run python -m pytest -q` — ~455 passing, 0 failing. Compare to baseline recorded in spec §11.4 (~440 + ~15 new = ~455)
- [ ] **Frontend unit:** `cd frontend && npm run test:unit` — all suites passed
- [ ] **Frontend build:** `cd frontend && npm run build` — exits 0
- [ ] **Database migrations:** `cd backend && uv run alembic -c app/migrations/alembic.ini upgrade head` — applies cleanly on an existing library DB; re-run is a no-op
- [ ] **Fresh-install smoke:**
  ```bash
  rm -rf ~/Library/Application\ Support/bookcompanion
  cd backend && uv run bookcompanion init
  uv run bookcompanion add /path/to/porter.epub
  uv run bookcompanion serve &
  # in new terminal:
  curl -s http://localhost:8000/api/v1/books/1 | jq '.summary_progress'
  # → {"summarized": 0, "total": 12}
  curl -sX POST http://localhost:8000/api/v1/books/1/summarize \
    -H 'content-type: application/json' -d '{"scope":"pending"}' | jq '.job_id'
  ```
- [ ] **API smoke:**
  ```bash
  # Invalid scope → 422
  curl -sX POST http://localhost:8000/api/v1/books/1/summarize -d '{"scope":"section"}' -H 'content-type: application/json'
  # → 422 with "section_id" in detail
  # Section summary_md
  curl -s "http://localhost:8000/api/v1/books/1/sections/4?include_content=true" | jq '.default_summary.summary_md, .is_summarizable'
  ```
- [ ] **Frontend smoke (manual, Playwright MCP if available):**
  1. `npm run dev` — visit http://localhost:5173
  2. Click Porter book → lands on "1. Competition: The Right Mind-Set" (not Copyright)
  3. Open TOC → "Front Matter (3)" collapsed; click to expand; click Copyright
  4. Summary tab → "Summary not applicable for Copyright"; no CTA button
  5. Navigate to a non-summarized chapter → Summary tab shows "Not yet summarized" + *Summarize this section*
  6. Click CTA → state transitions to "Generating…"; on SSE completion, summary renders and TOC gains "S" marker
  7. Book header reads "5 of 12 sections summarized" → click *Summarize pending sections* → state transitions for remaining chapters
  8. Hover any footnote anchor in chapter content → cursor does NOT become pointer; anchor rendered as plain text
  9. External link (if any) in summary content opens in new tab with rel="noopener noreferrer"
- [ ] **Data quality:**
  ```bash
  sqlite3 ~/Library/Application\ Support/bookcompanion/library.db \
    "SELECT count(*) FROM book_sections WHERE content_md LIKE '%__IMG_PLACEHOLDER__:%__ENDIMG__%'"
  # → 0
  sqlite3 ~/Library/Application\ Support/bookcompanion/library.db \
    "SELECT section_type, count(*) FROM book_sections GROUP BY section_type ORDER BY count(*) DESC"
  # → shows copyright, acknowledgments, part_header etc. alongside chapter
  ```
- [ ] **Changelog entry:** Add to `docs/changelog.md`:
  ```
  ### 2026-04-19
  - **Reader UX polish.** Opening a book lands on its first summarizable section.
    Front matter (Copyright, Acknowledgments, Part N, etc.) now groups under a
    collapsed Front Matter accordion in the TOC. The Summary tab shows the
    generated markdown (previously fell through to original content). Heading
    and footnote anchors render as non-clickable spans; external links open in
    a new tab with `rel="noopener noreferrer"`.
  - **Book-level summarization progress.** The book header reads "N of M
    summarized" (M counts only summarizable-type sections) and a one-click
    "Summarize pending sections" button fills the remainder over SSE.
    Non-summarizable types are never auto-summarized.
  - **Legacy image repair.** Images that rendered as broken tokens on books
    imported before the image-URL fix are now rewritten automatically on next
    server start.
  - **Reclassification.** Existing sections are reclassified on startup; auto
    summaries for newly-identified front matter are pruned; user-curated
    summaries are preserved.
  ```
- [ ] **Workstream update:** Apply any enrichment from Phase 6

**Cleanup:**
- [ ] Remove any `print` / `console.log` debug lines introduced during development
- [ ] Remove leftover `.playwright-mcp/` or `test.sh` files if unrelated to this plan
- [ ] Verify no temporary fixture files remain outside `tests/` directories

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | (a) Spec edge cases E4 (SSE drop) + E4a (SSE-fail-to-open grace polling) were not wired into T14 — would leave the button stuck "Summarizing…" on a real network glitch. (b) `reset()` spec text says "clears all state" but literal implementation loses `failedSections` on job completion — user returning to a failed section would lose the Retry banner. (c) T17 view-integration relied on manual testing only; plan reviewer could push back on structural-only verification. | (a) Added grace-polling (30s grace → 5s-interval `GET /books/{id}` polling, cancelled on any real event) to T14 implementation + two new Vitest tests with fake timers. Added decision P15 documenting the choice to implement inline. (b) Introduced decision P14: `reset()` preserves `bookId` + `failedSections`; per-section retry-clears-error lives in `startJob`. Updated the "reset clears everything" test to "reset clears job-session state but preserves failedSections". (c) Added a real component-mount test to T17 covering three render conditions (empty-state, summary_md render, progress mount). Adds ~15 min to T17. |
| 2 | _to fill in next_ | _to fill in next_ |

---

*Next step: `/pmos-toolkit:execute` to run this plan task-by-task.*
