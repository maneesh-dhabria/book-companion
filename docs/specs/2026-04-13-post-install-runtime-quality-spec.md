# Post-Install Runtime Quality — Spec

**Date:** 2026-04-13
**Status:** Draft
**Tier:** 2 — Enhancement
**Requirements:** `docs/requirements/2026-04-12-post-install-runtime-quality.md`

---

## 1. Problem Statement

After zero-dependency packaging shipped, the first real user session surfaced four runtime quality issues. The serious one: concurrent writes to SQLite fail immediately with `database is locked` 500s any time the UI writes reading-state while the summarizer is holding a transaction. Three smaller ones piled on: summarize is "all-or-nothing" (a 17-minute transaction + lost work on crash), the UI fires a preset `/active` request that 404s on a fresh library, and missing images silently return HTML-as-image due to the SPA fallback. Primary success metric: **zero 500 errors during a scroll-while-summarizing session**.

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|----------------|
| G1 | Concurrent reads/writes never fail on lock | Test fires 50 `PUT /api/v1/reading-state` during an active summarize job → 0×500 responses |
| G2 | Summarize progress is durable mid-run | Test kills summarize coroutine at section N → sections 1..N-1 committed, N absent |
| G3 | Re-running summarize skips completed sections | Book with 11/20 sections summarized → second run returns `{completed: 9, skipped: 11}`, 0 LLM calls for skipped range |
| G4 | Browser console is clean on fresh library | No 4xx/5xx entries in console when opening a library with 0 books |
| G5 | Missing images return correct 404 | `curl -sI /books/nonexistent.jpg` → `HTTP/1.1 404` |

---

## 3. Non-Goals

- Multi-user write concurrency — because this is a single-user tool; 5s busy_timeout is enough.
- Rewriting summarizer orchestration (map-reduce, cumulative context, eval retry) — because the fix is transactional, not algorithmic.
- SSE per-section progress events — because polling already surfaces progress once commits are granular; SSE is a future enhancement (Open Question 1).
- "Re-summarize all" / `--force` flag — because the current `force` flag in `summarize_book` already handles it; surfacing it to the UI is separate work.
- Auto-migrating image URLs in existing `content_md` for books ingested before this change — because we accept re-import as the recovery path for pre-existing books (single user, small library).

---

## 4. Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | `PRAGMA busy_timeout=5000` added to `_on_connect` in `session.py` | (a) 1s, (b) 5s (chosen), (c) 30s, (d) app-level retry loop | 5s exceeds any single-section write (LLM embeddings + summary insert = ~100ms). Longer than writes, shorter than user patience. SQLite-native; simpler than app-level retry. |
| D2 | `summarize_book()` commits after each successfully summarized section | (a) One commit at end (current), (b) Per-section (chosen), (c) Autocommit mode | Per-section reduces lock window from minutes to ~100ms and makes partial progress durable. Existing skip-completed logic (already implemented at `summarizer_service.py:82`) becomes usable. Autocommit would break eval trace + summary + search index co-atomicity within one section. |
| D3 | Remove `GET /api/v1/reading-presets/active`; list endpoint returns `{items, default_id}` | (a) Keep 404, (b) Return 200+null, (c) Collapse endpoints (chosen) | One source of truth, one round-trip. The "active preset" is metadata on the collection, not a separate resource. Backward-compat: keep `/active` returning 410 Gone with a deprecation header for one release, then delete — but see NFR-03 (no external users, so delete directly is acceptable). |
| D4 | Image URLs rewritten at ingestion to `/api/v1/images/{image_id}` (image_id is the stable identity) | (a) Parser placeholder + BookService substitution at insert (chosen), (b) Response-time serializer rewrite, (c) Filename-keyed URL `/books/{id}/images/{filename}` | (a) gives clean stored content with stable IDs and zero serve-time overhead. The `Image` model already has `id` as PK; `filename` is nullable so it can't be the URL key. Response-time rewrite (b) was considered but adds work to every section fetch and obscures stored data. Existing books need re-import (single user, small library). |
| D5 | SPA fallback in `CachingStaticFiles` skips asset extensions | (a) Blanket fallback (current), (b) Extension deny-list (chosen), (c) Path-prefix deny-list | Simple, ~10 extensions cover 99% of cases. Prefix-based would require coordinating with backend route shapes. Excluded: `.jpg .jpeg .png .gif .webp .svg .ico .pdf .mp4 .webm .woff .woff2 .ttf .otf .eot .map`. |
| D6 | All four fixes land in one branch | (a) Separate PRs, (b) Single branch (chosen) | Shared test/verify overhead; all four are small; pre-release (no external users). |

---

## 5. User Journeys

### 5.1 Read-while-summarizing (primary)

1. User clicks **Summarize** on a 17-section book.
2. Summarizer starts; each section commits independently (~60s LLM call + ~100ms DB write).
3. User scrolls through sections in the reader panel. Each scroll fires `PUT /api/v1/reading-state`.
4. If a PUT lands during a section's 100ms write window, SQLite queues it (busy_timeout=5000ms). It commits within milliseconds of the summarizer's commit.
5. User sees no errors; reading-state tracking works.

### 5.2 Crash-and-resume

1. Summarize running on a 20-section book; sections 1–11 already committed.
2. Process killed (laptop lid, OOM, Ctrl-C).
3. User re-runs `POST /api/v1/books/{id}/summarize` with same preset.
4. Summarizer loops sections; `summary_repo.get_latest_by_content_and_facets(...)` returns a row for sections 1–11 → skip.
5. Sections 12–20 run fresh. Result: `{completed: 9, skipped: 11, failed: 0}`.

### 5.3 Fresh-library first open

1. User opens `http://localhost:8000/` with 0 books, no custom presets.
2. Frontend fetches `GET /api/v1/reading-presets` once.
3. Response contains 3 system presets + `default_id: "<comfortable-id>"`.
4. Pinia store hydrates both list and active-preset-id from one response. No `/active` call made.
5. Browser console shows zero 4xx/5xx.

### 5.4 Missing image in section markdown

1. Section markdown contains `![alt](images/oops.jpg)` for an image that wasn't extracted.
2. Browser resolves to `/api/v1/books/1/images/oops.jpg` (absolute path from parser rewrite).
3. Backend returns 404 with JSON body `{"detail": "Image not found"}`.
4. Browser shows broken-image icon; no HTML-as-image mislabeling.

---

## 6. Functional Requirements

### 6.1 SQLite Concurrency

| ID | Requirement |
|----|-------------|
| FR-01 | `_on_connect` in `backend/app/db/session.py` executes `PRAGMA busy_timeout=5000` alongside existing WAL and foreign-keys pragmas. |
| FR-02 | The pragma is verified set by a unit test that opens a session, queries `PRAGMA busy_timeout`, asserts `5000`. |

### 6.2 Per-Section Commit

| ID | Requirement |
|----|-------------|
| FR-03 | `SummarizerService.summarize_book()` calls `await self.db.commit()` after each successfully persisted section summary (including eval trace, embedding, search index updates for that section). The in-memory `cumulative_parts` list used for cumulative context is unaffected by commits — it lives in Python state and continues to grow across the loop. |
| FR-04 | A section that fails mid-write (LLM error after DB changes) is rolled back via `await self.db.rollback()`; earlier committed sections are preserved. |
| FR-05 | The final `await self.db.commit()` at the end of `summarize_book()` is removed (or becomes a no-op since nothing is pending). |
| FR-06 | The existing `force=False` skip-completed path at `summarizer_service.py:80-95` continues to work unchanged — the per-section commit makes it effective across runs, it does not need modification. |
| FR-07 | On crash between sections, sections already committed remain in DB; sections in-flight have been rolled back by aiosqlite on connection close. |

### 6.3 Reading Presets Endpoint Collapse

| ID | Requirement |
|----|-------------|
| FR-08 | `GET /api/v1/reading-presets` returns `{items: [...], default_id: <id or null>}`. `default_id` is the id of the preset where `is_active=true`, or null if none. |
| FR-09 | `GET /api/v1/reading-presets/active` is removed from the API. |
| FR-10 | Frontend Pinia `readingPresets` store fetches only the list endpoint; `default_id` populates the active-preset selector. |
| FR-11 | On a fresh database, the `init` flow ensures at least one system preset (`Comfortable`) has `is_active=true` — so `default_id` is never null for a functional install. Verified by a migration check or an init-time guard. |

### 6.4 Image URL Rewriting

| ID | Requirement |
|----|-------------|
| FR-12 | `EpubParser` (and `PdfParser` for inline images) rewrites image references in `content_md` to a parse-time placeholder of the form `__IMG_PLACEHOLDER__:<original-filename>__` (token format chosen so it cannot occur in legitimate markdown). The parser does NOT need to know `image_id`. |
| FR-13 | After `BookService` inserts the `Book` + `BookSection` + `Image` rows and the database has assigned `Image.id`s, it builds a per-section `{filename → image_id}` map from the inserted `Image` rows (which have `filename` populated by the parser), then performs a single string-replace pass over each section's `content_md` to substitute placeholders with `/api/v1/images/{image_id}`. The substitution happens before `db.commit()` for the add-book transaction. |
| FR-14 | Image references whose source filename is missing or unmatched (i.e., no `Image` row was created for that filename, or `Image.filename` is null) are left as the original placeholder string. They will render as broken images in the browser; acceptable per E5. |
| FR-15 | A new route `GET /api/v1/images/{image_id}` returns the image bytes with `Content-Type` from the stored `Image.mime_type`. 404 if no row matches. The route does NOT take `book_id`; image_id is globally unique. |
| FR-16 | Re-imported books use the rewritten URLs. Books ingested before this change require re-import to display images; this is documented in the changelog, not auto-migrated. |

### 6.5 SPA Fallback Tightening

| ID | Requirement |
|----|-------------|
| FR-17 | `CachingStaticFiles.get_response` returns 404 (not SPA fallback) when the requested path ends in one of: `.jpg .jpeg .png .gif .webp .svg .ico .pdf .mp4 .webm .woff .woff2 .ttf .otf .eot .map`. |
| FR-18 | The existing SPA fallback behavior for path-like client routes (e.g., `/library/<id>`) is preserved. |

### 6.6 Database-busy Exception Handler

| ID | Requirement |
|----|-------------|
| FR-19 | A FastAPI exception handler registered in `create_app()` catches `sqlalchemy.exc.OperationalError` whose underlying message contains `database is locked` (i.e., busy_timeout exceeded). It returns HTTP 503 with body `{"detail": "Database busy, please retry"}` and logs the event as `db_busy_timeout` with route + method. |
| FR-20 | Other `OperationalError` causes (schema errors, disk full, etc.) re-raise so they hit the default 500 handler — only the specific busy-timeout case is rewritten. |

---

## 7. API Changes

### 7.1 `GET /api/v1/reading-presets` — modified response

**Before:**
```json
[ {"id": 1, "name": "Comfortable", ...}, {"id": 2, "name": "Compact", ...} ]
```

**After:**
```json
{
  "items": [
    {"id": 1, "name": "Comfortable", "is_active": true, ...},
    {"id": 2, "name": "Compact", "is_active": false, ...}
  ],
  "default_id": 1
}
```

**Errors:** None (empty library → `{items: [], default_id: null}`).

### 7.2 `GET /api/v1/reading-presets/active` — REMOVED

Previously returned a single `ReadingPresetResponse` or 404. No replacement; consumers read `default_id` from the list endpoint and look up the matching item.

### 7.3 `GET /api/v1/images/{image_id}` — new

**Request:** path parameter `image_id` (integer); no body.

**Response (200):**
- Binary body, `Content-Type` = stored `Image.mime_type` (fallback `image/jpeg`).
- `Cache-Control: public, max-age=31536000, immutable` (image_id is an immutable PK).

**Errors:**
- `404` — no `Image` row with that id.

---

## 8. Frontend Design

### 8.1 Reading presets store (`frontend/src/stores/readingPresets.ts`)

- Remove `fetchActive()` method (and any call sites).
- `fetchAll()` now sets both `state.items` and `state.defaultId` from the single response.
- Computed `activePreset` = `state.items.find(p => p.id === state.defaultId)`.

### 8.2 No other frontend changes

- `ReadingArea.vue` is unchanged — it renders whatever markdown the backend ships; the parser change is transparent.
- Cover image rendering is unchanged — it uses `/api/v1/books/{id}/cover` which is unaffected.

---

## 9. Edge Cases

| # | Scenario | Condition | Expected Behavior |
|---|---|---|---|
| E1 | Writer holds lock > 5 seconds | Pathological contention | FR-19 exception handler converts the `OperationalError` to HTTP 503 + `{"detail": "Database busy, please retry"}`. Logged as `db_busy_timeout` with route + method context. |
| E2 | Summarizer fails mid-section after partial DB writes | LLM exception after eval trace insert | `try/except` in the per-section block rolls back that section's changes; sections 1..N-1 remain committed. Job result reports `failed: 1` with section title. |
| E3 | User cancels summarize mid-run | Process killed / client disconnects | Sections already committed persist. No re-run needed; user hits Summarize again and completed sections are skipped (FR-06). |
| E4 | Preset list endpoint returns empty items but DB has presets | Race between seed and first fetch | `init` seeds system presets synchronously before `serve` binds the port, so this cannot happen in the standard flow. If it does (e.g., user wiped DB but kept process running), `default_id: null` and frontend falls back to built-in defaults. |
| E5 | Legacy book with unrewritten image URLs | Book ingested before FR-12 | Images show broken-image icons. Re-importing the book fixes them. Documented in the release notes. |
| E6 | Client requests `/favicon.ico` | Static file present | Served normally by `CachingStaticFiles` with 200. `.ico` is in D5's exclusion list, so the SPA fallback doesn't fire — but the file exists under `app/static/`, so the pre-fallback lookup succeeds. |
| E7 | Client requests a CSS map file that doesn't exist | Sourcemap request after prod build strips them | Returns 404 (`.map` in the deny-list), not HTML. Browser dev tools shows clean "map not available," not a parse error. |

---

## 10. Testing & Verification Strategy

### 10.1 Unit tests (per FR)

- `tests/unit/test_session_pragmas.py` — asserts `PRAGMA busy_timeout` returns 5000 after opening a session (FR-01, FR-02).
- `tests/unit/test_static_files.py` — new tests: missing `.jpg` returns 404, missing `/library/some-id` still returns index.html (FR-16, FR-17).
- `tests/unit/test_reading_presets_api.py` — list endpoint shape test covering `items` + `default_id` (FR-08), active endpoint absent (FR-09).
- `tests/unit/test_image_url_rewrite.py` — parser output contains `__IMG_PLACEHOLDER__:foo.jpg__` for matched images (FR-12); BookService substitutes placeholders to `/api/v1/images/{id}` after insert (FR-13); unmatched filenames remain as placeholders (FR-14).
- `tests/unit/test_images_route.py` — `GET /api/v1/images/{id}` returns bytes + correct `Content-Type` on hit, 404 on miss (FR-15).
- `tests/unit/test_db_busy_handler.py` — synthesize an `OperationalError("database is locked")` via mock; assert the handler returns 503 + correct body (FR-19); assert other `OperationalError`s pass through (FR-20).

### 10.2 Integration tests

- `tests/integration/test_summarizer_incremental_commit.py` (new):
  - Test 1: summarize a 3-section book; after each section, a separate session can read the new summary row (proves commits happen per-section) — covers FR-03.
  - Test 2: monkeypatch the LLM provider to raise on section 2; assert section 1's summary is committed and section 3 is summarized on re-run via skip-logic — covers FR-04, FR-06, FR-07.
- `tests/integration/test_concurrent_write.py` (new):
  - Spawn an asyncio task holding a write transaction open; fire 50 `PUT /api/v1/reading-state` concurrently; assert 0×500 — covers FR-01 (G1).

### 10.3 End-to-end / runtime evidence

- Manual (Playwright MCP or browser): upload a book, start summarize, scroll through sections; grep server log for `500 Internal`. Expected: zero matches.
- `curl -sI http://localhost:8000/books/nonexistent.jpg | head -1` → `HTTP/1.1 404` (G5).
- `curl -sI http://localhost:8000/library/fake-id | head -1` → `HTTP/1.1 200` (SPA deeplink preserved).
- `curl -s http://localhost:8000/api/v1/reading-presets | jq '.default_id'` → non-null integer.

### 10.4 Regression

- Full suite: `uv run pytest -q` → expect 464 + ~8 new = ~472 passing, 0 failing.
- Packaging ladder: `./test.sh ladder` → still passes (no packaging regressions).
- Slow pytest: `./test.sh slow` → still passes.

---

## 11. Rollout

- Single branch `feature/runtime-quality`, single merge to `main`.
- No schema migrations; pragma change is connection-time only.
- No config flags needed — fixes are strictly better behavior with no tradeoff surface.
- Existing books with old image URLs: user re-imports. Changelog entry documents it.

---

## 12. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Should the per-section commit also emit an SSE event so the UI can live-update without polling? Adds a small API surface; deferrable. | Maneesh | Post-release enhancement — not blocking this spec |

---

## 13. Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | (a) FR-12/13 used a clumsy `{book_id}` placeholder substitution. (b) FR-14 keyed image lookup by `(book_id, filename)` but `Image.filename` is nullable and not unique — fragile. (c) E1 promised 503 but no exception handler was specified; default FastAPI returns 500. (d) FR-03 didn't address whether per-section commits affect the in-memory `cumulative_parts` context. | (a, b) Rewrote D4, FR-12–FR-16 to use a `__IMG_PLACEHOLDER__:filename__` token + post-insert substitution to `/api/v1/images/{image_id}`. Image_id is the stable PK; filename is only used for placeholder-to-id matching at substitution time. (c) Added FR-19/FR-20 — a FastAPI exception handler for busy-timeout `OperationalError` returning 503; other OperationalErrors pass through. (d) Added one-liner to FR-03 confirming `cumulative_parts` is unaffected by commits. Renumbered FR-16/17 → FR-17/18 to make room. |
