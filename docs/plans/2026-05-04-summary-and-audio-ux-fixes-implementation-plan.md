---
date: 2026-05-04
spec: docs/specs/2026-05-03-summary-and-audio-ux-fixes-spec.md
simulation: docs/simulations/2026-05-03-summary-and-audio-ux-fixes-simulation.md
requirements: docs/requirements/2026-05-03-summary-and-audio-ux-fixes.md
tier: 2
---

# Summary & Audio UX Fixes — Implementation Plan

## Overview

Implements four shipping UX gaps from the audiobook-mode bundle:
spinner+elapsed feedback for book-summary generation; canonical button-class
sweep across the app; Listen entry points (book/section summary, section
content, single annotations) routed through a preload cache that preserves
iOS Safari's user-gesture chain; and wire-through of the existing Web Speech
voice/rate settings to actual playback. Three deployable phases gated by
full `/verify` between each.

**Done when:** All 21 tasks pass with their inline verification, the FR-ID
coverage gate (§13.5 grep) returns zero misses, the Playwright e2e suite for
Listen+spinner is green, manual iOS Safari spot-check confirms speech starts
on first tap, and `make verify` is clean.

**Execution order:**
```
Phase 1 (foundations, 6 tasks):  T1 → T2 → T3
                                  T4 → T5 → T6                  [P with T1-3]
                                  └─ /verify ──┐
Phase 2 (cache + shell, 6 tasks): T7 → T8 → T9 → T10
                                  T11 → T12                     [P with T8-10]
                                  └─ /verify ──┐
Phase 3 (UX surfaces, 9 tasks):   T13 → T14 → T15 → T16
                                  T17 [P]
                                  T18 [P]
                                  T19 → T20
                                  └─ TN final verification
```

---

## Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|--------------------|-----------|
| D1 | Cache subscription wires through `audioJob` Pinia store via a new `recordContentCompletion(contentType, contentId)` action that `useBufferedJobStream.applyEvent` calls when it sees `section_audio_completed` / `section_audio_failed` / `section_audio_already_stale` / equivalent book-level events. The preload cache uses `audioJob.$onAction` to react. | (a) cache subscribes to `audioJob.$onAction` via new action (chosen); (b) cache subscribes directly to `useBufferedJobStream` (per-job, not singleton); (c) global event bus. | Code study (Phase 2) found per-content events live in `useBufferedJobStream.applyEvent`, NOT in the `audioJob` store. Spec FR-25f said "subscribe to audioJob events" but that store doesn't currently emit per-content. Cleanest fix: `audioJob` exposes one action; the SSE consumer calls it; the cache subscribes via Pinia's standard `$onAction`. Single Pinia store, no new global state. |
| D2 | TDD strictly enforced for backend tasks (T1–T3) — write pytest test first, see RED, implement, see GREEN. Frontend cache module (T7) and TtsPlayButton overhaul (T11) follow TDD against Vitest. UI integration tasks (T13–T17) follow test-after for visible-DOM assertions because component-mount setup is heavy; manual Playwright MCP spot-check is the proof-of-life. | (a) strict TDD everywhere; (b) TDD where high-leverage, manual where setup-heavy (chosen); (c) test-after only. | Pure functions and APIs benefit most from TDD; full Vue component integration tests are setup-heavy and add little protection over Playwright e2e. Apply TDD where regression risk is highest. |
| D3 | The 9-file scoped `.btn-primary`/`.btn-secondary` sweep (T19) lifts ONE canonical version from `BookOverviewView.vue:454-470` per spec D2/FR-08 — no per-component visual deviation. Manual visual spot-check on each surface during TN catches regressions. | (a) one canonical (chosen); (b) preserve per-component padding/hover variations; (c) sweep gradually over multiple PRs. | Chosen at /spec time (loop 2 question). Padding/hover deltas across the 9 are subtle (5–10% size differences); a single canonical look is the strategic win. |
| D4 | `ContentType.ANNOTATION` is added to the Python enum but the SQLite CHECK constraints on `audio_files` / `audio_positions` are NOT extended — annotation lookups never persist. T1 ships a schema-empty Alembic migration that exists for version anchoring; if `--autogenerate` emits ALTER TABLE, T1 discards those statements. | (a) schema-empty migration (chosen); (b) extend CHECK to include 'annotation' for "consistency"; (c) skip migration entirely. | Spec D3/FR-21. Extending CHECK would imply the value can be persisted, which is a design lie. Skipping the migration leaves no version anchor for the enum extension. |
| D5 | Preload cache lives at `frontend/src/composables/audio/preloadCache.ts` (alongside `useTtsEngine.ts`, `mp3Engine.ts`, `webSpeechEngine.ts`). Module-level singleton (Map + functions), NOT a Pinia store — its state has no UI bindings and is consumed only by other audio composables. | (a) composable singleton (chosen); (b) Pinia store; (c) Vue `provide`/`inject`. | (b) overhead unjustified — cache has no reactive UI surface. (c) breaks single-source-of-truth across nested mounts. (a) matches existing audio-composable pattern. |
| D6 | `useWebSpeechSupported()` is a tiny module-level singleton-cached composable, NOT a Pinia store. The probe `'speechSynthesis' in window` runs once on first call and is cached for the session. | (a) module singleton (chosen); (b) Pinia store; (c) inline check at every TtsPlayButton mount. | Browser support doesn't change in-session. (a) is the lightest correct shape. |
| D7 | The `terminate()` method added to `useTtsEngine` (T4) returns the prior `lastEngine` for diagnostic test assertions, but production callers ignore the return value. | (a) returns engine (chosen); (b) returns void. | Lets unit tests assert which engine was terminated without exporting `lastEngine` directly (preserves D17 encapsulation from spec). Production cost: zero. |
| D8 | `audioApi.lookupAnnotation(annotationId)` (T12) does NOT take an explicit `voice` argument — the new annotation route ignores voice (always Web Speech, no MP3 path). The wrapper signature stays minimal. | (a) no voice arg (chosen); (b) optional voice for symmetry. | Annotation lookups never select among voices server-side because there's no Kokoro pre-gen path. Symmetry would be misleading. |

---

## Code Study Notes

**Spec assumptions confirmed (Q-resolutions to spec Open Questions):**
- **Q2 (Mp3Engine mediaSession):** `frontend/src/composables/audio/mp3Engine.ts:105-122` already wires `navigator.mediaSession`. T18 audits and EXTENDS — title currently appears static; needs to vary by contentType.
- **Q4 (dark-mode convention):** `frontend/src/assets/theme.css` uses `[data-theme='dark']` attribute selectors over CSS custom properties (`--color-bg-primary`, `--color-accent`, etc.). The canonical `.btn-primary`/`.btn-secondary` global classes (T19) only need `var(--color-*)` tokens — no separate dark-mode rules. **Spec §11.1 dark-variant FR is unnecessary; T19 omits.**
- **Q5 (SectionSummary/SectionContent paths):** No standalone files exist. Section summary + content render in `BookDetailView.vue:251-296` via `<ReadingArea>`. Header is `ReaderHeader.vue` which already exposes `<slot name="actions">` (line 62). T14 mounts `<TtsPlayButton>` into that slot from `BookDetailView`.

**New-file existence checks (per /plan learning #grep-for-spec-build-files):**
- `composables/audio/preloadCache.ts` — DOES NOT EXIST. T7 creates.
- `composables/useWebSpeechSupported.ts` — DOES NOT EXIST. T6 creates.
- All other spec-named "new" surfaces (helper, FR additions) are inline edits to existing files.

**Per-content audio events live in `useBufferedJobStream.applyEvent` (case `section_audio_completed`, `section_audio_failed`, `section_audio_already_stale` per `useBufferedJobStream.ts:34-36, 105-111`), not in `audioJob` Pinia store.** The `audioJob` store currently tracks only the active-job lifecycle (`apply()` at `audioJob.ts:36-66`), not per-content completions. **Drove D1 + T8.**

**409 sites:** `backend/app/api/routes/book_summary.py:94-101` (pre-INSERT check) and `113-131` (IntegrityError fallback). Both need `active_job_started_at` extension (T3). `ProcessingJob.started_at` column exists per spec gotcha #5; verify by inspection in T3 step 1.

**Existing 9-file scoped `.btn-primary`/`.btn-secondary` redefinitions (verified via `grep -n '\\.btn-\(primary\|secondary\)\\s*{' frontend/src --include="*.vue"`):**
1. `components/book/BookSummaryTab.vue:233,241`
2. `views/BookOverviewView.vue:454` (canonical source for global)
3. `views/JobProgressView.vue:218,222`
4. `components/settings/ReadingSettings.vue:166`
5. `components/settings/DatabaseSettings.vue:226`
6. `components/settings/PresetSettings.vue:358`
7. `components/settings/PresetCreateEditForm.vue:190`
8. `components/settings/CustomEditor.vue:208,214,219`
9. `components/settings/BackupSettings.vue:156`

**iOS gesture chain critical path:** `composables/audio/useTtsEngine.ts:64-90` already does `await audioApi.lookup()` then constructs engine then calls `engine.play()`. Without preload (T7+T11), the await between click and `speak()` breaks iOS Safari. T11's preload-on-mount + cache-read-at-click is the gesture-preserving fix.

---

## Prerequisites

- Working tree clean on `main` (or a feature branch from `main`).
- `cd backend && uv sync --dev` — Python deps installed.
- `cd frontend && npm install` — Node deps installed.
- At least one book seeded in the local DB with a populated `default_summary` AND at least one section with both `default_summary_id` and `content_md`. (Use `tests/fixtures/download_fixtures.py` + `bookcompanion add` if empty.)
- Optional: `bookcompanion serve --port 8765` running for Playwright MCP spot-checks (per CLAUDE.md interactive verification protocol).

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/db/models.py:82-87` | Add `ANNOTATION = "annotation"` to `ContentType` enum (T1). |
| Create | `backend/app/migrations/versions/v1_7_a_*.py` | Schema-empty Alembic revision anchoring the enum extension (T1). |
| Modify | `backend/app/api/routes/audio.py:227-344` | New route handler `audio_lookup_annotation` mounted at `GET /api/v1/audio/annotations/{annotation_id}/lookup`; reject `content_type=annotation` on existing `/audio/lookup` with the redirecting-hint 400 (T2). |
| Modify | `backend/app/api/routes/book_summary.py:94-131` | Extend both 409 response bodies to include `active_job_started_at` (T3). |
| Test   | `backend/tests/unit/db/test_content_type_enum.py` | Assert `ContentType("annotation")` resolves; assert NOT in CHECK constraints (T1). |
| Test   | `backend/tests/integration/api/test_audio_lookup_annotation.py` | Behavioral tests for the new annotation route (T2). |
| Test   | `backend/tests/integration/api/test_book_summary_409.py` | Assert 409 body includes `active_job_started_at` ISO8601 (T3). |
| Modify | `frontend/src/composables/audio/useTtsEngine.ts` | Add `terminate()` to returned API; read `settingsStore.tts.voice` + `default_speed` when web-speech engine resolves (T4, T5). |
| Create | `frontend/src/composables/useWebSpeechSupported.ts` | Module-level singleton probe; returns reactive `{ supported }` (T6). |
| Create | `frontend/src/composables/audio/preloadCache.ts` | Cache module: `getCached(key)`, `preload(args)`, `invalidate(key)`, `initCacheSubscription()`; coalescing + invalidation timestamp guard + error sentinel (T7). |
| Modify | `frontend/src/stores/audioJob.ts` | Add `recordContentCompletion(contentType, contentId)` action; no state mutation, just emits via `$onAction` (T8). |
| Modify | `frontend/src/composables/useBufferedJobStream.ts:90-220` | In `applyEvent`, on per-content audio events, call `useAudioJobStore().recordContentCompletion(...)` (T8). |
| Modify | `frontend/src/components/app/AppShell.vue` | Mount `<Playbar />`; install global Space handler with target exclusions; call `initCacheSubscription()` in `onMounted` (T9). |
| Modify | `frontend/src/components/reader/ReadingArea.vue:31-54` | Delete the Space branch (lines 45-50); keep ArrowLeft/ArrowRight (T10). |
| Modify | `frontend/src/components/audio/TtsPlayButton.vue` | Full overhaul: IntersectionObserver / hover-focus-touchstart preload; visibility predicate (FR-17); click-time loading; onUnmounted teardown (T11). |
| Modify | `frontend/src/api/audio.ts` | Add `lookupAnnotation(annotationId)` helper (T12). |
| Modify | `frontend/src/components/book/BookSummaryTab.vue` | Spinner + `M:SS elapsed` timer + ARIA live; `Cancel` button removed; 409 reattach uses `active_job_started_at`; remove scoped `.btn-primary`/`.btn-secondary`; add `<TtsPlayButton>` to populated header (T13, T15, T19). |
| Modify | `frontend/src/views/BookDetailView.vue:240-296` | Pass `<TtsPlayButton>` into `<ReaderHeader>` `actions` slot for both `contentMode` paths, bound to (section_summary or section_content, section.id) (T14). |
| Modify | `frontend/src/views/AnnotationsView.vue:40-50` | Per-row `<TtsPlayButton contentType="annotation" :contentId="annotation.id">` (T16). |
| Modify | `frontend/src/components/settings/SettingsTtsPanel.vue` | **Reset to defaults** button (FR-26); Loading-voices placeholder (FR-27); persisted-voice-missing hint (FR-28); replace raw Tailwind on Save with `.btn-primary` (T17, T20). |
| Modify | `frontend/src/composables/audio/webSpeechEngine.ts` | `play()` first-call: set `navigator.mediaSession.metadata` per FR-19 (T18). |
| Modify | `frontend/src/composables/audio/mp3Engine.ts:105-122` | Extend existing mediaSession to vary `title` by contentType per FR-19b (T18). |
| Modify | `frontend/src/assets/main.css` | Add canonical `.btn-primary` / `.btn-secondary` global classes using `var(--color-*)` tokens (T19). |
| Modify | (9 files per Code Study Notes) | Remove scoped `.btn-primary`/`.btn-secondary` redefinitions (T19). |
| Modify | (10 files in `frontend/src/components/audio/` + `TtsPlayButton.vue`) | Replace raw Tailwind button utilities per spec §11.2 mapping (T20). |
| Test   | `frontend/src/composables/audio/__tests__/preloadCache.spec.ts` | Coalescing race, error sentinel, invalidation timestamp guard, AppShell-init subscription (T7). |
| Test   | `frontend/src/components/audio/__tests__/TtsPlayButton.spec.ts` (extend) | Visibility predicate including `sanitized_text!==""`; preload IO trigger; section_content uses hover/focus; click-time loading; unmount teardown (T11). |
| Test   | `frontend/src/components/book/__tests__/BookSummaryTab.spec.ts` (extend) | Spinner + elapsed timer; ARIA live region; 409 reattach uses returned started_at (T13). |
| Test   | `frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts` (new) | settings read; terminate() public API; annotation routes through `lookupAnnotation` (T4, T5, T12). |
| Test   | `frontend/src/components/settings/__tests__/SettingsTtsPanel.spec.ts` (new) | Reset PUT body; Loading-voices placeholder; persisted-voice-missing hint (T17). |
| Test   | `frontend/e2e/listen-section-summary.spec.ts` (new) | Click Listen → `ttsPlayer.isActive===true` → Playbar visible → cross-route persistence → close stops (TN). |
| Test   | `frontend/e2e/book-summary-progress.spec.ts` (new) | Click Generate → spinner+ARIA within 1s → no Cancel → SSE completion swaps to populated (TN). |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| iOS Safari gesture chain still breaks on cold-cache slow-network click despite preload-on-mount | Medium | NFR-02 acknowledged residual risk. TN includes manual iOS Safari test on a slow-network simulation. If broken, follow-up patch ships a 2-step Prepare→Play affordance for iOS only. |
| Visual regression on one of 9 surfaces sweeping `.btn-primary`/`.btn-secondary` | Medium | TN's manual visual spot-check covers all 9; user sees screenshots and can request per-surface modifier classes if any look materially worse. |
| `useBufferedJobStream` event names drift between this spec and current code (per CLAUDE.md gotcha #23) | Low | T8 explicitly greps the file for the event-string union and asserts the cache covers all 4 documented variants (`_completed`, `_failed`, `_already_stale`, plus book-level equivalent). |
| `audioJob.$onAction` doesn't fire for the new `recordContentCompletion` action because Pinia setup-stores need explicit action declaration | Low | T8 step 1 writes the test asserting `$onAction` fires; if it doesn't, the action is wrapped in `defineStore`'s returned object — implementer adjusts the export shape. |
| `ProcessingJob.started_at` is null for jobs that never ran (PENDING-only) → 409 returns null timestamp → frontend timer crashes | Low | T3 step 1 verifies the column nullability; backend falls back to `created_at` if `started_at IS NULL`. T13 frontend handles null gracefully (omits elapsed timer instead of NaN). |

---

## Rollback

- If T1 migration fails on existing DBs: `cd backend && uv run alembic -c app/migrations/alembic.ini downgrade -1`. (Schema-empty migration; downgrade is a no-op but the version anchor reverses.)
- If T19 button sweep introduces visual regressions: `git revert <T19-commit>` reverts ONLY that commit; the global classes can stay if the per-file `<style scoped>` removals are the problem.
- All other tasks are pure additive frontend changes; rollback = `git revert <task-commit>`.
- No data mutations; no seed-data resets needed.

---

## Tasks

## Phase 1: Backend foundations + shared utilities

Phase produces a deployable slice: backend supports the new annotation lookup
route, the existing 409 carries the started timestamp, the frontend has the
shared composables (terminate, settings-read, web-speech-supported probe) but
no UI consumer wires them yet — the existing audio paths continue to work
unchanged.

### T1: Backend — extend `ContentType` enum + schema-empty migration

**Goal:** Add `ContentType.ANNOTATION` to the Python enum without changing the SQLite CHECK constraints.
**Spec refs:** FR-21, D3, D4 (this plan).

**Files:**
- Modify: `backend/app/db/models.py:82-87`
- Create: `backend/app/migrations/versions/v1_7_a_content_type_annotation.py`
- Test: `backend/tests/unit/db/test_content_type_enum.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  # backend/tests/unit/db/test_content_type_enum.py
  import pytest
  from sqlalchemy import inspect, create_engine, text
  from app.db.models import ContentType, AudioFile

  def test_annotation_enum_value_exists():
      assert ContentType("annotation") == ContentType.ANNOTATION
      assert ContentType.ANNOTATION.value == "annotation"

  def test_annotation_not_in_audio_files_check_constraint():
      # AudioFile.content_type SQLite CHECK must NOT permit 'annotation'
      engine = create_engine("sqlite://")
      from app.db.models import Base
      Base.metadata.create_all(engine)
      with engine.connect() as conn:
          row = conn.execute(text(
              "SELECT sql FROM sqlite_master WHERE type='table' AND name='audio_files'"
          )).fetchone()
          assert row is not None
          # Either the schema has no CHECK at all (column-typed string) OR the CHECK
          # explicitly omits 'annotation'. Fail if 'annotation' appears in any CHECK clause.
          assert "annotation" not in row[0].lower(), (
              f"audio_files schema must NOT include 'annotation' in CHECK: {row[0]}"
          )
  ```

- [ ] Step 2: Run test, confirm RED
  Run: `cd backend && uv run python -m pytest tests/unit/db/test_content_type_enum.py -v`
  Expected: FAIL on `ContentType("annotation")` (`ValueError: 'annotation' is not a valid ContentType`).

- [ ] Step 3: Add enum value
  In `backend/app/db/models.py`, change:
  ```python
  class ContentType(str, enum.Enum):
      SECTION_CONTENT = "section_content"
      SECTION_SUMMARY = "section_summary"
      BOOK_SUMMARY = "book_summary"
      ANNOTATIONS_PLAYLIST = "annotations_playlist"
      ANNOTATION = "annotation"  # FR-21: runtime-only; never persisted
  ```

- [ ] Step 4: Generate migration; inspect autogenerate output
  Run: `cd backend && uv run alembic -c app/migrations/alembic.ini revision --autogenerate -m "v1_7_a content_type_annotation"`
  Expected: a new file under `backend/app/migrations/versions/`. Open it and verify `upgrade()`/`downgrade()` are empty (no ALTER TABLE for `audio_files` / `audio_positions`). If autogenerate emitted any ALTER for those CHECK constraints, **delete those statements** so the migration body is `pass`.

- [ ] Step 5: Run tests
  Run: `cd backend && uv run python -m pytest tests/unit/db/test_content_type_enum.py -v && uv run alembic -c app/migrations/alembic.ini upgrade head`
  Expected: 2 passed, migration applies cleanly.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/db/models.py backend/app/migrations/versions/v1_7_a_*.py backend/tests/unit/db/test_content_type_enum.py
  git commit -m "feat(backend): add ContentType.ANNOTATION runtime-only enum value"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/unit/db/test_content_type_enum.py -v` — 2 passed
- `cd backend && uv run alembic -c app/migrations/alembic.ini upgrade head` — exits 0
- `cd backend && uv run ruff check app/db/models.py` — no errors

---

### T2: Backend — `GET /api/v1/audio/annotations/{annotation_id}/lookup`

**Goal:** Ship the dedicated annotation-lookup route. Reject `content_type=annotation` on the existing `/audio/lookup` with a redirecting-hint 400.
**Spec refs:** FR-22, FR-22b, §7.1, §7.2.

**Files:**
- Modify: `backend/app/api/routes/audio.py:227-344`
- Test: `backend/tests/integration/api/test_audio_lookup_annotation.py`

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend/tests/integration/api/test_audio_lookup_annotation.py
  import pytest
  from httpx import AsyncClient

  pytestmark = pytest.mark.asyncio

  async def test_annotation_lookup_returns_sanitized(client, seeded_annotation):
      # seeded_annotation has selected_text="Hello world."
      r = await client.get(f"/api/v1/audio/annotations/{seeded_annotation.id}/lookup")
      assert r.status_code == 200
      body = r.json()
      assert body["pregenerated"] is False
      assert body["sanitized_text"]  # non-empty
      assert isinstance(body["sentence_offsets_chars"], list)
      assert body["sanitizer_version_current"]
      assert body["stale"] is None

  async def test_annotation_lookup_404_when_missing(client):
      r = await client.get("/api/v1/audio/annotations/999999/lookup")
      assert r.status_code == 404
      assert "annotation not found" in r.json()["detail"]

  async def test_annotation_lookup_empty_returns_empty_shape(client, seeded_empty_annotation):
      # seeded_empty_annotation: selected_text=None, note=None
      r = await client.get(f"/api/v1/audio/annotations/{seeded_empty_annotation.id}/lookup")
      assert r.status_code == 200
      body = r.json()
      assert body["sanitized_text"] == ""
      assert body["sentence_offsets_chars"] == []

  async def test_old_route_rejects_annotation_with_hint(client):
      r = await client.get("/api/v1/audio/lookup", params={
          "book_id": 1, "content_type": "annotation", "content_id": 1,
      })
      assert r.status_code == 400
      assert "/audio/annotations/" in r.json()["detail"]
  ```

  Add fixtures to `backend/tests/integration/conftest.py` (extend, don't replace):
  ```python
  @pytest_asyncio.fixture
  async def seeded_annotation(db_session, seeded_book):
      from app.db.models import Annotation, ContentType, AnnotationType
      ann = Annotation(
          content_type=ContentType.SECTION_SUMMARY,
          content_id=seeded_book.sections[0].id,
          selected_text="Hello world.",
          note=None,
          annotation_type=AnnotationType.HIGHLIGHT,
      )
      db_session.add(ann)
      await db_session.commit()
      await db_session.refresh(ann)
      return ann

  @pytest_asyncio.fixture
  async def seeded_empty_annotation(db_session, seeded_book):
      from app.db.models import Annotation, ContentType, AnnotationType
      ann = Annotation(
          content_type=ContentType.SECTION_SUMMARY,
          content_id=seeded_book.sections[0].id,
          selected_text=None,
          note=None,
          annotation_type=AnnotationType.FREEFORM,
      )
      db_session.add(ann)
      await db_session.commit()
      await db_session.refresh(ann)
      return ann
  ```

- [ ] Step 2: Run tests, confirm RED
  Run: `cd backend && uv run python -m pytest tests/integration/api/test_audio_lookup_annotation.py -v`
  Expected: 4 FAIL on 404 (route doesn't exist) or 422 (no validation match).

- [ ] Step 3: Implement the new route + the hint-rejecting branch
  In `backend/app/api/routes/audio.py`:
  - Add at the top of the existing `audio_lookup` handler, BEFORE the existing `try: ct = ContentType(content_type)`: `if content_type == "annotation": raise HTTPException(400, detail="use /audio/annotations/{id}/lookup for annotations")`.
  - Add a new handler:
    ```python
    @router.get("/api/v1/audio/annotations/{annotation_id}/lookup")
    async def audio_lookup_annotation(
        annotation_id: int,
        db: AsyncSession = Depends(get_db),
        settings: Settings = Depends(get_settings),
    ):
        from app.db.repositories.annotation_repo import AnnotationRepository
        from app.services.tts.markdown_to_speech import (
            EmptySanitizedTextError, sanitize, SANITIZER_VERSION,
        )
        repo = AnnotationRepository(db)
        ann = await repo.get_by_id(annotation_id)
        if ann is None:
            raise HTTPException(status_code=404, detail="annotation not found")
        parts: list[str] = []
        if ann.selected_text:
            parts.append(ann.selected_text)
        if ann.note:
            parts.append(ann.note)
        source_md = "\n\n".join(parts)
        if not source_md.strip():
            return {
                "pregenerated": False,
                "sanitized_text": "",
                "sentence_offsets_chars": [],
                "url": None, "duration_seconds": None, "voice": None,
                "sentence_offsets_seconds": None, "source_hash": None,
                "source_hash_stored": None, "source_hash_current": None,
                "sanitizer_version_stored": None,
                "sanitizer_version_current": SANITIZER_VERSION,
                "stale": None,
            }
        try:
            sanitized = sanitize(source_md)
        except EmptySanitizedTextError:
            return {
                "pregenerated": False,
                "sanitized_text": "",
                "sentence_offsets_chars": [],
                "url": None, "duration_seconds": None, "voice": None,
                "sentence_offsets_seconds": None, "source_hash": None,
                "source_hash_stored": None, "source_hash_current": None,
                "sanitizer_version_stored": None,
                "sanitizer_version_current": SANITIZER_VERSION,
                "stale": None,
            }
        import hashlib
        source_hash = hashlib.sha256(sanitized.text.encode("utf-8")).hexdigest()
        return {
            "pregenerated": False,
            "sanitized_text": sanitized.text,
            "sentence_offsets_chars": sanitized.sentence_offsets,
            "url": None, "duration_seconds": None, "voice": None,
            "sentence_offsets_seconds": None,
            "source_hash": source_hash,
            "source_hash_stored": None, "source_hash_current": source_hash,
            "sanitizer_version_stored": None,
            "sanitizer_version_current": SANITIZER_VERSION,
            "stale": None,
        }
    ```
  - Verify `SANITIZER_VERSION` export exists in `markdown_to_speech.py` (per audiobook spec D24); if not, the implementer reads its current name and substitutes accordingly.

- [ ] Step 4: Run tests, confirm GREEN
  Run: `cd backend && uv run python -m pytest tests/integration/api/test_audio_lookup_annotation.py -v`
  Expected: 4 passed.

- [ ] Step 5: Smoke-test via curl
  Start `bookcompanion serve --port 8765` in background (per CLAUDE.md interactive verification protocol). Seed an annotation via the API:
  ```bash
  curl -sf http://localhost:8765/api/v1/audio/annotations/1/lookup | python3 -m json.tool
  ```
  Expected: response with `"pregenerated": false`, `"sanitized_text"` populated, `"sentence_offsets_chars"` array, `"sanitizer_version_current"` non-null. (404 if no annotation id 1 exists — seed one first.)

- [ ] Step 6: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/api/test_audio_lookup_annotation.py backend/tests/integration/conftest.py
  git commit -m "feat(backend): add /audio/annotations/{id}/lookup; reject annotation on /audio/lookup"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/integration/api/test_audio_lookup_annotation.py -v` — 4 passed
- `cd backend && uv run ruff check app/api/routes/audio.py` — no errors

---

### T3: Backend — extend POST `/book-summary` 409 with `active_job_started_at`

**Goal:** UI's elapsed timer can show real job age on reattach (G14).
**Spec refs:** FR-07b.

**Files:**
- Modify: `backend/app/api/routes/book_summary.py:94-131`
- Test: `backend/tests/integration/api/test_book_summary_409.py`

**Steps:**

- [ ] Step 1: Verify `ProcessingJob.started_at` column exists and is nullable
  Run: `cd backend && uv run python -c "from app.db.models import ProcessingJob; col = ProcessingJob.__table__.c.started_at; print(col.type, col.nullable)"`
  Expected: prints `DateTime True` (or similar). If nullable, T3 must fall back to `created_at` for PENDING-state jobs.

- [ ] Step 2: Write failing test
  ```python
  # backend/tests/integration/api/test_book_summary_409.py
  import pytest
  from datetime import datetime
  pytestmark = pytest.mark.asyncio

  async def test_409_includes_active_job_started_at(client, seeded_book_with_in_flight_job):
      book_id, in_flight_job_id = seeded_book_with_in_flight_job
      r = await client.post(
          f"/api/v1/books/{book_id}/book-summary",
          json={"preset_name": "practitioner_bullets"},
      )
      assert r.status_code == 409
      body = r.json()
      assert body["active_job_id"] == in_flight_job_id
      assert "active_job_started_at" in body
      # Must be ISO8601-parseable
      datetime.fromisoformat(body["active_job_started_at"].replace("Z", "+00:00"))
  ```

  Add fixture to `conftest.py`:
  ```python
  @pytest_asyncio.fixture
  async def seeded_book_with_in_flight_job(db_session, seeded_book):
      from app.db.models import ProcessingJob, ProcessingJobStatus, ProcessingStep
      from datetime import datetime, timezone
      job = ProcessingJob(
          book_id=seeded_book.id, step=ProcessingStep.SUMMARIZE,
          status=ProcessingJobStatus.RUNNING, pid=99999,
          started_at=datetime.now(timezone.utc),
      )
      db_session.add(job)
      await db_session.commit()
      await db_session.refresh(job)
      return seeded_book.id, job.id
  ```

- [ ] Step 3: Run, confirm RED
  Run: `cd backend && uv run python -m pytest tests/integration/api/test_book_summary_409.py -v`
  Expected: KeyError on `active_job_started_at`.

- [ ] Step 4: Implement the extension
  In `book_summary.py:94-101` (pre-INSERT 409) and `113-131` (IntegrityError fallback), extend the JSONResponse `content` dict to include:
  ```python
  "active_job_started_at": (in_flight.started_at or in_flight.created_at).isoformat()
  ```
  (and same for `active` in the IntegrityError branch). Use `(active.started_at or active.created_at)` to handle PENDING-state nulls.

- [ ] Step 5: Run, confirm GREEN
  Run: `cd backend && uv run python -m pytest tests/integration/api/test_book_summary_409.py -v`
  Expected: 1 passed.

- [ ] Step 6: Commit
  ```bash
  git add backend/app/api/routes/book_summary.py backend/tests/integration/api/test_book_summary_409.py backend/tests/integration/conftest.py
  git commit -m "feat(backend): include active_job_started_at in book-summary 409 response"
  ```

**Inline verification:**
- `cd backend && uv run python -m pytest tests/integration/api/test_book_summary_409.py -v` — 1 passed
- Existing book-summary tests unaffected: `uv run python -m pytest tests/integration/api/ -k book_summary -v` — all pass

---

### T4: Frontend — add `terminate()` to `useTtsEngine` API

**Goal:** Public termination point for Playbar.onClose; encapsulates module-level `lastEngine`.
**Spec refs:** FR-31, D17 (spec), D7 (this plan).

**Files:**
- Modify: `frontend/src/composables/audio/useTtsEngine.ts`
- Test: `frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Write failing test
  ```ts
  // frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { setActivePinia, createPinia } from 'pinia'
  import { useTtsEngine } from '../useTtsEngine'
  import { audioApi } from '@/api/audio'

  beforeEach(() => { setActivePinia(createPinia()) })

  describe('useTtsEngine.terminate()', () => {
    it('exposes terminate() that clears lastEngine', async () => {
      vi.spyOn(audioApi, 'lookup').mockResolvedValue({
        pregenerated: false, sanitized_text: 'Hi.',
        sentence_offsets_chars: [0],
      } as any)
      // Stub speechSynthesis to avoid jsdom 'engine_unavailable'
      ;(globalThis as any).window = { ...(globalThis as any).window, speechSynthesis: { getVoices: () => [{ name: 'X' }], paused: false } }
      const api = useTtsEngine()
      await api.load({ bookId: 1, contentType: 'section_summary', contentId: 1 })
      const terminated = api.terminate()
      expect(terminated).not.toBeNull()
      // Calling again returns null (no live engine)
      expect(api.terminate()).toBeNull()
    })
  })
  ```

- [ ] Step 2: Confirm RED
  Run: `cd frontend && npm run test:unit -- useTtsEngine.spec`
  Expected: TypeError — `api.terminate is not a function`.

- [ ] Step 3: Implement
  In `useTtsEngine.ts`, change the returned object from `{ load: ... }` to `{ load, terminate }`. Add at module scope:
  ```ts
  function terminate(): TtsEngine | null {
    if (!lastEngine) return null
    const eng = lastEngine
    try { eng.terminate() } catch { /* ignore */ }
    lastEngine = null
    return eng
  }
  ```
  Update the return inside `useTtsEngine()` to include `terminate`. Update the `UseTtsEngineApi` interface to include `terminate(): TtsEngine | null`.

- [ ] Step 4: Confirm GREEN
  Run: `cd frontend && npm run test:unit -- useTtsEngine.spec`
  Expected: 1 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/useTtsEngine.ts frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts
  git commit -m "feat(frontend): expose useTtsEngine.terminate() public API"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useTtsEngine.spec` — passes
- `cd frontend && npm run type-check` — no new errors

---

### T5: Frontend — `useTtsEngine.load()` reads `settingsStore.tts`; engine constructors get final consolidated signatures

**Goal:** Saved Web Speech voice + rate are actually applied (FR-18); both engine constructors get the FULL signature future consumers will need (avoids /execute-time TypeError per L1-F2). **Cache routing is added in T7** (preloadCache must exist first).
**Spec refs:** FR-18, D4 (spec).

**Phase ordering note (L1-F1 fix):** T5 keeps `useTtsEngine.load()` calling `audioApi.lookup()` directly. T7's final step swaps that single call to `preloadCache.preload()`. Splitting this way preserves Phase 1 / Phase 2 boundaries — T5 ships in Phase 1 with the existing audio paths still working.

**Files:**
- Modify: `frontend/src/composables/audio/useTtsEngine.ts`
- Test: extend `frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```ts
  it('passes settingsStore.tts.voice + default_speed to WebSpeechEngine when no explicit voice', async () => {
    const settings = useSettingsStore()
    settings.tts = { engine: 'web-speech', voice: 'Daniel', default_speed: 1.5, auto_advance: true } as any
    vi.spyOn(audioApi, 'lookup').mockResolvedValue({
      pregenerated: false, sanitized_text: 'Hi there.', sentence_offsets_chars: [0, 3],
    } as any)
    const wsCtorSpy = vi.spyOn(await import('../webSpeechEngine'), 'WebSpeechEngine')
    const api = useTtsEngine()
    await api.load({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    expect(wsCtorSpy).toHaveBeenCalledWith(expect.objectContaining({
      voice: 'Daniel', rate: 1.5,
    }))
  })
  ```
  (Adjust `useSettingsStore` import per current store shape; see code in `frontend/src/stores/settings.ts`.)

- [ ] Step 2: Confirm RED — current load() doesn't read settings.

- [ ] Step 3: Add the FULL consolidated constructor signatures FIRST (before any consumer adds incremental opts)
  In `webSpeechEngine.ts`, expand `WebSpeechEngineOpts`:
  ```ts
  export interface WebSpeechEngineOpts {
    sanitizedText: string
    sentenceOffsetsChars: number[]
    voice?: string
    rate?: number          // already accepted; keep
    contentType?: string   // for mediaSession (T18 consumes)
    bookTitle?: string     // for mediaSession artist (T18 consumes)
  }
  ```
  In `mp3Engine.ts`, expand its opts equivalently. (T18 will fill in the metadata wiring; T5's job is to make the SHAPE final so /execute doesn't hit TypeErrors.)

- [ ] Step 4: Implement settings read in useTtsEngine.load() (cache routing comes in T7)
  In `useTtsEngine.ts` `load()`, after the existing `audioApi.lookup(...)` call but BEFORE constructing the engine:
  ```ts
  import { useSettingsStore } from '@/stores/settings'
  import { useBooksStore } from '@/stores/books'
  // ...
  const settings = useSettingsStore()
  const tts = (settings as any).tts ?? {}
  const wsVoice = args.voice ?? tts.voice ?? undefined
  const wsRate = tts.default_speed ?? 1.0
  const bookTitle = useBooksStore().getById?.(args.bookId)?.title ?? ''
  ```
  Pass to constructor: `new WebSpeechEngine({ sanitizedText, sentenceOffsetsChars, voice: wsVoice, rate: wsRate, contentType: args.contentType, bookTitle })`.
  Symmetric for `Mp3Engine`: pass `contentType` + `bookTitle` opts (T18 implements the metadata setter; T5 just ensures the constructor accepts them so the call site compiles today).

- [ ] Step 5: Confirm GREEN
  Run: `cd frontend && npm run test:unit -- useTtsEngine.spec`
  Expected: 2 passed (settings read + terminate from T4).

- [ ] Step 6: Commit
  ```bash
  git add frontend/src/composables/audio/useTtsEngine.ts frontend/src/composables/audio/webSpeechEngine.ts frontend/src/composables/audio/mp3Engine.ts frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts
  git commit -m "feat(frontend): useTtsEngine.load reads saved Web Speech settings; consolidated ctor sigs"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useTtsEngine.spec` — 2 passed

---

### T6: Frontend — `useWebSpeechSupported()` composable

**Goal:** Cached one-shot probe consumed by TtsPlayButton visibility predicate.
**Spec refs:** spec §8.2, FR-17.

**Files:**
- Create: `frontend/src/composables/useWebSpeechSupported.ts`
- Test: `frontend/src/composables/__tests__/useWebSpeechSupported.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Write failing test
  ```ts
  // frontend/src/composables/__tests__/useWebSpeechSupported.spec.ts
  import { describe, it, expect, beforeEach } from 'vitest'
  import { useWebSpeechSupported, _resetForTests } from '../useWebSpeechSupported'

  beforeEach(() => _resetForTests())

  describe('useWebSpeechSupported', () => {
    it('returns true when speechSynthesis is on window', () => {
      ;(globalThis as any).window = { speechSynthesis: {} }
      expect(useWebSpeechSupported().supported.value).toBe(true)
    })
    it('returns false when speechSynthesis is missing', () => {
      ;(globalThis as any).window = {}
      expect(useWebSpeechSupported().supported.value).toBe(false)
    })
    it('caches the result across calls', () => {
      ;(globalThis as any).window = { speechSynthesis: {} }
      const a = useWebSpeechSupported()
      ;(globalThis as any).window = {}  // change after first call
      const b = useWebSpeechSupported()
      expect(b.supported.value).toBe(true)  // cached from first
    })
  })
  ```

- [ ] Step 2: Confirm RED.

- [ ] Step 3: Implement
  ```ts
  // frontend/src/composables/useWebSpeechSupported.ts
  import { ref, type Ref } from 'vue'
  let supported: Ref<boolean> | null = null
  export function useWebSpeechSupported(): { supported: Readonly<Ref<boolean>> } {
    if (supported === null) {
      supported = ref(typeof window !== 'undefined' && 'speechSynthesis' in window)
    }
    return { supported }
  }
  export function _resetForTests(): void { supported = null }
  ```

- [ ] Step 4: Confirm GREEN
  Run: `cd frontend && npm run test:unit -- useWebSpeechSupported.spec`
  Expected: 3 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/useWebSpeechSupported.ts frontend/src/composables/__tests__/useWebSpeechSupported.spec.ts
  git commit -m "feat(frontend): add useWebSpeechSupported() singleton-cached probe"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useWebSpeechSupported.spec` — 3 passed

---

## Phase 2: Cache + AppShell wiring

Phase produces a deployable slice: the cache module + audioJob integration +
AppShell-mounted Playbar/Space-handler/cache-init are live, and TtsPlayButton
preloads its lookup. No new Listen entry points yet — existing TtsPlayButton
references (test-only today) demonstrate the path. The annotation lookup
helper exists.

### T7: Frontend — `preloadCache.ts` module

**Goal:** Singleton cache with coalescing, error sentinel, invalidation timestamp guard, and AppShell-init subscription.
**Spec refs:** FR-25b, FR-25c, FR-25d, FR-25e, FR-25f.

**Files:**
- Create: `frontend/src/composables/audio/preloadCache.ts`
- Test: `frontend/src/composables/audio/__tests__/preloadCache.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Write failing tests covering the four invariants
  ```ts
  // frontend/src/composables/audio/__tests__/preloadCache.spec.ts
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import { setActivePinia, createPinia } from 'pinia'
  import * as cache from '../preloadCache'
  import { audioApi } from '@/api/audio'

  beforeEach(() => {
    setActivePinia(createPinia())
    cache._resetForTests()
  })

  describe('preloadCache', () => {
    it('coalesces N parallel preloads for the same content (FR-25c)', async () => {
      const lookupSpy = vi.spyOn(audioApi, 'lookup').mockResolvedValue({
        pregenerated: false, sanitized_text: 'A.', sentence_offsets_chars: [0],
      } as any)
      const args = { bookId: 1, contentType: 'section_summary' as const, contentId: 5 }
      const [a, b, c] = await Promise.all([cache.preload(args), cache.preload(args), cache.preload(args)])
      expect(lookupSpy).toHaveBeenCalledTimes(1)
      expect(a).toBe(b)
      expect(b).toBe(c)
    })

    it('stores error sentinel with 30s TTL on lookup failure (FR-25d)', async () => {
      vi.spyOn(audioApi, 'lookup').mockRejectedValueOnce(new Error('boom'))
      const args = { bookId: 1, contentType: 'section_summary' as const, contentId: 6 }
      await expect(cache.preload(args)).rejects.toThrow('boom')
      const entry = cache._inspect(`section_summary:6`)
      expect(entry?.error).toBeInstanceOf(Error)
      expect(entry?.expiresAt - Date.now()).toBeLessThan(30_000 + 100)
    })

    it('discards preload result when invalidation timestamp is newer (FR-25e)', async () => {
      let resolveFn: (v: any) => void = () => {}
      vi.spyOn(audioApi, 'lookup').mockReturnValueOnce(new Promise((r) => { resolveFn = r }))
      const args = { bookId: 1, contentType: 'section_summary' as const, contentId: 7 }
      const promise = cache.preload(args)
      // Invalidate while preload is in-flight
      cache.invalidate('section_summary:7')
      // Now resolve with stale result
      resolveFn({ pregenerated: false, sanitized_text: 'Stale.', sentence_offsets_chars: [0] })
      // Mock the second (retry) lookup with fresh result
      vi.spyOn(audioApi, 'lookup').mockResolvedValueOnce({
        pregenerated: true, url: '/audio/x.mp3', sanitized_text: 'Fresh.', sentence_offsets_chars: [0],
      } as any)
      const result = await promise
      expect(result.sanitized_text).toBe('Fresh.')
    })

    it('coalesces annotation preloads via lookupAnnotation (FR-25b key format)', async () => {
      const spy = vi.spyOn(audioApi, 'lookupAnnotation').mockResolvedValue({
        pregenerated: false, sanitized_text: 'Note.', sentence_offsets_chars: [0],
      } as any)
      const args = { bookId: 0, contentType: 'annotation' as const, contentId: 9 }
      await Promise.all([cache.preload(args), cache.preload(args)])
      expect(spy).toHaveBeenCalledTimes(1)
    })
  })
  ```

- [ ] Step 2: Confirm RED — module doesn't exist.

- [ ] Step 3: Implement the module per spec FR-25b–f
  ```ts
  // frontend/src/composables/audio/preloadCache.ts
  import { audioApi, type AudioLookupResponse, type AudioContentType } from '@/api/audio'
  import { useAudioJobStore } from '@/stores/audioJob'

  type Key = string
  export interface CacheEntry {
    result?: AudioLookupResponse
    promise?: Promise<AudioLookupResponse>
    error?: Error
    createdAt: number
    expiresAt: number
  }
  export interface PreloadArgs {
    bookId: number
    contentType: AudioContentType | 'annotation'
    contentId: number
    voice?: string
  }

  const TTL_OK = 5 * 60 * 1000
  const TTL_ERR = 30 * 1000
  const cache = new Map<Key, CacheEntry>()
  const lastInvalidatedAt = new Map<Key, number>()
  let subscriptionInstalled = false

  function key(args: { contentType: PreloadArgs['contentType']; contentId: number }): Key {
    return `${args.contentType}:${args.contentId}`
  }

  function fetchOnce(args: PreloadArgs): Promise<AudioLookupResponse> {
    if (args.contentType === 'annotation') return audioApi.lookupAnnotation(args.contentId)
    return audioApi.lookup({
      book_id: args.bookId, content_type: args.contentType,
      content_id: args.contentId, voice: args.voice,
    })
  }

  export function getCached(k: Key): CacheEntry | undefined {
    const e = cache.get(k)
    if (!e) return undefined
    if (e.expiresAt < Date.now()) { cache.delete(k); return undefined }
    return e
  }

  export function preload(args: PreloadArgs): Promise<AudioLookupResponse> {
    const k = key(args)
    const existing = getCached(k)
    if (existing?.result) return Promise.resolve(existing.result)
    if (existing?.promise) return existing.promise
    if (existing?.error) return Promise.reject(existing.error)
    const startedAt = Date.now()
    const fetchPromise = fetchOnce(args)
    const wrapped: Promise<AudioLookupResponse> = fetchPromise.then(
      (result) => {
        const inv = lastInvalidatedAt.get(k) ?? 0
        if (inv > startedAt) {
          // Invalidated mid-flight; discard and re-fire (one retry)
          cache.delete(k)
          return preload(args)
        }
        cache.set(k, { result, createdAt: Date.now(), expiresAt: Date.now() + TTL_OK })
        return result
      },
      (err) => {
        cache.set(k, { error: err, createdAt: Date.now(), expiresAt: Date.now() + TTL_ERR })
        throw err
      },
    )
    cache.set(k, { promise: wrapped, createdAt: startedAt, expiresAt: startedAt + TTL_OK })
    return wrapped
  }

  export function invalidate(k: Key): void {
    lastInvalidatedAt.set(k, Date.now())
    cache.delete(k)
  }

  export function initCacheSubscription(): void {
    if (subscriptionInstalled) return
    subscriptionInstalled = true
    const store = useAudioJobStore()
    store.$onAction(({ name, args }) => {
      if (name !== 'recordContentCompletion') return
      const [contentType, contentId] = args as [string, number]
      invalidate(`${contentType}:${contentId}`)
      // section completions also invalidate the matching content view
      if (contentType === 'section_summary') invalidate(`section_content:${contentId}`)
      if (contentType === 'section_content') invalidate(`section_summary:${contentId}`)
    })
  }

  export function _resetForTests(): void {
    cache.clear()
    lastInvalidatedAt.clear()
    subscriptionInstalled = false
  }
  export function _inspect(k: Key): CacheEntry | undefined { return cache.get(k) }
  ```

- [ ] Step 4: Confirm GREEN
  Run: `cd frontend && npm run test:unit -- preloadCache.spec`
  Expected: 4 passed.

- [ ] Step 5: **Route useTtsEngine.load through preloadCache (L1-F1 fix)**
  In `useTtsEngine.ts` `load()`, replace the existing `audioApi.lookup(...)` block with:
  ```ts
  import * as preloadCache from './preloadCache'
  // inside load():
  let lookup: AudioLookupResponse
  try {
    lookup = await preloadCache.preload({
      bookId: args.bookId, contentType: args.contentType,
      contentId: args.contentId, voice: args.voice,
    })
  } catch (err) {
    store.setError('lookup_failed')
    throw err
  }
  ```
  This means: when TtsPlayButton's onMount preload has already populated the cache, `preloadCache.preload()` resolves synchronously inside `useTtsEngine.load()`, and `engine.play()` is reached without a fresh `await fetch` — preserving the iOS Safari user-gesture chain (FR-25h, D16, spec FR-24).

  Add the corresponding test to `useTtsEngine.spec.ts`:
  ```ts
  it('routes lookup via preloadCache.preload (FR-24, FR-25h)', async () => {
    const cacheSpy = vi.spyOn(preloadCache, 'preload').mockResolvedValue({
      pregenerated: false, sanitized_text: 'X.', sentence_offsets_chars: [0],
    } as any)
    const lookupSpy = vi.spyOn(audioApi, 'lookup')
    const api = useTtsEngine()
    await api.load({ bookId: 1, contentType: 'section_summary', contentId: 5 })
    expect(cacheSpy).toHaveBeenCalled()
    expect(lookupSpy).not.toHaveBeenCalled()
  })
  ```

- [ ] Step 6: Confirm GREEN on both test files
  Run: `cd frontend && npm run test:unit -- preloadCache.spec useTtsEngine.spec`
  Expected: preloadCache 4 passed; useTtsEngine 3 passed (settings + terminate + cache-routing).

- [ ] Step 7: Commit
  ```bash
  git add frontend/src/composables/audio/preloadCache.ts frontend/src/composables/audio/__tests__/preloadCache.spec.ts frontend/src/composables/audio/useTtsEngine.ts frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts
  git commit -m "feat(frontend): preloadCache + route useTtsEngine.load through it (FR-24, FR-25h)"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- preloadCache.spec useTtsEngine.spec` — 4+3 passed
- `cd frontend && npm run type-check` — no errors

---

### T8: Frontend — `audioJob.recordContentCompletion` action + `useBufferedJobStream` wiring

**Goal:** Per-content audio events fire a Pinia action that the cache can subscribe to.
**Spec refs:** FR-25f; this plan D1.

**Files:**
- Modify: `frontend/src/stores/audioJob.ts`
- Modify: `frontend/src/composables/useBufferedJobStream.ts:90-220`
- Test: `frontend/src/composables/__tests__/useBufferedJobStream.audioEvents.spec.ts` (extend)

**Steps:**

- [ ] Step 1: Inspect `useBufferedJobStream.ts` cases
  Run: `grep -n "case 'section_audio_completed'\\|case 'section_audio_failed'\\|case 'section_audio_already_stale'\\|case 'book_audio_completed'\\|case 'annotations_playlist_audio_completed'" frontend/src/composables/useBufferedJobStream.ts`
  Note all matched lines. The wiring (Step 4) must touch each case.

- [ ] Step 2: Write failing test
  ```ts
  // extend frontend/src/composables/__tests__/useBufferedJobStream.audioEvents.spec.ts
  it('calls audioJob.recordContentCompletion on section_audio_completed', async () => {
    setActivePinia(createPinia())
    const store = useAudioJobStore()
    const spy = vi.spyOn(store, 'recordContentCompletion')
    // Fire applyEvent for section_audio_completed with section_id=42
    // (use whatever existing test scaffolding the file has)
    applyEvent({
      event: 'section_audio_completed',
      section_id: 42,
      // ... other required fields
    } as any)
    expect(spy).toHaveBeenCalledWith('section_summary', 42)
  })
  ```

- [ ] Step 3: Confirm RED — `recordContentCompletion is not a function`.

- [ ] Step 4: Add the action to `audioJob.ts`
  Inside the `defineStore` setup function, before the `return { ... }`:
  ```ts
  function recordContentCompletion(contentType: string, contentId: number): void {
    // No state mutation — this exists purely as a $onAction beacon for preloadCache
    void contentType; void contentId
  }
  ```
  Add `recordContentCompletion` to the returned object.

- [ ] Step 5: Wire from `useBufferedJobStream.applyEvent`
  In each per-content case (`section_audio_completed`, `section_audio_failed`, `section_audio_already_stale`), add:
  ```ts
  useAudioJobStore().recordContentCompletion('section_summary', ev.section_id)
  ```
  For book-level events (`book_audio_completed` etc.), use `'book_summary'` and `ev.book_id`. For annotations playlist events, use `'annotations_playlist'` and `ev.book_id`.

- [ ] Step 6: Confirm GREEN
  Run: `cd frontend && npm run test:unit -- useBufferedJobStream.audioEvents`
  Expected: previously-passing tests still pass + new test passes.

- [ ] Step 7: Commit
  ```bash
  git add frontend/src/stores/audioJob.ts frontend/src/composables/useBufferedJobStream.ts frontend/src/composables/__tests__/useBufferedJobStream.audioEvents.spec.ts
  git commit -m "feat(frontend): audioJob.recordContentCompletion + wire from useBufferedJobStream"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useBufferedJobStream` — all pass
- `cd frontend && npm run type-check` — no errors

---

### T9: Frontend — `AppShell.vue` mounts Playbar + global Space + cache subscription init

**Goal:** Single mount point for global audio chrome.
**Spec refs:** FR-13, FR-14, FR-25f.

**Files:**
- Modify: `frontend/src/components/app/AppShell.vue`

**Steps:**

- [ ] Step 1: Read AppShell to find the right insertion point
  Run: `cat frontend/src/components/app/AppShell.vue`
  Locate the `<template>` root and where global chrome (toasts, modals) currently mounts.

- [ ] Step 2: Add the Playbar + handler
  ```vue
  <script setup lang="ts">
  import { onMounted, onUnmounted } from 'vue'
  import { useTtsPlayerStore } from '@/stores/ttsPlayer'
  import Playbar from '@/components/audio/Playbar.vue'
  import { initCacheSubscription } from '@/composables/audio/preloadCache'
  // ... existing imports

  const ttsPlayer = useTtsPlayerStore()

  function onGlobalKeydown(e: KeyboardEvent) {
    if (e.key !== ' ') return
    if (!ttsPlayer.isActive) return
    const t = e.target as HTMLElement | null
    if (!t) return
    const tag = t.tagName
    const role = t.getAttribute('role')
    if (
      tag === 'INPUT' || tag === 'TEXTAREA' ||
      tag === 'BUTTON' || tag === 'A' ||
      role === 'button' ||
      t.isContentEditable
    ) return
    e.preventDefault()
    if (ttsPlayer.status === 'playing') ttsPlayer.pause()
    else ttsPlayer.play()
  }

  onMounted(() => {
    document.addEventListener('keydown', onGlobalKeydown)
    initCacheSubscription()
  })
  onUnmounted(() => document.removeEventListener('keydown', onGlobalKeydown))
  </script>

  <template>
    <!-- existing layout -->
    <slot />
    <Playbar />
  </template>
  ```

- [ ] Step 3: Verify Playbar appears in the rendered DOM only when `ttsPlayer.isActive===true`
  Run: `cd frontend && npm run build` — build succeeds.
  Then start dev server: `cd frontend && npm run dev` (or use the built app served from backend per CLAUDE.md interactive verification protocol). Manually:
  1. Open `http://localhost:5173` (or `:8765`).
  2. Open DevTools console: `useTtsPlayerStore().open({contentType:'section_summary', contentId:1})` — Playbar appears.
  3. `useTtsPlayerStore().close()` — Playbar disappears.
  4. With `isActive=true`, focus is on `body`: press Space → status toggles. Focus a `<button>` → press Space → only the button activates (no Playbar toggle).

- [ ] Step 4: Add a small AppShell test
  ```ts
  // frontend/src/components/app/__tests__/AppShell.audio.spec.ts
  it('mounts Playbar in DOM', () => {
    const wrapper = mount(AppShell)
    expect(wrapper.findComponent(Playbar).exists()).toBe(true)
  })
  it('calls initCacheSubscription on mount', () => {
    const spy = vi.spyOn(preloadCache, 'initCacheSubscription')
    mount(AppShell)
    expect(spy).toHaveBeenCalled()
  })
  ```

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/app/AppShell.vue frontend/src/components/app/__tests__/AppShell.audio.spec.ts
  git commit -m "feat(frontend): AppShell mounts Playbar + global Space + cache subscription"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- AppShell.audio` — passes
- `cd frontend && npm run build` — succeeds
- Manual DOM check per Step 3

---

### T10: Frontend — delete reader-scoped Space handler in `ReadingArea.vue`

**Goal:** Remove the no-op-race source (FR-14b).
**Spec refs:** FR-14b, D19 (spec).

**Files:**
- Modify: `frontend/src/components/reader/ReadingArea.vue:45-50`
- Test: `frontend/src/components/reader/__tests__/ReadingArea.keybindings.spec.ts` (relocate the Space test to AppShell.audio.spec)

**Steps:**

- [ ] Step 1: Delete lines 45-50 from `ReadingArea.vue` (the `if (e.key === ' ') { … }` block inside the `if (ttsPlayer?.isActive)` branch). Keep ArrowLeft and ArrowRight branches intact.

- [ ] Step 2: Update existing test
  Open `frontend/src/components/reader/__tests__/ReadingArea.keybindings.spec.ts`. Find the test asserting Space toggles play/pause. Either delete it (it's now AppShell's concern) or rewrite to assert that ReadingArea does NOT call `ttsPlayer.play()/pause()` on Space. Add the equivalent positive assertion to `AppShell.audio.spec.ts` from T9.

- [ ] Step 3: Run tests
  Run: `cd frontend && npm run test:unit -- ReadingArea AppShell.audio`
  Expected: all pass.

- [ ] Step 4: Manual smoke
  Start dev server. Navigate to a section content view. Open Playbar via console. Press Space with focus on body → toggles ONCE (was twice). Press ArrowLeft/Right → still skips sentences as before.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/reader/ReadingArea.vue frontend/src/components/reader/__tests__/ReadingArea.keybindings.spec.ts frontend/src/components/app/__tests__/AppShell.audio.spec.ts
  git commit -m "refactor(frontend): remove reader-scoped Space handler (global owner is AppShell)"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- ReadingArea AppShell.audio` — all pass

---

### T11: Frontend — `TtsPlayButton.vue` overhaul (preload + visibility + lifecycle)

**Goal:** Implements the gesture-preserving preload, visibility predicate, click-loading, and unmount teardown. On preload error or runtime engine_unavailable, error path falls through to Playbar's existing error+Retry UI (FR-20).
**Spec refs:** FR-15 (loading), FR-17, FR-20, FR-25a, FR-25g, FR-25h.

**Files:**
- Modify: `frontend/src/components/audio/TtsPlayButton.vue`
- Test: `frontend/src/components/audio/__tests__/TtsPlayButton.spec.ts` (extend)

**Steps:**

- [ ] Step 1: Write failing tests
  ```ts
  // extend TtsPlayButton.spec.ts
  describe('TtsPlayButton preload + visibility', () => {
    it('renders with visibility:hidden initially when WS unsupported', async () => {
      _resetWebSpeechProbe(); ;(globalThis as any).window = {}
      const w = mount(TtsPlayButton, { props: { contentType: 'section_summary', contentId: 1, hasSummary: true, bookId: 1 } })
      expect(w.element.style.visibility).toBe('hidden')
    })
    it('hides after preload result if !pregenerated and !webSpeechSupported', async () => {
      ;(globalThis as any).window = {}
      vi.spyOn(preloadCache, 'preload').mockResolvedValue({ pregenerated: false, sanitized_text: 'X.', sentence_offsets_chars: [0] } as any)
      const w = mount(TtsPlayButton, { props: { contentType: 'section_summary', contentId: 1, hasSummary: true, bookId: 1 } })
      // Force preload trigger (jsdom has no IO; simulate)
      await (w.vm as any)._triggerPreloadForTests()
      await flushPromises()
      expect(w.element.style.display).toBe('none')
    })
    it('hides when sanitized_text is empty (G4)', async () => {
      ;(globalThis as any).window = { speechSynthesis: {} }
      vi.spyOn(preloadCache, 'preload').mockResolvedValue({ pregenerated: false, sanitized_text: '', sentence_offsets_chars: [] } as any)
      const w = mount(TtsPlayButton, { props: { contentType: 'annotation', contentId: 9 } })
      await (w.vm as any)._triggerPreloadForTests()
      await flushPromises()
      expect(w.element.style.display).toBe('none')
    })
    it('disables button + shows spinner during loading state', async () => {
      const w = mount(TtsPlayButton, { props: { contentType: 'section_summary', contentId: 1, hasSummary: true, bookId: 1 } })
      vi.spyOn(preloadCache, 'getCached').mockReturnValue({ result: { pregenerated: false, sanitized_text: 'X.', sentence_offsets_chars: [0] } as any, createdAt: 0, expiresAt: Date.now() + 1000 })
      await w.find('button').trigger('click')
      expect(w.find('button').attributes('disabled')).toBeDefined()
    })
    it('disconnects observer on unmount (G13)', () => {
      const disconnect = vi.fn()
      ;(globalThis as any).IntersectionObserver = vi.fn(() => ({ observe: vi.fn(), disconnect, unobserve: vi.fn() })) as any
      const w = mount(TtsPlayButton, { props: { contentType: 'section_summary', contentId: 1, hasSummary: true, bookId: 1 } })
      w.unmount()
      expect(disconnect).toHaveBeenCalled()
    })
  })
  ```

- [ ] Step 2: Confirm RED.

- [ ] Step 3: Implement TtsPlayButton overhaul
  Replace the entire component (file is small — ~40 lines current, ~120 lines after). Skeleton:
  ```vue
  <script setup lang="ts">
  import { computed, onMounted, onUnmounted, ref } from 'vue'
  import type { AudioLookupResponse } from '@/api/audio'
  import { useTtsPlayerStore } from '@/stores/ttsPlayer'
  import { useTtsEngine } from '@/composables/audio/useTtsEngine'
  import { useWebSpeechSupported } from '@/composables/useWebSpeechSupported'
  import * as preloadCache from '@/composables/audio/preloadCache'

  const props = defineProps<{
    contentType: 'section_summary' | 'book_summary' | 'section_content' | 'annotations_playlist' | 'annotation'
    contentId: number
    hasSummary?: boolean
    bookId?: number
  }>()

  const store = useTtsPlayerStore()
  const engine = useTtsEngine()
  const { supported: webSpeechSupported } = useWebSpeechSupported()

  const buttonEl = ref<HTMLButtonElement | null>(null)
  const preloadResult = ref<AudioLookupResponse | null>(null)
  const preloadFailed = ref(false)
  const loadingClick = ref(false)
  // Visibility tri-state: 'hidden-while-resolving' | true | false
  const resolveState = ref<'hidden-while-resolving' | 'visible' | 'gone'>('hidden-while-resolving')
  let observer: IntersectionObserver | null = null
  let fallbackTimer: number | null = null
  const PRELOAD_KEY = `${props.contentType}:${props.contentId}`

  const visibilityComputed = computed(() => {
    if (props.hasSummary === false) return 'gone'
    const r = preloadResult.value
    if (r === null && !preloadFailed.value) return resolveState.value
    if (r && r.sanitized_text === '') return 'gone'
    if (webSpeechSupported.value) return 'visible'
    if (r?.pregenerated) return 'visible'
    return 'gone'
  })
  const inlineStyle = computed(() => {
    const v = visibilityComputed.value
    if (v === 'gone') return { display: 'none' }
    if (v === 'hidden-while-resolving') return { visibility: 'hidden' as const }
    return {}
  })
  const disabled = computed(() => loadingClick.value || props.hasSummary === false)

  async function triggerPreload(): Promise<void> {
    if (props.hasSummary === false) return
    try {
      const result = await preloadCache.preload({
        bookId: props.bookId ?? 0,
        contentType: props.contentType,
        contentId: props.contentId,
      })
      preloadResult.value = result
    } catch {
      preloadFailed.value = true
    }
  }

  async function onClick(): Promise<void> {
    if (visibilityComputed.value === 'gone') return
    loadingClick.value = true
    try {
      store.open({ contentType: props.contentType, contentId: props.contentId })
      await engine.load({
        bookId: props.bookId ?? 0,
        contentType: props.contentType,
        contentId: props.contentId,
      })
      // Engine.play() is called inside load(); verify against current useTtsEngine impl
    } finally {
      loadingClick.value = false
    }
  }

  onMounted(() => {
    if (props.contentType === 'section_content') {
      // Hover/focus/touchstart preload for large content (G1)
      const el = buttonEl.value
      if (el) {
        const trigger = () => { el.removeEventListener('mouseenter', trigger); el.removeEventListener('focus', trigger); el.removeEventListener('touchstart', trigger); void triggerPreload() }
        el.addEventListener('mouseenter', trigger, { once: true })
        el.addEventListener('focus', trigger, { once: true })
        el.addEventListener('touchstart', trigger, { once: true, passive: true })
      }
    } else if (typeof IntersectionObserver !== 'undefined') {
      observer = new IntersectionObserver((entries) => {
        if (entries[0]?.isIntersecting) {
          observer?.disconnect()
          window.setTimeout(triggerPreload, 500)  // 500ms debounce per FR-25a
        }
      }, { rootMargin: '200px' })
      if (buttonEl.value) observer.observe(buttonEl.value)
    }
    fallbackTimer = window.setTimeout(() => {
      if (resolveState.value === 'hidden-while-resolving') resolveState.value = webSpeechSupported.value ? 'visible' : 'gone'
    }, 300)
  })
  onUnmounted(() => {
    observer?.disconnect()
    if (fallbackTimer !== null) window.clearTimeout(fallbackTimer)
  })

  // Test hook
  defineExpose({ _triggerPreloadForTests: triggerPreload })
  </script>

  <template>
    <button
      ref="buttonEl"
      type="button"
      class="btn-secondary"
      :style="inlineStyle"
      :disabled="disabled || undefined"
      :aria-disabled="disabled ? 'true' : undefined"
      :title="props.hasSummary === false ? 'Audio is only generated for summaries' : 'Listen'"
      @click="onClick"
    >
      <svg v-if="!loadingClick" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path d="M6 4l10 6-10 6V4z" />
      </svg>
      <svg v-else class="h-4 w-4 animate-spin" viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="40" />
      </svg>
      <span>Listen</span>
    </button>
  </template>
  ```
  Note: the existing test `TtsPlayButton.spec.ts` checks `disabled` based on `hasSummary` — keep that contract.

- [ ] Step 4: Confirm GREEN
  Run: `cd frontend && npm run test:unit -- TtsPlayButton.spec`
  Expected: all pass (existing + 5 new). If any existing tests break, the implementer adjusts to the new visibility model.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/TtsPlayButton.vue frontend/src/components/audio/__tests__/TtsPlayButton.spec.ts
  git commit -m "feat(frontend): TtsPlayButton preload+visibility+lifecycle overhaul"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- TtsPlayButton` — all pass
- `cd frontend && npm run type-check` — no errors
- `cd frontend && npm run build` — succeeds

---

### T12: Frontend — `audioApi.lookupAnnotation` helper

**Goal:** Thin wrapper over the new backend route.
**Spec refs:** FR-23, §7.4.

**Files:**
- Modify: `frontend/src/api/audio.ts`
- Test: `frontend/src/api/__tests__/audioContentType.spec.ts` (extend)

**Steps:**

- [ ] Step 1: Write failing test
  ```ts
  it('lookupAnnotation hits /audio/annotations/{id}/lookup', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ pregenerated: false, sanitized_text: 'X', sentence_offsets_chars: [0] })
    await audioApi.lookupAnnotation(42)
    expect(spy).toHaveBeenCalledWith('/audio/annotations/42/lookup')
  })
  ```

- [ ] Step 2: Confirm RED.

- [ ] Step 3: Add helper
  In `frontend/src/api/audio.ts` `audioApi` object:
  ```ts
  lookupAnnotation(annotationId: number): Promise<AudioLookupResponse> {
    return apiClient.get<AudioLookupResponse>(`/audio/annotations/${annotationId}/lookup`)
  },
  ```

- [ ] Step 4: GREEN.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/api/audio.ts frontend/src/api/__tests__/audioContentType.spec.ts
  git commit -m "feat(frontend): audioApi.lookupAnnotation wrapper"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- audioContentType` — passes

---

## Phase 3: UX surfaces — Listen entry points, Settings, button parity

Phase produces the user-facing slice: BookSummaryTab spinner + Listen button,
Listen on section views and annotations, Settings polish, mediaSession on
both engines, button parity sweep across the app. After this phase the bundle
is shippable.

### T13: Frontend — `BookSummaryTab.vue` spinner + elapsed timer + ARIA + 409 reattach

**Goal:** FR-01 through FR-07b implemented.
**Spec refs:** FR-01, FR-02, FR-03 (ARIA), FR-04, FR-05, FR-06, FR-07, FR-07b.

**Files:**
- Modify: `frontend/src/components/book/BookSummaryTab.vue`
- Test: `frontend/src/components/book/__tests__/BookSummaryTab.spec.ts` (extend)

**Steps:**

- [ ] Step 1: Write failing tests
  ```ts
  it('shows spinner + 0:00 elapsed within 1s after POST 201', async () => {
    vi.useFakeTimers()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ job_id: 7 }), { status: 201 }) as any)
    const w = mount(BookSummaryTab, { props: { book: { id: 1, sections: [{id:1, has_summary:true}], default_summary: null } } })
    await w.find('button.generate-cta').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Generating book summary')
    expect(w.text()).toContain('0:00 elapsed')
    expect(w.find('[role="status"]').exists()).toBe(true)
    expect(w.find('[role="status"]').attributes('aria-live')).toBe('polite')
    expect(w.find('[role="status"]').attributes('aria-busy')).toBe('true')
    expect(w.find('button.cancel-cta').exists()).toBe(false)  // Cancel removed
    // Tick 1500ms
    vi.advanceTimersByTime(1500)
    await flushPromises()
    expect(w.text()).toContain('0:01 elapsed')
  })

  it('on 409 uses active_job_started_at for elapsed (not Date.now)', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-04T10:05:00Z'))
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      detail: '...', active_job_id: 9, active_job_started_at: '2026-05-04T10:00:00Z',
    }), { status: 409 }) as any)
    const w = mount(BookSummaryTab, { props: { book: { id: 1, sections: [{id:1,has_summary:true}], default_summary: null } } })
    await w.find('button.generate-cta').trigger('click')
    await flushPromises()
    // 5 minutes elapsed
    expect(w.text()).toMatch(/5:0\d elapsed/)
  })
  ```

- [ ] Step 2: Confirm RED.

- [ ] Step 3: Implement
  Modify `BookSummaryTab.vue`:
  - Add refs: `startedAt = ref<number | null>(null)`, `nowTick = ref(Date.now())`. Set up a `setInterval(() => nowTick.value = Date.now(), 1000)` started in `attachSse`, cleared in `detachSse`.
  - `elapsedMs = computed(() => startedAt.value ? nowTick.value - startedAt.value : 0)`.
  - `formatElapsed(ms): string` — `MM:SS` past 9:59, else `M:SS`.
  - In `startGenerate()`: on 201/202, `startedAt.value = Date.now()`. On 409, parse `body.active_job_started_at` → `startedAt.value = parseISO(...).getTime()` (use `Date.parse(...)` for ISO8601 with `Z`).
  - Replace the `state==='inProgress'` template:
    ```vue
    <template v-else-if="state === 'inProgress'">
      <div class="book-summary-tab__progress" role="status" aria-live="polite" aria-busy="true">
        <div class="spinner" aria-hidden="true"></div>
        <p>Generating book summary… {{ formatElapsed(elapsedMs) }} elapsed</p>
      </div>
    </template>
    ```
  - Add scoped CSS for `.spinner` with `@keyframes` rotation, and `@media (prefers-reduced-motion: reduce) { .spinner { animation: none; } }`.
  - **Remove** the `<button class="btn-secondary" @click="cancelJob">Cancel</button>` — FR-04. Also remove the now-unused `cancelJob()` function.
  - Disable the Generate button while `state === 'inProgress'`: `:disabled="summarizedCount === 0 || state === 'inProgress'"`.

- [ ] Step 4: GREEN
  Run: `cd frontend && npm run test:unit -- BookSummaryTab.spec`
  Expected: existing + 2 new pass.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/book/BookSummaryTab.vue frontend/src/components/book/__tests__/BookSummaryTab.spec.ts
  git commit -m "feat(frontend): BookSummaryTab spinner + elapsed timer + ARIA live + 409 reattach"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- BookSummaryTab` — all pass

---

### T14: Frontend — Listen button in `ReaderHeader` actions slot via `BookDetailView`

**Goal:** Listen button on section summary AND section content surfaces (FR-15).
**Spec refs:** FR-15.

**Files:**
- Modify: `frontend/src/views/BookDetailView.vue:240-296`

**Steps:**

- [ ] Step 1: Read the current ReaderHeader invocation in BookDetailView
  Run: `grep -n "ReaderHeader" frontend/src/views/BookDetailView.vue`
  Expected: a `<ReaderHeader …>` instance somewhere above line 240.

- [ ] Step 2: Insert TtsPlayButton into the `actions` slot
  ```vue
  <ReaderHeader … >
    <template #actions>
      <TtsPlayButton
        v-if="reader.currentSection"
        :content-type="reader.contentMode === 'summary' ? 'section_summary' : 'section_content'"
        :content-id="reader.currentSection.id"
        :has-summary="reader.contentMode === 'summary' ? !!reader.currentSection.default_summary?.summary_md : true"
        :book-id="reader.book?.id"
      />
    </template>
  </ReaderHeader>
  ```
  Add `import TtsPlayButton from '@/components/audio/TtsPlayButton.vue'` to the script block.

- [ ] Step 3: Manual smoke
  Build + serve. Navigate to `/books/1/sections/1?tab=summary` — Listen button visible in the header. Toggle to content — same button rebound to `section_content`. Click each — Playbar opens; Web Speech or MP3 plays per the existing engine routing.

- [ ] Step 4: Commit
  ```bash
  git add frontend/src/views/BookDetailView.vue
  git commit -m "feat(frontend): mount TtsPlayButton in ReaderHeader actions for section views"
  ```

**Inline verification:**
- `cd frontend && npm run build` — succeeds
- Manual DOM check per Step 3

---

### T15: Frontend — Listen button in `BookSummaryTab` populated header

**Goal:** Listen on book-summary view (FR-15).
**Spec refs:** FR-15.

**Files:**
- Modify: `frontend/src/components/book/BookSummaryTab.vue:148-160`

**Steps:**

- [ ] Step 1: Insert button in the populated header action row, leftmost
  ```vue
  <header class="book-summary-tab__header">
    <h2>Book Summary</h2>
    <div class="book-summary-tab__actions">
      <TtsPlayButton
        content-type="book_summary"
        :content-id="book.id"
        :has-summary="true"
        :book-id="book.id"
      />
      <button class="btn-secondary" type="button" @click="readSectionSummaries">
        Read Section Summaries
      </button>
      <button class="btn-secondary regenerate-cta" type="button" @click="startGenerate">
        Regenerate
      </button>
    </div>
  </header>
  ```
  Add `import TtsPlayButton from '@/components/audio/TtsPlayButton.vue'`.

- [ ] Step 2: Update existing BookSummaryTab test snapshot if needed (check for `wrapper.findAll('button')` count assertions).

- [ ] Step 3: Manual smoke
  Navigate to `/books/1?tab=summary` (with a populated book summary) — Listen visible leftmost. Click — Playbar opens. Click Regenerate — works as before.

- [ ] Step 4: Commit
  ```bash
  git add frontend/src/components/book/BookSummaryTab.vue
  git commit -m "feat(frontend): Listen button in BookSummaryTab populated header"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- BookSummaryTab` — all pass

---

### T16: Frontend — Per-row Listen button in `AnnotationsView`

**Goal:** FR-16.
**Spec refs:** FR-16.

**Files:**
- Modify: `frontend/src/views/AnnotationsView.vue:40-50`
- Possibly also a per-row component (check during implementation)

**Steps:**

- [ ] Step 1: Read AnnotationsView to find the per-row template
  Run: `cat frontend/src/views/AnnotationsView.vue`
  Identify whether annotations render inline in the v-for or via a child component (e.g., `<AnnotationCard>`).

- [ ] Step 2: Insert TtsPlayButton inside each annotation row, right-aligned
  ```vue
  <div v-for="annotation in store.annotations" :key="annotation.id" class="annotation-row">
    <!-- existing annotation content -->
    <div class="annotation-actions">
      <TtsPlayButton
        content-type="annotation"
        :content-id="annotation.id"
        :book-id="annotation.book_id || 0"
      />
      <!-- existing delete/edit buttons -->
    </div>
  </div>
  ```
  Add the import. Note: `bookId` is informational only for `annotation` contentType (the route doesn't use it); pass 0 if the annotation object doesn't carry one.

- [ ] Step 3: Manual smoke
  Navigate to `/annotations` (or the per-book annotations route). Per-row Listen visible. Click on row N → Playbar opens with that annotation's text. Click on row N+1 → switches immediately (J7 / E8).

- [ ] Step 4: Commit
  ```bash
  git add frontend/src/views/AnnotationsView.vue
  git commit -m "feat(frontend): per-row Listen button on AnnotationsView"
  ```

**Inline verification:**
- `cd frontend && npm run build` — succeeds
- Manual DOM check per Step 3

---

### T17: Frontend — `SettingsTtsPanel` Reset + Loading-voices + persisted-voice hint

**Goal:** FR-26, FR-27, FR-28.
**Spec refs:** FR-26, FR-27, FR-28, D13 (spec).

**Files:**
- Modify: `frontend/src/components/settings/SettingsTtsPanel.vue`
- Test: `frontend/src/components/settings/__tests__/SettingsTtsPanel.spec.ts` (NEW)

**Steps:**

- [ ] Step 1: Write failing tests
  ```ts
  // frontend/src/components/settings/__tests__/SettingsTtsPanel.spec.ts
  it('Reset to defaults PUTs canonical defaults', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }) as any)
    vi.spyOn(globalThis, 'confirm').mockReturnValue(true)
    const w = mount(SettingsTtsPanel)
    await w.find('[data-testid="reset"]').trigger('click')
    expect(fetchSpy).toHaveBeenLastCalledWith('/api/v1/settings/tts', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ engine: 'web-speech', voice: '', default_speed: 1.0, auto_advance: true }),
    }))
  })

  it('shows Loading voices… while voices empty and probe in flight', async () => {
    ;(globalThis as any).window = { speechSynthesis: { getVoices: () => [], onvoiceschanged: null } }
    const w = mount(SettingsTtsPanel)
    await flushPromises()
    expect(w.text()).toContain('Loading voices…')
  })

  it('shows persisted-voice-missing hint when saved voice not in list', async () => {
    ;(globalThis as any).window = { speechSynthesis: { getVoices: () => [{ name: 'Daniel' }], onvoiceschanged: null } }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ engine: 'web-speech', voice: 'Alex', default_speed: 1.0, auto_advance: true }), { status: 200 }) as any)
    const w = mount(SettingsTtsPanel)
    await flushPromises()
    expect(w.text()).toContain('Previously selected voice not available')
  })
  ```

- [ ] Step 2: Confirm RED.

- [ ] Step 3: Implement
  In `SettingsTtsPanel.vue`:
  - **Reset button** in the action row next to Save:
    ```vue
    <button type="button" data-testid="reset" class="btn-secondary" @click="onReset" :disabled="saving">
      Reset to defaults
    </button>
    ```
    ```ts
    async function onReset() {
      if (!window.confirm('Reset TTS settings to defaults?')) return
      saving.value = true
      try {
        const r = await fetch('/api/v1/settings/tts', {
          method: 'PUT',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ engine: 'web-speech', voice: '', default_speed: 1.0, auto_advance: true }),
        })
        if (!r.ok) throw new Error(`reset failed: ${r.status}`)
        await load()
      } catch (e) {
        error.value = e instanceof Error ? e.message : 'reset failed'
      } finally { saving.value = false }
    }
    ```
  - **Loading voices placeholder:** in the `<select v-model="webSpeechVoice">`:
    ```vue
    <option v-if="webSpeechVoices.length === 0 && !noVoicesAvailable" disabled>Loading voices…</option>
    <option v-else-if="noVoicesAvailable" value="" disabled>No voices available</option>
    ```
  - **Persisted-voice-missing hint:** computed
    ```ts
    const persistedVoiceMissing = computed(() =>
      webSpeechVoice.value && webSpeechVoices.value.length > 0 && !webSpeechVoices.value.includes(webSpeechVoice.value)
    )
    ```
    Render above the picker:
    ```vue
    <p v-if="persistedVoiceMissing" class="text-xs text-amber-700">
      Previously selected voice not available; falling back to browser default.
    </p>
    ```

- [ ] Step 4: GREEN
  Run: `cd frontend && npm run test:unit -- SettingsTtsPanel.spec`
  Expected: 3 passed.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/settings/SettingsTtsPanel.vue frontend/src/components/settings/__tests__/SettingsTtsPanel.spec.ts
  git commit -m "feat(frontend): SettingsTtsPanel Reset + Loading placeholder + missing-voice hint"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- SettingsTtsPanel` — 3 passed
- Manual: navigate to /settings/tts, click Reset, confirm dialog, observe Save indicator

---

### T18: Frontend — mediaSession metadata on both engines

**Goal:** WebSpeechEngine sets navigator.mediaSession; Mp3Engine extends existing wiring to vary title by contentType (FR-19, FR-19b).
**Spec refs:** FR-19, FR-19b, D14 (spec).

**Files:**
- Modify: `frontend/src/composables/audio/webSpeechEngine.ts`
- Modify: `frontend/src/composables/audio/mp3Engine.ts:105-122`

**Steps:**

- [ ] Step 1: Read the existing mp3Engine mediaSession block
  Run: `sed -n '100,130p' frontend/src/composables/audio/mp3Engine.ts`
  Note the current title argument; identify where it would receive a contentType-derived title.

- [ ] Step 2: Add a helper module
  ```ts
  // frontend/src/composables/audio/mediaSessionTitles.ts
  export function titleForContentType(ct: string): string {
    switch (ct) {
      case 'section_summary': return 'Section summary'
      case 'book_summary': return 'Book summary'
      case 'section_content': return 'Section content'
      case 'annotation': return 'Annotation'
      case 'annotations_playlist': return 'Annotations playlist'
      default: return 'Audio'
    }
  }
  ```

- [ ] Step 3: Wire WebSpeechEngine
  In `webSpeechEngine.ts`, the constructor accepts an optional `contentType?: string` (or the caller passes a `title?` directly). Modify `useTtsEngine.load()` to pass `title: titleForContentType(args.contentType)` and `artist: bookTitle` (resolved via `useBooksStore` if available; else empty). Inside `WebSpeechEngine.play()`, on the first call, set `navigator.mediaSession.metadata = new MediaMetadata({ title, artist, album: 'Book Companion' })` if `mediaSessionEnabled` on the store is true. Also wire `setActionHandler('play'|'pause'|'stop')`.

- [ ] Step 4: Wire Mp3Engine
  In `mp3Engine.ts:105-122`, replace the current static title (whatever it is) with `titleForContentType(opts.contentType)`. Caller (`useTtsEngine.load`) passes contentType into the constructor opts.

- [ ] Step 5: Smoke test
  Manual on macOS: trigger Listen on a section summary. Open the Now Playing widget in macOS menubar — should show "Section summary" + book title + "Book Companion". Same for book summary, content, annotation. Hardware play/pause keys (if accessible) toggle Playbar.

- [ ] Step 6: Commit
  ```bash
  git add frontend/src/composables/audio/webSpeechEngine.ts frontend/src/composables/audio/mp3Engine.ts frontend/src/composables/audio/mediaSessionTitles.ts frontend/src/composables/audio/useTtsEngine.ts
  git commit -m "feat(frontend): mediaSession metadata varies by contentType (both engines)"
  ```

**Inline verification:**
- `cd frontend && npm run build` — succeeds
- Manual macOS Now Playing widget check per Step 5

---

### T19: Frontend — Promote `.btn-primary`/`.btn-secondary` global + sweep 9 scoped redefinitions

**Goal:** FR-08, FR-09. **No dark-mode rules needed** (Q4 resolved — `theme.css` uses `[data-theme='dark']` attribute selectors via custom properties).
**Spec refs:** FR-08, FR-09, D2, D3 (this plan).

**Files:**
- Modify: `frontend/src/assets/main.css`
- Modify: 9 files per Code Study Notes

**Steps:**

- [ ] Step 1: Add canonical global classes to `main.css`
  Append (after the existing utilities block):
  ```css
  .btn-primary,
  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    font-weight: 600;
    font-size: 0.9rem;
    text-decoration: none;
    border: 1px solid transparent;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  .btn-primary {
    background: var(--color-accent);
    color: var(--color-text-on-accent, #fff);
  }
  .btn-primary:hover { background: var(--color-accent-hover); }
  .btn-primary:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

  .btn-secondary {
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    border-color: var(--color-border);
  }
  .btn-secondary:hover { background: var(--color-bg-secondary); }
  .btn-secondary:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
  ```
  Token sourcing notes: `--color-text-on-accent` may not exist yet; if `theme.css` doesn't define it, add it to the `:root` block (`--color-text-on-accent: #ffffff;`) and to each `[data-theme='dark']`/sepia/etc. variant as appropriate (white on accent works for all current themes).

- [ ] Step 2: Per-file sweep — remove scoped `.btn-primary`/`.btn-secondary` blocks
  For each of the 9 files (per Code Study Notes), open and DELETE the entire `.btn-primary { ... }` and `.btn-secondary { ... }` rule blocks (and any `:hover` / `:focus-visible` / `:disabled` variants on those classes) inside `<style scoped>`. Leave other scoped rules untouched.

- [ ] Step 3: Run regression-grep gate
  ```bash
  ! grep -rn '\.btn-\(primary\|secondary\)\s*{' \
    frontend/src/components/audio/ \
    frontend/src/components/book/BookSummaryTab.vue \
    frontend/src/views/BookOverviewView.vue \
    frontend/src/views/JobProgressView.vue \
    frontend/src/components/settings/{ReadingSettings,DatabaseSettings,PresetSettings,PresetCreateEditForm,CustomEditor,BackupSettings}.vue
  ```
  Expected: zero matches → command exits 0.

- [ ] Step 4: Visual spot check (manual)
  Build, serve, open each surface in a browser:
  - `/` (LibraryView)
  - `/books/1` populated → BookSummaryTab populated header → Listen + Read Section Summaries + Regenerate buttons all canonical
  - `/books/1/sections/1?tab=summary` → reader header
  - `/processing/jobs` (JobProgressView)
  - `/settings/reading`, `/settings/database`, `/settings/presets`, `/settings/backup` — Save buttons canonical
  Take screenshots; if any surface looks materially worse, log as a /verify finding (not a plan failure).

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/assets/main.css frontend/src/components/book/BookSummaryTab.vue frontend/src/views/BookOverviewView.vue frontend/src/views/JobProgressView.vue frontend/src/components/settings/{ReadingSettings,DatabaseSettings,PresetSettings,PresetCreateEditForm,CustomEditor,BackupSettings}.vue
  git commit -m "refactor(frontend): promote .btn-primary/.btn-secondary global; sweep 9 scoped redefinitions"
  ```

**Inline verification:**
- Step 3 grep gate
- `cd frontend && npm run build` — succeeds
- Manual visual spot check per Step 4

---

### T20: Frontend — Sweep raw Tailwind in `audio/` + `TtsPlayButton`

**Goal:** FR-10, FR-11, FR-12 + spec §11.2 mapping table.
**Spec refs:** FR-10, FR-11, FR-12.

**Files:**
- Modify: 10 files per spec §11.2 mapping (audio/ folder + TtsPlayButton + SettingsTtsPanel Save)

**Steps:**

- [ ] Step 1: Apply spec §11.2 mapping per-file
  For each row in the mapping table, replace the named raw-Tailwind classes with `.btn-primary` or `.btn-secondary`. Specific edits:
  - **AudioTab.vue Generate audio:** `class="btn-primary"` (replace `bg-indigo-600 text-white …`)
  - **AudioTab.vue Cancel:** `class="btn-secondary"` (replace `bg-slate-200 …`)
  - **GenerateAudioModal.vue Generate:** `class="btn-primary"`
  - **GenerateAudioModal.vue Close:** `class="btn-secondary"`
  - **AudioFileRow.vue Play / Re-generate:** `class="btn-secondary"` (Delete button KEEPS its `text-red-600` styling per spec — NOT in sweep scope)
  - **AnnotationPlaylistRow.vue actions:** `class="btn-secondary"` for each action row button
  - **SectionsAudioRow.vue actions:** `class="btn-secondary"`
  - **Playbar.vue Play/Pause:** `class="btn-primary rounded-full p-2"` (keep `rounded-full` for icon shape)
  - **Playbar.vue Retry:** `class="btn-primary"`
  - **Playbar.vue Close (✕) + Prev + Next:** `class="btn-secondary rounded-full p-2"`
  - **StaleSourceBanner.vue Re-generate:** `class="btn-primary"`
  - **StaleSourceBanner.vue Dismiss:** `class="btn-secondary"`
  - **TtsPlayButton.vue:** already `.btn-secondary` per T11
  - **AnnotationsTab.vue Build playlist:** `class="btn-primary"`
  - **ResumeAffordance.vue Resume:** `class="btn-primary"`
  - **SettingsTtsPanel.vue Save:** `class="btn-primary"` (replace `bg-indigo-600 …`)

- [ ] Step 2: Regression grep
  ```bash
  ! grep -rn 'bg-indigo-\(500\|600\|700\)\|border-slate-\(200\|300\)' \
    frontend/src/components/audio/ frontend/src/components/audio/TtsPlayButton.vue
  ```
  Expected: zero matches.

- [ ] Step 3: Visual spot check (manual)
  - `/books/1?tab=audio` — Generate audio + Cancel + per-row buttons + Generate Audio Modal
  - Trigger Playbar (via console or Listen) — Play/Pause + Retry + Close all canonical
  - StaleSourceBanner if any audio is stale

- [ ] Step 4: Run existing audio component tests to verify nothing broke
  Run: `cd frontend && npm run test:unit -- audio`
  Expected: all pass.

- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/ frontend/src/components/settings/SettingsTtsPanel.vue
  git commit -m "refactor(frontend): sweep raw Tailwind to .btn-primary/.btn-secondary in audio surfaces"
  ```

**Inline verification:**
- Step 2 regression grep
- `cd frontend && npm run test:unit -- audio` — all pass
- Manual visual spot check per Step 3

---

### TN: Final Verification

**Goal:** Verify the entire implementation works end-to-end and matches every spec FR.

- [ ] **Lint & format:**
  ```bash
  cd backend && uv run ruff check . && uv run ruff format --check .
  cd frontend && npm run lint && npm run format
  ```
  Expected: all clean.

- [ ] **Type check:**
  ```bash
  cd frontend && npm run type-check
  ```
  Expected: 0 errors.

- [ ] **Backend unit + integration tests:**
  ```bash
  cd backend && uv run python -m pytest tests/unit/db/test_content_type_enum.py tests/integration/api/test_audio_lookup_annotation.py tests/integration/api/test_book_summary_409.py -v
  ```
  Expected: all passes; 0 failures.

- [ ] **Backend full suite (regression):**
  ```bash
  cd backend && uv run python -m pytest -m "not integration_llm"
  ```
  Expected: no regressions vs baseline.

- [ ] **Frontend unit tests (new + extended):**
  ```bash
  cd frontend && npm run test:unit -- preloadCache useTtsEngine useWebSpeechSupported TtsPlayButton BookSummaryTab SettingsTtsPanel AppShell.audio audioContentType useBufferedJobStream.audioEvents ReadingArea.keybindings
  ```
  Expected: all pass.

- [ ] **Frontend full suite (regression):**
  ```bash
  cd frontend && npm run test:unit
  ```
  Expected: no regressions.

- [ ] **Database migrations:**
  ```bash
  cd backend && uv run alembic -c app/migrations/alembic.ini upgrade head
  ```
  Expected: applied cleanly; new revision present in history.

- [ ] **Frontend build + ship to backend static dir** (per CLAUDE.md interactive verification protocol):
  ```bash
  cd frontend && npm run build
  rm -rf ../backend/app/static && cp -R dist ../backend/app/static
  cd backend && uv run bookcompanion serve --port 8765 &
  curl -sf http://localhost:8765/api/v1/health   # gate
  ```

- [ ] **API smoke test — annotation lookup:**
  ```bash
  # Pick an annotation id from the seeded DB
  curl -sf http://localhost:8765/api/v1/audio/annotations/1/lookup | python3 -m json.tool
  ```
  Expected: response with `pregenerated:false`, `sanitized_text` populated, `sanitizer_version_current` non-null.

- [ ] **API smoke test — 409 carries started_at:**
  ```bash
  # Trigger 409 by submitting two book-summary requests in quick succession
  curl -X POST -H "content-type: application/json" -d '{"preset_name":"practitioner_bullets"}' http://localhost:8765/api/v1/books/1/book-summary
  curl -X POST -H "content-type: application/json" -d '{"preset_name":"practitioner_bullets"}' http://localhost:8765/api/v1/books/1/book-summary | python3 -m json.tool
  ```
  Expected: second response is 409 with `active_job_started_at` ISO8601.

- [ ] **API smoke test — old route rejects annotation:**
  ```bash
  curl -i -sf "http://localhost:8765/api/v1/audio/lookup?book_id=1&content_type=annotation&content_id=1" | head -20
  ```
  Expected: `HTTP/1.1 400` with detail `use /audio/annotations/{id}/lookup for annotations`.

- [ ] **Frontend smoke test (Playwright MCP):**
  1. `browser_navigate` to `http://localhost:8765/books/1?tab=summary` (book has populated default_summary).
  2. `browser_snapshot` — confirm Listen button is leftmost in the action row alongside Read Section Summaries / Regenerate.
  3. `browser_click` on Listen — Playbar appears at bottom; engine chip shows `mp3` if pre-gen exists, else `web-speech`.
  4. `browser_navigate` to `/books/1/sections/1?tab=summary` — Listen visible in the reader header; Playbar is STILL visible (cross-route persistence).
  5. `browser_click` on the section's Listen — playback content swaps without confirmation.
  6. `browser_click` on Playbar's ✕ — Playbar disappears.
  7. **Hard-reload** `/books/1?tab=summary` (open in fresh tab via `browser_tabs`) — page renders correctly; Playbar absent until next click.
  8. **Hard-reload** `/books/1/sections/1?tab=content` — section content view renders the LISTEN button on hover/focus (NOT pre-loaded — section_content uses hover/focus per FR-25a / G1).
  9. **Hard-reload** `/annotations` (or the per-book annotations route) — page renders; per-row Listen buttons become visible (or hidden for empty-content annotations per G4).
  10. **Force error path A:** intercept `/api/v1/audio/annotations/1/lookup` with 500 (`browser_evaluate` mocks fetch) — visit AnnotationsView, click Listen → Playbar shows error+Retry.
  11. **Force error path B:** intercept `/api/v1/audio/lookup?content_type=section_content&...` with 500 — visit `/books/1/sections/1?tab=content`, hover Listen, then click — Playbar shows error+Retry (covers FR-25d error sentinel + click-time fallback for the hover/focus preload path).
  12. `browser_console_messages level=error` — should be empty.

- [ ] **In-progress spinner smoke test:**
  1. `browser_navigate` to `/books/1?tab=summary` for a book with NO default_summary but at least one summarized section.
  2. `browser_click` Generate book summary.
  3. Within 1s: `browser_snapshot` shows spinner element + "Generating book summary… 0:00 elapsed", no Cancel button.
  4. After 2s: text shows "0:01 elapsed" or "0:02 elapsed".
  5. Open DevTools accessibility tree; confirm `<div role="status" aria-live="polite" aria-busy="true">` wraps the message.
  6. Wait for `processing_completed` SSE — view swaps to populated state with the new summary.

- [ ] **Settings smoke test:**
  1. `browser_navigate` to `/settings/tts`.
  2. Click Reset — confirm dialog → after OK, voice picker reads default browser voice; speed reads 1.0.
  3. Pick a different voice + rate, Save → "Saved." indicator appears.
  4. Navigate to `/books/1?tab=summary`, click Listen — observe in DevTools Network the lookup response, then verify the `WebSpeechEngine.play()` invocation uses the saved voice (instrument via `vi.spy` if needed; or trust the e2e test from §13).

- [ ] **UX polish checklist:**
  - `document.title` updates per route (existing app behavior; verify with Generate / Listen flow).
  - No internal IDs in copy ("Audio file 7" → must be "Section summary audio" or similar).
  - Listen button title attribute is "Listen" (not "audio is only generated for summaries" except when disabled).
  - Spinner respects `prefers-reduced-motion` (toggle in DevTools rendering settings; spinner stops rotating).
  - All Listen buttons have visible focus rings (Tab through them; check focus-visible).
  - 0 uncaught console errors during the smoke flow.

- [ ] **Wireframe diff:** N/A — no wireframes for this feature.

- [ ] **No-op verifications (existing infra unchanged):**
  - **FR-25:** confirm `audio_files` / `audio_positions` repos and `SectionEditService` re-import flow are NOT modified by this branch: `git diff main backend/app/db/repositories/audio_file_repo.py backend/app/db/repositories/audio_position_repo.py backend/app/services/section_edit_service.py` — expect empty diff (annotation rows have nothing in those tables to clean up).
  - **FR-29:** verify `SettingsTtsPanel.vue` rate slider still has `min="0.5" max="2" step="0.05"` (Web Speech rate range — pre-existing).
  - **FR-30:** verify the **Test** affordance still works: navigate to /settings/tts, click the per-engine VoiceSampleButton — browser speaks the sample. (Pre-existing component; no changes.)
  - **FR-32:** Playwright e2e test (frontend smoke step 4 above) covers cross-route playback persistence — Playbar visible after navigation; only ✕ stops it.

- [ ] **FR coverage gate (mechanical):**
  ```bash
  grep -oE "FR-[0-9]+[a-z]?" docs/specs/2026-05-03-summary-and-audio-ux-fixes-spec.md | sort -u > /tmp/spec-frs.txt
  grep -oE "FR-[0-9]+[a-z]?" docs/plans/2026-05-04-summary-and-audio-ux-fixes-implementation-plan.md | sort -u > /tmp/plan-frs.txt
  diff /tmp/spec-frs.txt /tmp/plan-frs.txt
  ```
  Expected: empty diff (every spec FR-ID appears in the plan).

- [ ] **Manual iOS Safari spot check (NFR-02 residual risk):**
  Open the deployed app from an iPhone or iPad on the LAN. Tap Listen on a section summary that has NOT been preloaded (cold cache — fresh page load). Confirm Web Speech starts speaking within ~2s. If broken, document in /verify findings — it's a known residual risk per NFR-02; follow-up patch needed.

**Cleanup:**
- [ ] Stop the verification server: `kill $(lsof -ti:8765)`
- [ ] Remove temporary `frontend/dist/` if not part of the deploy strategy (keep if `make build-frontend` regenerates).
- [ ] Update `docs/changelog.md` with a v1.7 entry summarizing the four shipping fixes (separate task per CLAUDE.md "after merging to main, run /changelog").
- [ ] Update `CLAUDE.md` if any new gotchas surfaced during /execute (run-time discoveries → /session-log first, then condensed into CLAUDE.md).

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | L1-F1 (BLOCKER): useTtsEngine.load() in T5 didn't consume preloadCache → click-time `await audioApi.lookup()` defeated the preload AND broke iOS gesture chain. L1-F2 (significant): WebSpeechEngine + Mp3Engine constructor signatures touched by T5 + T18 — risk of /execute-time TypeError. L1-F3 (minor): 5 spec FRs uncited (FR-20, FR-25, FR-29, FR-30, FR-32). L1-F4 (minor): TN smoke missed annotations hard-reload + section_content error-path probe. | L1-F1: T5 split into "settings + ctor consolidation" (Phase 1, no cache) + cache routing now lives in T7's new Step 5 with its own test (Phase 2). L1-F2: T5 Step 3 now defines the FULL final WebSpeechEngine + Mp3Engine opts shape so /execute call-sites compile; T18 only fills metadata setters. L1-F3: T11 cites FR-20; new TN sub-section "No-op verifications" cites FR-25/29/30/32 with concrete checks. L1-F4: TN frontend smoke gained step 9 (hard-reload /annotations) and step 11 (section_content error-path probe). |
| 2 | (to be filled) | |
