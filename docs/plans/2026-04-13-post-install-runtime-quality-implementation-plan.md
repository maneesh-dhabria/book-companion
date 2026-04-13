# Post-Install Runtime Quality — Implementation Plan

**Date:** 2026-04-13
**Spec:** `docs/specs/2026-04-13-post-install-runtime-quality-spec.md`
**Requirements:** `docs/requirements/2026-04-12-post-install-runtime-quality.md`

---

## Overview

Six small, focused fixes that together eliminate the runtime quality issues surfaced during the first real end-user session: SQLite busy-timeout, per-section commits in the summarizer, a database-busy exception handler, collapse of the `/reading-presets/active` endpoint into the list endpoint, image URL rewriting at ingestion time, and SPA-fallback hardening so missing assets return real 404s. Tasks land in the order of foundation → behavior → polish so each commit is independently shippable.

**Done when:** A 17-section EPUB ingested, summarized, and read concurrently produces zero `database is locked` 500s; the slow pytest still passes; `./test.sh ladder` still passes; full test suite green at ~472 tests.

**Execution order:**

```
T1 (busy_timeout pragma) ──── foundational, unblocks everything else
  └─ T2 (DB-busy 503 handler)
       └─ T3 (per-section commit)
            └─ T4 (preset endpoint collapse)  [P after T3]
                 └─ T5 (SPA fallback hardening) [P after T3]
                      └─ T6a (new /api/v1/images/{id} route)
                           └─ T6b (parser placeholder emission)
                                └─ T6c (BookService URL substitution)
                                     └─ T7 (final verification)
```

T4 and T5 can land in either order after T3. Keeping T6 as three sub-tasks because each is independently testable and ~30 min apiece.

---

## Decision Log

> Inherits architecture decisions D1–D6 from the spec. Below are implementation-specific decisions made during planning.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| D1 | T1 (pragma) ships before T3 (per-section commit) | (a) Pragma first, (b) Commit first, (c) Together | Pragma alone makes the test suite already-green code more robust. Per-section commits change observable behavior. Ship the safety net first so if T3 has a bug, we still catch fewer 500s. |
| D2 | T2 (exception handler) ships before T3 | (a) Order shown, (b) Defer to end | The handler converts spec edge case E1 from a 500-with-traceback to a clean 503. With T1 in place it should rarely fire, but having it in place when T3 changes summarizer behavior gives us a clean failure mode if a regression slips through. |
| D3 | T6 split into 6a (route) → 6b (parser) → 6c (substitution) | (a) Single task, (b) Three tasks (chosen) | Three commits, three independently revertible changes, three test files. Route is independently testable (just query by ID). Parser is independently testable (just check placeholder format). Substitution is the integration point. |
| D4 | Parser placeholder rewrite happens AFTER `markdownify`, not before | (a) Rewrite HTML before markdown conversion, (b) Rewrite markdown after conversion (chosen) | markdownify produces both `![alt](src)` and inline `<img>` tags. Rewriting at the markdown layer means one regex pass over a single representation rather than coordinating HTML preprocessing with markdownify's output rules. |
| D5 | Substitution map keyed by filename basename, not full path | (a) Full path key, (b) Basename only (chosen) | EPUBs use both `images/foo.jpg` and `../images/foo.jpg` references; basename matching is robust to that. Collisions within a single book section are vanishingly rare and would mean the EPUB itself is malformed. |
| D6 | Per-section commit is wrapped in try/except inside the existing for-loop, not a refactor | (a) Refactor `summarize_book` into smaller helpers, (b) Minimal in-place change (chosen) | Refactoring is out of scope; the fix is one `commit()` line and a `rollback()` in the existing exception handler. Smaller diff, easier review, easier revert. |
| D7 | Frontend `getActivePreset()` is deleted, not deprecated-and-stubbed | (a) Stub returning derived data, (b) Delete (chosen) | Single-user pre-release tool; no external consumers. Deletion forces all callers to use the new shape and prevents drift. |
| D8 | TDD enforced: every task writes the failing test first | — | Catches plan-time misunderstandings of current behavior. Each task verification runs the new test AND the relevant prior tests. |

---

## Code Study Notes

- **`backend/app/db/session.py:21-27`** — existing `_on_connect` listener executes WAL + foreign-keys pragmas. Add `busy_timeout=5000` here. Single function, single test.
- **`backend/app/api/main.py`** — `create_app()` already registers CORS and routers. Adding an exception handler is one `app.exception_handler(...)` call near line 120.
- **`backend/app/api/static_files.py`** — `CachingStaticFiles.get_response()` already has SPA-fallback logic (catch `HTTPException` 404, re-fetch `index.html`). Need a single check before fallback: if path ends in an asset extension, re-raise rather than fall back.
- **`backend/app/services/summarizer/summarizer_service.py:79-233`** — main loop at line 79, single commit at line 233. The skip-completed branch at lines 80-95 already exists and works correctly — per-section commit makes it persist across runs. Need: `await self.db.commit()` after each successful section's writes (around line 215, where eval trace insert completes), `await self.db.rollback()` in the existing `except` branch around line 220. The final commit at line 233 becomes a no-op but harmless to leave.
- **`backend/app/api/routes/reading_presets.py:17-26`** — list endpoint returns `list[ReadingPresetResponse]`. Change to a wrapper response. Active endpoint at lines 30-60 with three-step fallback to deduplicate logic — that fallback moves into a small helper or just gets enforced at init time (the `Comfortable` system preset already has `is_active=true` set during `init`; just need to verify this).
- **`backend/app/services/parser/epub_parser.py:260+`** — `_extract_sections` produces `ParsedSection.content_md` via `markdownify(...)`. Image references will be in the markdown as `![alt](images/foo.jpg)` (or with full path). Best place to inject placeholder rewrite: a small post-process method called right after `markdownify` per section.
- **`backend/app/services/parser/pdf_parser.py`** — pymupdf4llm extracts inline images differently; need to verify whether image refs appear in its markdown output. Likely yes (it embeds `![](path/to/img-N.png)`). Same regex fix applies.
- **`backend/app/services/book_service.py:141-191`** — `_store_book` flushes after `book` insert (line 162), inserts sections + images per loop iteration (line 165-188), commits at line 190. To substitute placeholders we need image IDs, so we need `await self.db.flush()` after the image inserts, then a substitution pass over each section's `content_md`, then commit.
- **`backend/app/db/models.py`** — `Image.id` is the PK, `section_id` is FK, `filename` is nullable string. The substitution helper must skip images with `filename=None` (no source filename to match).
- **`frontend/src/api/readingPresets.ts`** — has `listPresets()` and `getActivePreset()`. Change `listPresets()` return type to `{items, default_id}`. Delete `getActivePreset()`.
- **`frontend/src/stores/readerSettings.ts:58-70, 105-114`** — two call sites of `getActivePreset()`. Both replaced with reading `default_id` from the list response.
- **`backend/tests/unit/test_static_files.py`** — existing tests for SPA fallback assume `/library/some-id` falls back to `index.html`. Those keep passing because `/library/some-id` has no asset extension. Add a new test for `.jpg` returning 404.
- **CLAUDE.md gotchas to respect:** #1 (deferred Image.data must be eager-loaded for the new image route), #6 (LLM provider may be None — not relevant here), #7 (lazy loading after commit), #8 (alembic env reads Settings directly — not relevant here).

---

## Prerequisites

- On `main` branch, working tree clean.
- `cd backend && uv sync --dev` already run (hatchling, twine, etc. installed via earlier work).
- `./test.sh fast` passes as baseline before starting (currently 464 passed, 35 skipped).
- Node 18+ on PATH for any frontend changes (verified during prior packaging work).

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/db/session.py:21-27` | Add `PRAGMA busy_timeout=5000` to connect listener |
| Create | `backend/tests/unit/test_session_pragmas.py` | Verify all three pragmas active on a fresh session |
| Modify | `backend/app/api/main.py` (in `create_app()`) | Register `OperationalError` handler scoped to "database is locked" |
| Create | `backend/tests/unit/test_db_busy_handler.py` | Synthesize OperationalError via a test route, assert 503 + body |
| Modify | `backend/app/services/summarizer/summarizer_service.py:79-233` | `commit()` per section in the success branch, `rollback()` in the failure branch |
| Create | `backend/tests/integration/test_summarizer_incremental_commit.py` | Three-section book; assert section 1 visible from a second session before section 2 finishes |
| Modify | `backend/app/api/routes/reading_presets.py:17-60` | Replace list response shape with `{items, default_id}`; delete `/active` route |
| Modify | `backend/app/api/schemas.py` | Add `ReadingPresetListResponse` schema |
| Modify | `backend/tests/unit/test_reading_presets_api.py` (or wherever existing preset tests live; create if absent) | Test new shape |
| Modify | `frontend/src/api/readingPresets.ts` | `listPresets` returns new shape; delete `getActivePreset` |
| Modify | `frontend/src/stores/readerSettings.ts:58-70, 105-114` | Read `default_id` from list response |
| Modify | `frontend/src/types/index.ts` (or wherever `ReadingPreset` is) | Add `ReadingPresetListResponse` type |
| Modify | `backend/app/api/static_files.py` (CachingStaticFiles class) | Skip SPA fallback for asset-extension paths |
| Modify | `backend/tests/unit/test_static_files.py` | Add `.jpg` returns 404 test; existing `/library/some-id` test still passes |
| Create | `backend/app/api/routes/images.py` | `GET /api/v1/images/{image_id}` returns image bytes |
| Modify | `backend/app/api/main.py` | Register new images router |
| Create | `backend/tests/unit/test_images_route.py` | 200 with bytes + correct mime, 404 on miss |
| Modify | `backend/app/services/parser/epub_parser.py` (after markdownify per section) | Rewrite image refs in markdown to `__IMG_PLACEHOLDER__:<basename>__` tokens |
| Modify | `backend/app/services/parser/pdf_parser.py` (post-extract) | Same rewrite pass on PDF-derived markdown |
| Create | `backend/app/services/parser/image_url_rewrite.py` | Shared helper: `to_placeholder(md)` and `from_placeholder(md, fn_to_id)` |
| Create | `backend/tests/unit/test_image_url_rewrite.py` | Helper unit tests for both directions |
| Modify | `backend/app/services/book_service.py:141-191` (`_store_book`) | After image inserts, flush, substitute placeholders in each section's content_md, then commit |
| Modify | `backend/app/services/book_service.py` (`_re_import_book`) | Same substitution pass for re-imports |
| Create | `backend/tests/integration/test_image_url_substitution.py` | Add a real EPUB with an image; assert content_md contains `/api/v1/images/{N}` after store, route serves bytes |
| Modify | `docs/changelog.md` | User-facing entry: "Concurrent reads/writes no longer fail; partial summarize progress is preserved; clean console; missing images 404 correctly." |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Per-section commit changes the meaning of "summarize_book result counts" — UI might display intermediate counts as final | Low | The job-status route already polls; the result counts at job completion are unchanged. UI shows "in progress" until the route returns. |
| `pymupdf4llm` markdown output format for images is different than expected, regex misses some refs | Medium | T6b includes a real PDF in the test fixture set; verify regex matches both EPUB and PDF outputs. If PDF format differs, extend the regex. |
| The substitution pass in `_store_book` runs after `db.flush()` of images but before `db.commit()` — if substitution raises, the whole add-book is rolled back, which is the right behavior but means a parser regression aborts uploads | Medium | Substitution is a pure string-replace, very low failure surface. Wrap in try/except logging the section title for diagnostics, then re-raise. |
| `OperationalError` exception handler accidentally catches non-busy errors, masking real bugs | Low | FR-19/FR-20: handler checks `"database is locked" in str(exc.orig)` — only that specific cause is rewritten. Test in T2 verifies non-busy OperationalErrors pass through to 500. |
| Frontend store update accidentally breaks the existing "active preset switching" flow (apply preset, save preset, etc.) | Medium | T4's frontend changes touch only the load path; the apply/save/delete paths stay on the existing `activatePreset()`/`createPreset()`/`deletePreset()` API calls. Verify with a manual click-through after T4. |
| Re-importing an existing book triggers `_re_import_book` which doesn't use `_store_book` — image substitution may skip | Medium | T6c includes substitution in `_re_import_book` too. Add an integration test for re-import. |

---

## Rollback

- All changes are code-only — no migrations, no data mutations, no schema changes.
- If T1–T5 land cleanly but T6 breaks: `git revert <T6 commits>` restores existing image behavior (broken but stable).
- If T3 (per-section commit) destabilizes summarization: `git revert <T3 commit>` restores all-or-nothing behavior; T1's busy_timeout still helps with reduced contention.
- Worst case full revert: `git revert <range>` — branch is cleanly stacked.

---

## Tasks

### T1: Add `busy_timeout=5000` pragma

**Goal:** Concurrent writers wait up to 5 seconds instead of failing immediately.
**Spec refs:** FR-01, FR-02; G1.

**Files:**
- Modify: `backend/app/db/session.py` (add line in `_on_connect`)
- Create: `backend/tests/unit/test_session_pragmas.py`

**Steps:**

- [ ] Step 1: Write failing test.
  ```python
  # backend/tests/unit/test_session_pragmas.py
  import pytest
  from sqlalchemy import text
  from app.db.session import create_session_factory
  from app.config import Settings


  @pytest.mark.asyncio
  async def test_busy_timeout_pragma_set(tmp_path, monkeypatch):
      db_path = tmp_path / "library.db"
      monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
      session_factory = create_session_factory(Settings())
      async with session_factory() as session:
          result = await session.execute(text("PRAGMA busy_timeout"))
          assert result.scalar() == 5000


  @pytest.mark.asyncio
  async def test_journal_mode_still_wal(tmp_path, monkeypatch):
      db_path = tmp_path / "library.db"
      monkeypatch.setenv("BOOKCOMPANION_DATABASE__URL", f"sqlite+aiosqlite:///{db_path}")
      session_factory = create_session_factory(Settings())
      async with session_factory() as session:
          result = await session.execute(text("PRAGMA journal_mode"))
          assert result.scalar().lower() == "wal"
  ```

- [ ] Step 2: Run, expect failure.
  Run: `cd backend && uv run pytest tests/unit/test_session_pragmas.py::test_busy_timeout_pragma_set -v`
  Expected: FAIL — pragma returns 0 (default).

- [ ] Step 3: Add pragma in `_on_connect`.
  In `backend/app/db/session.py`, in the `_on_connect` function, add a line after the foreign-keys pragma:
  ```python
  dbapi_conn.execute("PRAGMA busy_timeout=5000")
  ```

- [ ] Step 4: Run, expect pass.
  Run: `cd backend && uv run pytest tests/unit/test_session_pragmas.py -v`
  Expected: 2 passed.

- [ ] Step 5: Lint + commit.
  ```bash
  cd backend && uv run ruff check app/db/session.py tests/unit/test_session_pragmas.py
  git add app/db/session.py tests/unit/test_session_pragmas.py
  git commit -m "fix(db): set sqlite busy_timeout=5000 to wait under write contention"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/test_session_pragmas.py -v` → 2 passed.
- `cd backend && uv run pytest tests/unit/ -q` → previously-passing unit tests still pass.

---

### T2: Database-busy exception handler

**Goal:** When busy_timeout still trips (pathological contention), return a clean 503 instead of a 500 with a SQLAlchemy traceback.
**Spec refs:** FR-19, FR-20; E1.

**Files:**
- Modify: `backend/app/api/main.py` (add handler in `create_app()`)
- Create: `backend/tests/unit/test_db_busy_handler.py`

**Steps:**

- [ ] Step 1: Write failing tests.
  ```python
  # backend/tests/unit/test_db_busy_handler.py
  import sqlite3
  import pytest
  from fastapi import FastAPI
  from httpx import ASGITransport, AsyncClient
  from sqlalchemy.exc import OperationalError

  from app.api.main import register_db_busy_handler  # to be added in step 3


  def _make_app_with_routes():
      app = FastAPI()
      register_db_busy_handler(app)

      @app.get("/_test/busy")
      async def busy():
          raise OperationalError(
              "PRAGMA something",
              {},
              sqlite3.OperationalError("database is locked"),
          )

      @app.get("/_test/other")
      async def other():
          raise OperationalError(
              "INSERT INTO ...",
              {},
              sqlite3.OperationalError("disk I/O error"),
          )

      return app


  @pytest.mark.asyncio
  async def test_busy_returns_503():
      app = _make_app_with_routes()
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
          r = await ac.get("/_test/busy")
      assert r.status_code == 503
      assert r.json() == {"detail": "Database busy, please retry"}


  @pytest.mark.asyncio
  async def test_other_operational_error_returns_500():
      app = _make_app_with_routes()
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
          r = await ac.get("/_test/other")
      assert r.status_code == 500
  ```

- [ ] Step 2: Run, expect failure on import.
  Run: `cd backend && uv run pytest tests/unit/test_db_busy_handler.py -v`
  Expected: FAIL — `register_db_busy_handler` doesn't exist.

- [ ] Step 3: Implement in `backend/app/api/main.py`.
  Add a function near the top of the module:
  ```python
  from fastapi import Request
  from fastapi.responses import JSONResponse
  from sqlalchemy.exc import OperationalError
  import structlog

  _logger = structlog.get_logger()


  def register_db_busy_handler(app: FastAPI) -> None:
      @app.exception_handler(OperationalError)
      async def _handle_op_error(request: Request, exc: OperationalError):
          msg = str(getattr(exc, "orig", exc))
          if "database is locked" in msg:
              _logger.warning(
                  "db_busy_timeout", path=request.url.path, method=request.method
              )
              return JSONResponse(
                  status_code=503,
                  content={"detail": "Database busy, please retry"},
              )
          # Non-busy OperationalError: return generic 500 (FastAPI exception
          # handlers are terminal — `raise exc` here would not cascade).
          _logger.error(
              "operational_error", path=request.url.path, method=request.method, error=msg
          )
          return JSONResponse(
              status_code=500,
              content={"detail": "Internal server error"},
          )
  ```
  Then in `create_app()`, after the routers are included, call `register_db_busy_handler(app)`.

- [ ] Step 4: Run tests, expect pass.
  Run: `cd backend && uv run pytest tests/unit/test_db_busy_handler.py -v`
  Expected: 2 passed.

- [ ] Step 5: Lint + commit.
  ```bash
  cd backend && uv run ruff check app/api/main.py tests/unit/test_db_busy_handler.py
  git add app/api/main.py tests/unit/test_db_busy_handler.py
  git commit -m "feat(api): convert SQLite busy-timeout OperationalError to 503"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/test_db_busy_handler.py -v` → 2 passed.
- `cd backend && uv run pytest -q` → no regressions vs baseline.

---

### T3: Per-section commit in summarizer

**Goal:** Each successful section commits independently; failures roll back to the last commit; existing skip-completed logic becomes effective across runs.
**Spec refs:** FR-03, FR-04, FR-05, FR-06, FR-07; G2, G3.

**Files:**
- Modify: `backend/app/services/summarizer/summarizer_service.py` (around lines 79–233)
- Create: `backend/tests/integration/test_summarizer_incremental_commit.py`

**Steps:**

- [ ] Step 0: Read the actual `summarize_book()` signature and existing test fixture pattern.
  Run: `cd backend && grep -n "def summarize_book" app/services/summarizer/summarizer_service.py`
  Run: `cd backend && head -50 tests/conftest.py`
  Adapt the test below to whatever fixture name is in use (`db_session`, `async_session`, etc.) and to the real `summarize_book` parameter list. The PRESET name `"practitioner_bullets"` should exist in `prompts/presets/`; verify with `ls prompts/presets/`.

- [ ] Step 1: Write failing integration test (uses second-session polling, no callback dependency).
  ```python
  # backend/tests/integration/test_summarizer_incremental_commit.py
  import pytest
  from sqlalchemy import select
  from app.db.models import Book, BookSection, BookStatus, Summary, SummaryContentType
  from app.config import Settings
  from app.db.session import create_session_factory


  @pytest.fixture
  async def three_section_book(db_session):
      book = Book(title="Test", file_data=b"x", file_hash="h1",
                  file_format="epub", file_size_bytes=1, status=BookStatus.PARSED)
      db_session.add(book)
      await db_session.flush()
      for i in range(3):
          db_session.add(BookSection(
              book_id=book.id, title=f"S{i}", order_index=i, depth=1,
              content_md=f"Section {i} content. " * 100,
          ))
      await db_session.commit()
      return book


  class StubLLM:
      """LLM stub returning predictable summary text."""
      def __init__(self):
          self.call_count = 0

      async def generate(self, prompt: str, **kw):
          self.call_count += 1
          return {"summary": "stub summary text " * 20}


  @pytest.mark.asyncio
  async def test_summarize_commits_each_section(three_section_book, db_session):
      """All three section summaries are committed (visible from a fresh session)."""
      from app.services.summarizer import SummarizerService
      service = SummarizerService(db_session, StubLLM(), Settings())
      result = await service.summarize_book(
          three_section_book.id, preset_name="practitioner_bullets"
      )
      assert result["completed"] == 3

      # Fresh session in a separate transaction proves commits happened.
      sf = create_session_factory(Settings())
      async with sf() as fresh:
          rows = (await fresh.execute(
              select(Summary).where(Summary.content_type == SummaryContentType.SECTION)
          )).scalars().all()
          assert len(rows) == 3


  @pytest.mark.asyncio
  async def test_summarize_skips_already_summarized_on_rerun(three_section_book, db_session):
      """Re-running summarize on a complete book skips all sections (no LLM calls)."""
      from app.services.summarizer import SummarizerService
      llm = StubLLM()
      service = SummarizerService(db_session, llm, Settings())

      r1 = await service.summarize_book(three_section_book.id, preset_name="practitioner_bullets")
      assert r1["completed"] == 3
      calls_after_first = llm.call_count

      r2 = await service.summarize_book(three_section_book.id, preset_name="practitioner_bullets")
      assert r2["skipped"] >= 3
      assert r2["completed"] == 0
      assert llm.call_count == calls_after_first, "no new LLM calls on re-run"


  @pytest.mark.asyncio
  async def test_summarize_partial_failure_preserves_earlier_sections(three_section_book, db_session):
      """If section 2 fails mid-summarize, section 1 stays committed."""
      from app.services.summarizer import SummarizerService

      class FailingOnSecondLLM:
          def __init__(self):
              self.call_count = 0
          async def generate(self, prompt: str, **kw):
              self.call_count += 1
              if self.call_count == 2:
                  raise RuntimeError("simulated mid-run failure")
              return {"summary": "ok " * 30}

      service = SummarizerService(db_session, FailingOnSecondLLM(), Settings())
      result = await service.summarize_book(
          three_section_book.id, preset_name="practitioner_bullets"
      )
      # At least section 1 should be committed even though section 2 failed
      sf = create_session_factory(Settings())
      async with sf() as fresh:
          rows = (await fresh.execute(
              select(Summary).where(Summary.content_type == SummaryContentType.SECTION)
          )).scalars().all()
          assert len(rows) >= 1, "section 1 must be committed despite later failure"
      assert result["failed"], "summarize_book must report the failure"


  @pytest.mark.slow
  @pytest.mark.asyncio
  async def test_concurrent_writes_no_500s_under_busy_timeout(three_section_book, db_session):
      """While summarize is running, 50 concurrent reading-state PUTs return non-5xx.

      Regression test for the post-install runtime quality bug. Marked `slow` because
      it spins a real ASGI app and parallel HTTP clients (~5s).
      """
      import asyncio
      from httpx import ASGITransport, AsyncClient
      from app.api.main import create_app
      from app.services.summarizer import SummarizerService

      app = create_app()
      transport = ASGITransport(app=app)

      async def hammer():
          async with AsyncClient(transport=transport, base_url="http://t") as ac:
              return await ac.put(
                  "/api/v1/reading-state",
                  headers={"User-Agent": "ConcurrencyTest"},
                  json={"book_id": three_section_book.id, "section_id": 1,
                        "scroll_position": 0, "content_mode": "summary"},
              )

      async def summarize_now():
          service = SummarizerService(db_session, StubLLM(), Settings())
          return await service.summarize_book(
              three_section_book.id, preset_name="practitioner_bullets"
          )

      # Fire summarize and 50 parallel writes together
      results = await asyncio.gather(
          summarize_now(),
          *[hammer() for _ in range(50)],
          return_exceptions=True,
      )
      put_results = results[1:]
      statuses = [r.status_code for r in put_results if hasattr(r, "status_code")]
      assert statuses, "no PUT responses captured"
      assert all(s < 500 for s in statuses), (
          f"some PUTs returned 5xx: {[s for s in statuses if s >= 500]}"
      )
  ```

  Note: the existing test fixtures may use a different session-fixture name in `conftest.py` (verified in Step 0); adapt accordingly.

- [ ] Step 2: Run, expect failure.
  Run: `cd backend && uv run pytest tests/integration/test_summarizer_incremental_commit.py -v`
  Expected: FAIL — `test_summarize_commits_after_each_section` fails because all commits happen at end (second-session read inside the loop sees nothing).

- [ ] Step 3: Modify `summarize_book` in `summarizer_service.py`.
  In the for-loop around line 79, after the section's summary is successfully persisted (just before the next iteration), add `await self.db.commit()`. In the existing exception handler that catches LLM/persist failures, add `await self.db.rollback()` before recording the failure. The end-of-function commit at line 233 can remain — it's a no-op now but doesn't hurt.
  Pseudocode:
  ```python
  for i, section in enumerate(sections):
      # ... existing skip-completed check ...
      try:
          # ... LLM call, summary insert, eval trace, embedding ...
          completed += 1
          await self.db.commit()  # NEW
      except Exception as e:
          await self.db.rollback()  # NEW
          failed.append(...)
  ```

- [ ] Step 4: Run tests, expect pass.
  Run (default suite, excludes slow): `cd backend && uv run pytest tests/integration/test_summarizer_incremental_commit.py -v`
  Expected: 3 passed (the slow concurrency test is excluded by `addopts="-m 'not slow'"`).
  Run (slow): `cd backend && uv run pytest -m slow --override-ini='addopts=' tests/integration/test_summarizer_incremental_commit.py -v`
  Expected: 1 passed (just the concurrency stress test).

- [ ] Step 5: Run full suite to catch regressions.
  Run: `cd backend && uv run pytest -q`
  Expected: ≥465 passed (one new test file with 2 tests counted in baseline).

- [ ] Step 6: Lint + commit.
  ```bash
  cd backend && uv run ruff check app/services/summarizer/summarizer_service.py tests/integration/test_summarizer_incremental_commit.py
  git add app/services/summarizer/summarizer_service.py tests/integration/test_summarizer_incremental_commit.py
  git commit -m "fix(summarizer): commit after each section so progress is durable and resumable"
  ```

**Inline verification:**
- New tests pass: `pytest tests/integration/test_summarizer_incremental_commit.py -v` → 2 passed.
- Full suite: `pytest -q` → no regressions.
- Manual: `bookcompanion summarize <id>` followed by `bookcompanion summarize <id>` (force=False) — second run reports `skipped: N` matching the first run's `completed: N`.

---

### T4: Reading-presets endpoint collapse

**Goal:** `GET /api/v1/reading-presets` returns `{items, default_id}`; `/active` deleted; frontend store uses one fetch.
**Spec refs:** FR-08, FR-09, FR-10, FR-11; §7.1, §7.2, §8.1.

**Files:**
- Modify: `backend/app/api/routes/reading_presets.py:17-60`
- Modify: `backend/app/api/schemas.py` (add `ReadingPresetListResponse`)
- Create or modify: `backend/tests/unit/test_reading_presets_api.py`
- Modify: `frontend/src/api/readingPresets.ts`
- Modify: `frontend/src/stores/readerSettings.ts:58-70, 105-114`
- Modify: `frontend/src/types/index.ts` (or wherever the `ReadingPreset` type lives)

**Steps:**

- [ ] Step 1: Write failing backend test.
  Read `backend/tests/unit/` to find existing preset test file. If absent, create:
  ```python
  # backend/tests/unit/test_reading_presets_api.py
  import pytest
  from httpx import ASGITransport, AsyncClient
  from app.api.main import create_app


  @pytest.mark.asyncio
  async def test_list_returns_items_and_default_id(seeded_presets_db):
      """List endpoint returns {items: [...], default_id: <id>}."""
      app = create_app()
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
          r = await ac.get("/api/v1/reading-presets")
      assert r.status_code == 200
      body = r.json()
      assert "items" in body and isinstance(body["items"], list)
      assert "default_id" in body
      assert body["default_id"] is not None  # Comfortable preset is_active by default
      # default_id matches the item with is_active=true
      active_items = [i for i in body["items"] if i["is_active"]]
      assert len(active_items) == 1
      assert active_items[0]["id"] == body["default_id"]


  @pytest.mark.asyncio
  async def test_active_endpoint_removed(seeded_presets_db):
      app = create_app()
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
          r = await ac.get("/api/v1/reading-presets/active")
      assert r.status_code == 404
  ```
  The `seeded_presets_db` fixture should seed system presets with one having `is_active=true`. Use the existing init/seeding code as reference.

- [ ] Step 2: Run, expect failure.
  Run: `cd backend && uv run pytest tests/unit/test_reading_presets_api.py -v`
  Expected: FAIL — list still returns a bare array; `/active` still exists.

- [ ] Step 3: Update backend.
  In `backend/app/api/schemas.py`, add:
  ```python
  class ReadingPresetListResponse(BaseModel):
      items: list[ReadingPresetResponse]
      default_id: int | None
  ```
  In `backend/app/api/routes/reading_presets.py`, replace `list_reading_presets`:
  ```python
  @router.get("", response_model=ReadingPresetListResponse)
  async def list_reading_presets(db: AsyncSession = Depends(get_db)):
      result = await db.execute(
          select(ReadingPreset).order_by(
              ReadingPreset.is_system.desc(), ReadingPreset.name.asc()
          )
      )
      items = list(result.scalars().all())
      default = next((p for p in items if p.is_active), None)
      return {"items": items, "default_id": default.id if default else None}
  ```
  Delete the `get_active_preset` route entirely.

- [ ] Step 4: Run backend tests, expect pass.
  Run: `cd backend && uv run pytest tests/unit/test_reading_presets_api.py -v`
  Expected: 2 passed.

- [ ] Step 5: Update frontend API client (`frontend/src/api/readingPresets.ts`).
  Change `listPresets` to:
  ```ts
  export interface ReadingPresetListResponse {
    items: ReadingPreset[]
    default_id: number | null
  }

  export async function listPresets(): Promise<ReadingPresetListResponse> {
    return apiClient.get<ReadingPresetListResponse>('/reading-presets')
  }
  ```
  Delete `getActivePreset`.

- [ ] Step 6: Update store (`frontend/src/stores/readerSettings.ts`).
  Replace `loadPresets()`:
  ```ts
  async function loadPresets() {
    loading.value = true
    try {
      const resp = await listPresets()
      presets.value = resp.items
      const active = resp.items.find((p) => p.id === resp.default_id) ?? resp.items[0]
      if (active) {
        activePreset.value = active
        applySettingsFromPreset(active)
      }
    } catch {
      // Use defaults if API unavailable
    } finally {
      loading.value = false
    }
  }
  ```
  Update `deleteUserPreset`:
  ```ts
  async function deleteUserPreset(id: number) {
    await deletePresetApi(id)
    presets.value = presets.value.filter((p) => p.id !== id)
    if (activePreset.value?.id === id) {
      const resp = await listPresets()
      presets.value = resp.items
      const active = resp.items.find((p) => p.id === resp.default_id) ?? resp.items[0]
      if (active) {
        activePreset.value = active
        applySettingsFromPreset(active)
      }
    }
  }
  ```
  Update `applyPreset` to refresh from the new shape:
  ```ts
  // After activatePreset(id):
  presets.value = (await listPresets()).items
  ```
  Remove the `getActivePreset` import at the top of the file.

- [ ] Step 7: Frontend type-check + build.
  Run: `cd frontend && npm run type-check && npm run build`
  Expected: clean compilation.

- [ ] Step 8: Lint backend + commit.
  ```bash
  cd backend && uv run ruff check app/api/routes/reading_presets.py app/api/schemas.py tests/unit/test_reading_presets_api.py
  git add backend/app/api/routes/reading_presets.py backend/app/api/schemas.py backend/tests/unit/test_reading_presets_api.py frontend/src/api/readingPresets.ts frontend/src/stores/readerSettings.ts
  git commit -m "feat(presets): collapse /active into list endpoint with default_id"
  ```

**Inline verification:**
- Backend tests: `pytest tests/unit/test_reading_presets_api.py -v` → 2 passed.
- Backend full suite: `pytest -q` → no regressions.
- Frontend: `npm run type-check && npm run build` → 0 errors.
- Manual (after all tasks): with the dev server running, open the app, reload, check browser console — no `/reading-presets/active` request, no 404s.

---

### T5: SPA fallback hardening

**Goal:** Missing image and other binary asset requests return 404, not HTML.
**Spec refs:** FR-17, FR-18; G5.

**Files:**
- Modify: `backend/app/api/static_files.py` (CachingStaticFiles)
- Modify: `backend/tests/unit/test_static_files.py` (add asset-extension tests)

**Steps:**

- [ ] Step 1: Write failing tests.
  Append to `backend/tests/unit/test_static_files.py`:
  ```python
  def test_missing_jpg_returns_404(static_tree):
      r = _client(static_tree).get("/books/nonexistent.jpg")
      assert r.status_code == 404


  def test_missing_png_returns_404(static_tree):
      r = _client(static_tree).get("/some/path/missing.png")
      assert r.status_code == 404


  def test_missing_pdf_returns_404(static_tree):
      r = _client(static_tree).get("/files/manual.pdf")
      assert r.status_code == 404


  def test_missing_sourcemap_returns_404(static_tree):
      r = _client(static_tree).get("/assets/something.map")
      assert r.status_code == 404


  def test_spa_deeplink_still_falls_back(static_tree):
      """Existing behavior: client-side routes serve index.html so refresh works."""
      r = _client(static_tree).get("/library/some-book-id")
      assert r.status_code == 200
      assert "<html>" in r.text or "Vite" in r.text or "doctype" in r.text.lower()
  ```

- [ ] Step 2: Run, expect failure on the four "missing asset" tests, pass on the deeplink test.
  Run: `cd backend && uv run pytest tests/unit/test_static_files.py -v`
  Expected: 4 NEW failures (200 returned where 404 expected); existing pass.

- [ ] Step 3: Modify `CachingStaticFiles.get_response` in `backend/app/api/static_files.py`.
  Add a constant near the class:
  ```python
  _ASSET_EXTENSIONS = (
      ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
      ".pdf", ".mp4", ".webm",
      ".woff", ".woff2", ".ttf", ".otf", ".eot",
      ".map",
  )
  ```
  In the existing `except (HTTPException, StarletteHTTPException) as exc:` block, before the SPA fallback runs, check the path:
  ```python
  if exc.status_code != 404 or path.startswith("assets/") or path.lower().endswith(_ASSET_EXTENSIONS):
      raise
  ```
  (Combine with the existing `path.startswith("assets/")` check rather than adding a separate branch.)

- [ ] Step 4: Run tests, expect all pass.
  Run: `cd backend && uv run pytest tests/unit/test_static_files.py -v`
  Expected: all (existing + 5 new) pass.

- [ ] Step 5: Lint + commit.
  ```bash
  cd backend && uv run ruff check app/api/static_files.py tests/unit/test_static_files.py
  git add app/api/static_files.py tests/unit/test_static_files.py
  git commit -m "fix(static): missing asset paths return 404 instead of SPA index.html"
  ```

**Inline verification:**
- Static-file tests: `pytest tests/unit/test_static_files.py -v` → all pass.
- Manual: `curl -sI http://localhost:8000/books/nonexistent.jpg | head -1` → `HTTP/1.1 404 Not Found`.
- Manual: `curl -sI http://localhost:8000/library/fake-id | head -1` → `HTTP/1.1 200 OK` (deeplink preserved).

---

### T6a: New `GET /api/v1/images/{image_id}` route

**Goal:** Stand up the route that section content_md will reference, before changing anything that emits its URL.
**Spec refs:** FR-15; §7.3.

**Files:**
- Create: `backend/app/api/routes/images.py`
- Modify: `backend/app/api/main.py` (register new router)
- Create: `backend/tests/unit/test_images_route.py`

**Steps:**

- [ ] Step 1: Write failing test.
  ```python
  # backend/tests/unit/test_images_route.py
  import pytest
  from httpx import ASGITransport, AsyncClient
  from app.api.main import create_app
  from app.db.models import Book, BookSection, Image, BookStatus


  @pytest.mark.asyncio
  async def test_get_image_returns_bytes(db_session):
      book = Book(title="t", file_data=b"x", file_hash="h", file_format="epub",
                  file_size_bytes=1, status=BookStatus.PARSED)
      db_session.add(book); await db_session.flush()
      section = BookSection(book_id=book.id, title="s", order_index=0, depth=1, content_md="x")
      db_session.add(section); await db_session.flush()
      image = Image(section_id=section.id, data=b"\x89PNG\r\n\x1a\n",
                    mime_type="image/png", filename="cover.png")
      db_session.add(image); await db_session.commit()

      app = create_app()
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
          r = await ac.get(f"/api/v1/images/{image.id}")
      assert r.status_code == 200
      assert r.content == b"\x89PNG\r\n\x1a\n"
      assert r.headers["content-type"] == "image/png"
      assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


  @pytest.mark.asyncio
  async def test_get_image_404_when_missing():
      app = create_app()
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
          r = await ac.get("/api/v1/images/99999")
      assert r.status_code == 404
  ```

- [ ] Step 2: Run, expect failure.
  Run: `cd backend && uv run pytest tests/unit/test_images_route.py -v`
  Expected: FAIL — route doesn't exist (404 from FastAPI's not-found, but the *content* won't match either).

- [ ] Step 3: Create `backend/app/api/routes/images.py`.
  ```python
  """Image serving — looks up Image by id and returns the binary."""
  from fastapi import APIRouter, Depends, HTTPException, Response
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy.orm import undefer
  from sqlalchemy import select

  from app.api.deps import get_db
  from app.db.models import Image

  router = APIRouter(prefix="/api/v1/images", tags=["images"])


  @router.get("/{image_id}")
  async def get_image(image_id: int, db: AsyncSession = Depends(get_db)):
      # `data` is deferred on the Image model — undefer eagerly.
      result = await db.execute(
          select(Image).where(Image.id == image_id).options(undefer(Image.data))
      )
      image = result.scalar_one_or_none()
      if image is None:
          raise HTTPException(status_code=404, detail="Image not found")
      return Response(
          content=image.data,
          media_type=image.mime_type or "image/jpeg",
          headers={"Cache-Control": "public, max-age=31536000, immutable"},
      )
  ```

- [ ] Step 4: Register router in `backend/app/api/main.py`.
  Import `images` alongside the other route imports, then `app.include_router(images.router)` near the other includes.

- [ ] Step 5: Run, expect pass.
  Run: `cd backend && uv run pytest tests/unit/test_images_route.py -v`
  Expected: 2 passed.

- [ ] Step 6: Lint + commit.
  ```bash
  cd backend && uv run ruff check app/api/routes/images.py app/api/main.py tests/unit/test_images_route.py
  git add app/api/routes/images.py app/api/main.py tests/unit/test_images_route.py
  git commit -m "feat(api): add GET /api/v1/images/{id} route serving stored image bytes"
  ```

**Inline verification:**
- New tests pass: `pytest tests/unit/test_images_route.py -v` → 2 passed.
- Full suite: `pytest -q` → no regressions.

---

### T6b: Parser placeholder emission

**Goal:** EPUB and PDF parsers replace image references in their markdown output with `__IMG_PLACEHOLDER__:<basename>__` tokens.
**Spec refs:** FR-12, FR-14.

**Files:**
- Create: `backend/app/services/parser/image_url_rewrite.py`
- Modify: `backend/app/services/parser/epub_parser.py` (call helper after markdownify)
- Modify: `backend/app/services/parser/pdf_parser.py` (call helper after extraction)
- Create: `backend/tests/unit/test_image_url_rewrite.py`

**Steps:**

- [ ] Step 1: Write failing helper tests.
  ```python
  # backend/tests/unit/test_image_url_rewrite.py
  from app.services.parser.image_url_rewrite import to_placeholder, from_placeholder


  def test_markdown_image_to_placeholder():
      md = "Here is an image: ![alt](images/foo.jpg) end."
      out = to_placeholder(md)
      assert "__IMG_PLACEHOLDER__:foo.jpg__" in out
      assert "images/foo.jpg" not in out


  def test_html_img_tag_to_placeholder():
      md = '<img src="images/bar.png" alt="b" />'
      out = to_placeholder(md)
      assert "__IMG_PLACEHOLDER__:bar.png__" in out


  def test_path_with_subdirs_uses_basename():
      md = "![](OEBPS/images/baz.jpeg)"
      out = to_placeholder(md)
      assert "__IMG_PLACEHOLDER__:baz.jpeg__" in out


  def test_non_image_links_untouched():
      md = "[link](https://example.com)"
      assert to_placeholder(md) == md


  def test_from_placeholder_substitutes_known_filenames():
      md = "before __IMG_PLACEHOLDER__:foo.jpg__ middle __IMG_PLACEHOLDER__:bar.png__ end"
      out = from_placeholder(md, {"foo.jpg": 11, "bar.png": 22})
      assert "/api/v1/images/11" in out
      assert "/api/v1/images/22" in out
      assert "__IMG_PLACEHOLDER__" not in out


  def test_from_placeholder_leaves_unknown_filenames():
      md = "__IMG_PLACEHOLDER__:missing.jpg__"
      out = from_placeholder(md, {})
      assert out == md
  ```

- [ ] Step 2: Run, expect failure (module doesn't exist).
  Run: `cd backend && uv run pytest tests/unit/test_image_url_rewrite.py -v`
  Expected: FAIL — `image_url_rewrite` module not found.

- [ ] Step 3: Create the helper.
  ```python
  # backend/app/services/parser/image_url_rewrite.py
  """Image URL rewriting between parse-time placeholders and stored absolute URLs."""
  from __future__ import annotations

  import re

  # Markdown image: ![alt](path)
  _MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
  # HTML <img src="path">
  _HTML_IMG = re.compile(r'(<img\s[^>]*?src=)([\"\'])([^\"\']+)([\"\'])([^>]*>)', re.IGNORECASE)
  _PLACEHOLDER = re.compile(r"__IMG_PLACEHOLDER__:([^_]+(?:_[^_]+)*?)__")


  def _basename(path: str) -> str:
      return path.rsplit("/", 1)[-1]


  def to_placeholder(md: str) -> str:
      """Replace image refs with __IMG_PLACEHOLDER__:<basename>__ tokens."""
      def md_repl(m: re.Match) -> str:
          alt, src = m.group(1), m.group(2)
          # Skip absolute URLs (http(s)://) — they're not local images
          if src.startswith(("http://", "https://", "data:")):
              return m.group(0)
          return f"![{alt}](__IMG_PLACEHOLDER__:{_basename(src)}__)"

      def html_repl(m: re.Match) -> str:
          prefix, q1, src, q2, suffix = m.groups()
          if src.startswith(("http://", "https://", "data:")):
              return m.group(0)
          return f"{prefix}{q1}__IMG_PLACEHOLDER__:{_basename(src)}__{q2}{suffix}"

      out = _MD_IMG.sub(md_repl, md)
      out = _HTML_IMG.sub(html_repl, out)
      return out


  def from_placeholder(md: str, filename_to_image_id: dict[str, int]) -> str:
      """Substitute placeholders with /api/v1/images/{id}; leave unknown filenames untouched."""
      def repl(m: re.Match) -> str:
          fn = m.group(1)
          image_id = filename_to_image_id.get(fn)
          if image_id is None:
              return m.group(0)  # leave as placeholder; will 404 on fetch
          return f"/api/v1/images/{image_id}"
      return _PLACEHOLDER.sub(repl, md)
  ```

- [ ] Step 4: Run helper tests, expect pass.
  Run: `cd backend && uv run pytest tests/unit/test_image_url_rewrite.py -v`
  Expected: 6 passed.

- [ ] Step 5: Wire helper into EPUB parser.
  In `backend/app/services/parser/epub_parser.py`, near the top add:
  ```python
  from app.services.parser.image_url_rewrite import to_placeholder
  ```
  In `_extract_sections`, after the markdown is produced for each section (after the `markdownify(...).strip()` call around line 269), wrap with `to_placeholder(...)`. The simplest place: where `content_map[item.get_name()] = md.strip()` — change to `content_map[item.get_name()] = to_placeholder(md.strip())`.

- [ ] Step 6: Wire helper into PDF parser.
  Locate the markdown emission point first:
  ```bash
  cd backend && grep -n "to_markdown\|content_md\s*=" app/services/parser/pdf_parser.py
  ```
  At each line where a string is assigned to `content_md` (or to a local that becomes `content_md`), wrap with `to_placeholder(...)`. Add the import at the top:
  ```python
  from app.services.parser.image_url_rewrite import to_placeholder
  ```
  If the file's structure makes wrapping at multiple sites unwieldy, do a single pass on the final `parsed.sections` list at the end of `parse()`:
  ```python
  for s in parsed.sections:
      if s.content_md:
          s.content_md = to_placeholder(s.content_md)
  ```
  Either approach is acceptable — pick whichever fits the file's existing structure with the smaller diff.

- [ ] Step 7: Run parser tests + helper tests.
  Run: `cd backend && uv run pytest tests/unit/test_image_url_rewrite.py tests/integration/ -k "parser or epub or pdf" -v`
  Expected: green. (Existing parser tests should still pass because they don't assert on image src values inside content_md, and if any do, the new placeholder format is what they should now see.)

- [ ] Step 8: Lint + commit.
  ```bash
  cd backend && uv run ruff check app/services/parser/image_url_rewrite.py app/services/parser/epub_parser.py app/services/parser/pdf_parser.py tests/unit/test_image_url_rewrite.py
  git add app/services/parser/image_url_rewrite.py app/services/parser/epub_parser.py app/services/parser/pdf_parser.py tests/unit/test_image_url_rewrite.py
  git commit -m "feat(parser): emit image URL placeholders for post-insert substitution"
  ```

**Inline verification:**
- Helper tests: `pytest tests/unit/test_image_url_rewrite.py -v` → 6 passed.
- Adjacent parser tests: green.
- Manual: parse a small EPUB locally and grep its `content_md` — should see `__IMG_PLACEHOLDER__:` tokens.

---

### T6c: BookService URL substitution

**Goal:** After image inserts, build filename→id map per section and substitute placeholders to absolute URLs in `content_md` before commit.
**Spec refs:** FR-13.

**Files:**
- Modify: `backend/app/services/book_service.py` (`_store_book` and `_re_import_book`)
- Create: `backend/tests/integration/test_image_url_substitution.py`

**Steps:**

- [ ] Step 1: Write failing integration test.
  ```python
  # backend/tests/integration/test_image_url_substitution.py
  import pytest
  from pathlib import Path
  from sqlalchemy import select

  from app.services.book_service import BookService
  from app.config import Settings
  from app.db.models import BookSection, Image


  @pytest.mark.asyncio
  async def test_store_book_substitutes_image_placeholders(db_session, tmp_path):
      """An EPUB with images, after _store_book, has /api/v1/images/{id} URLs in content_md."""
      # Use existing fixture EPUB if available; otherwise mark xfail with reason
      fixture = Path(__file__).resolve().parents[1] / "fixtures" / "sample_epub"
      epubs = list(fixture.glob("*.epub"))
      if not epubs:
          pytest.skip("no EPUB fixture available")

      service = BookService(db_session, Settings())
      book = await service.add_book(epubs[0])

      sections = (await db_session.execute(
          select(BookSection).where(BookSection.book_id == book.id)
      )).scalars().all()

      images = (await db_session.execute(
          select(Image).join(BookSection).where(BookSection.book_id == book.id)
      )).scalars().all()

      if not images:
          pytest.skip("fixture EPUB has no images")

      # At least one section should reference at least one image via the new URL shape
      url_pattern = "/api/v1/images/"
      sections_with_imgs = [s for s in sections if url_pattern in (s.content_md or "")]
      assert sections_with_imgs, (
          f"no section content_md contains {url_pattern}; "
          f"images extracted: {len(images)}, sections: {len(sections)}"
      )

      # No remaining placeholder tokens (or only those for missing/null filenames)
      for s in sections:
          if "__IMG_PLACEHOLDER__" in (s.content_md or ""):
              # Allowed only if there's no matching Image with that filename
              # (we don't deeply validate the exact pairing here)
              pass
  ```

- [ ] Step 2: Run, expect failure.
  Run: `cd backend && uv run pytest tests/integration/test_image_url_substitution.py -v`
  Expected: FAIL — substitution doesn't happen yet, so `content_md` either still has placeholders or original relative paths.

- [ ] Step 3: Modify `_store_book` in `backend/app/services/book_service.py`.
  Around lines 165-190, after the inner `for pi in ps.images:` loop and before `db.commit()`, add a flush + substitution pass:
  ```python
  # ... existing section + image inserts ...

  # Get image IDs (flush assigns them).
  await self.db.flush()

  # Single query with eager image loading — avoids N+1.
  from sqlalchemy import select
  from sqlalchemy.orm import selectinload
  from app.db.models import BookSection
  from app.services.parser.image_url_rewrite import from_placeholder

  result = await self.db.execute(
      select(BookSection)
      .where(BookSection.book_id == book.id)
      .options(selectinload(BookSection.images))
  )
  for section in result.scalars().all():
      if "__IMG_PLACEHOLDER__" not in (section.content_md or ""):
          continue
      fn_map: dict[str, int] = {}
      for img in section.images:
          if img.filename:
              fn_map[img.filename.rsplit("/", 1)[-1]] = img.id
      if fn_map:
          section.content_md = from_placeholder(section.content_md, fn_map)

  await self.db.commit()
  ```
  (Refactor as the implementor sees fit — the import positions, helper extraction, etc. are judgment calls. Behavior contract: after `_store_book` returns, every section's `content_md` contains `/api/v1/images/{id}` URLs for images that have a known filename.)

- [ ] Step 4: Mirror the substitution pass in `_re_import_book`.
  After the section-update loop in `_re_import_book` and before its commit, run the same substitution. Reuse a helper if you've extracted one in step 3.

- [ ] Step 5: Run integration test, expect pass.
  Run: `cd backend && uv run pytest tests/integration/test_image_url_substitution.py -v`
  Expected: pass (or skip if no fixture EPUB has images, in which case download a fixture per `tests/fixtures/README.md`).

- [ ] Step 6: Run full suite for regressions.
  Run: `cd backend && uv run pytest -q`
  Expected: ≥470 passed.

- [ ] Step 7: Lint + commit.
  ```bash
  cd backend && uv run ruff check app/services/book_service.py tests/integration/test_image_url_substitution.py
  git add app/services/book_service.py tests/integration/test_image_url_substitution.py
  git commit -m "feat(parser): substitute image placeholders to /api/v1/images/{id} on store"
  ```

**Inline verification:**
- Integration test: `pytest tests/integration/test_image_url_substitution.py -v` → pass.
- Full suite: `pytest -q` → no regressions.
- End-to-end manual (after the dev server starts in T7): import a book with images, open a section in the reader, view-source the rendered HTML — `<img src="/api/v1/images/N">`. Network panel shows 200s for those URLs.

---

### T7: Final Verification

**Goal:** Confirm the entire feature lands correctly end-to-end against an installed wheel, with no regressions.

- [ ] **Lint & format:** `cd backend && uv run ruff check . && uv run ruff format --check .`
  Expected: same baseline of pre-existing errors as before this work; no new errors in any modified file.

- [ ] **Backend full test suite:** `cd backend && uv run pytest -q`
  Expected: 464 baseline + ~13 new (2 pragmas, 2 db-busy, 2 incremental commit, 2 preset, 5 static-files, 2 image route, 6 helper, ≥1 image substitution) ≈ 480 passed; 0 failed.

- [ ] **Slow regression test:** `cd backend && uv run pytest -m slow --override-ini='addopts=' tests/build/test_end_to_end_packaging.py -v`
  Expected: 1 passed (still works after all changes).

- [ ] **Frontend type-check + build:** `cd frontend && npm run type-check && npm run build`
  Expected: clean.

- [ ] **Packaging ladder:** `./test.sh ladder`
  Expected: All layers passed.

- [ ] **Concurrency proof (G1):** automated by `test_concurrent_writes_no_500s_under_busy_timeout` (T3 step 1, slow marker). Re-run as part of the slow-test sweep:
  ```bash
  cd backend && uv run pytest -m slow --override-ini='addopts=' -v
  ```
  Expected: 1 (existing `test_built_sdist_installs_and_runs`) + 1 (new concurrency test) = 2 passed.

- [ ] **Resume proof (G2, G3):** start a summarize on a 5-section book, kill the server with Ctrl-C after 2 sections complete. Restart. Re-run summarize. Expect `completed: 3, skipped: 2`.

- [ ] **Clean console (G4):** open the app at `/` with no books in library. Open browser DevTools → Console. Reload. Expected: zero 4xx/5xx network entries; specifically no `GET /api/v1/reading-presets/active`.

- [ ] **Image 404 (G5):** `curl -sI http://localhost:8000/books/nonexistent.jpg | head -1`
  Expected: `HTTP/1.1 404 Not Found`.

- [ ] **SPA deeplink preserved:** `curl -sI http://localhost:8000/library/fake-id | head -1`
  Expected: `HTTP/1.1 200 OK` (returns `index.html`).

- [ ] **Image rendering end-to-end:** import a book with images, open a section, verify images render. View source: `<img src="/api/v1/images/N">`. Network panel: 200 with correct mime.

**Cleanup:**
- [ ] Remove temporary test files and any `/tmp/bc-*` venvs created during smoke.
- [ ] `cd backend && rm -rf dist/` (if any).
- [ ] Update `docs/changelog.md` with a user-facing entry.
- [ ] `git add docs/changelog.md && git commit -m "docs: changelog for runtime quality fixes"`.

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | (A) T3 test referenced callback `on_section_done` that may not exist on `summarize_book()`. (B) T2 handler used `raise exc` for non-busy errors but FastAPI exception handlers are terminal — wouldn't cascade to 500. (C) Spec §10.2 promised a concurrency test; plan demoted it to a manual T7 step. (D) T6c had N+1 query (one image fetch per section). (E) T6b said "locate where to_markdown is called" — too vague for an engineer with no codebase context. | (A) Replaced callback test with second-session polling; added Step 0 to verify summarizer signature + fixture name first; added a third behavioral test for partial-failure preservation. (B) T2 handler now returns explicit JSONResponse(500) for non-busy errors, with structlog logging. (C) Added `test_concurrent_writes_no_500s_under_busy_timeout` to T3 with `@pytest.mark.slow`; T7 references it instead of curl. (D) T6c now uses `selectinload(BookSection.images)` — single query. (E) T6b now starts with an explicit `grep` to find emission points + offers a single-pass alternative. |
