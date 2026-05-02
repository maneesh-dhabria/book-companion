# Audiobook Mode — Implementation Plan

**Date:** 2026-05-02
**Spec:** `docs/specs/2026-05-02-audiobook-mode-spec.md`
**Simulation:** `docs/simulations/2026-05-02-audiobook-mode-simulation.md`
**Requirements:** `docs/requirements/2026-05-02-audiobook-mode-requirements.md`
**Wireframes:** `docs/wireframes/2026-05-02-audiobook-mode/`

---

## Overview

Build a pluggable two-engine TTS subsystem (Web Speech in browser + Kokoro-82M as local subprocess) with sentence-level highlight, ID3-tagged MP3 export, resume position, CLI parity, and a markdown→speech sanitizer. Tasks follow the spec's 8-phase carving (A–H) plus a final verification task TN. Each task is TDD: write the failing test → verify red → implement → verify green → commit.

**Done when:** all 70 spec FRs are implemented; `pytest tests/` passes (including new ~40 audio tests); `npm run test:unit` passes; Playwright e2e flows for J1 (click-play Web Speech), J2 (pre-generate book audio), J3 (annotations playlist) pass; `bookcompanion init` + `serve` + `listen --generate <id>` all work end-to-end on a clean install; `bookcompanion spike tts` emits a findings template.

**Execution order:**

```
A (backend foundation)  ─────────────► B (job + API wiring)
   │ deps, models, sanitizer,             │ AudioGenService, worker dispatch,
   │ provider ABC, Kokoro, ID3,           │ SSE events, FastAPI routes, lifespan
   │ migration, repo fixes                │ pre-warm + orphan recovery
   └─► A1..A17                            └─► B1..B16
                                                 │
                                                 ▼
                       ┌─────────── C (frontend reader playback)
                       │              ttsPlayer store, useTtsEngine,
                       │              Playbar, EngineChip, TtsPlayButton,
                       │              MarkdownRenderer sentence-wrap
                       │              C1..C15
                       │
                       ▼
                  D (Audio tab + Generate modal) [P with E]
                  D1..D8  — BookOverviewView 5-tab strip,
                           AudioTab, GenerateAudioModal,
                           useGenerateCost, audioJob store
                       │
                       ▼
                  E (Annotations + Sections audio + repo fix) [P with D]
                  E1..E7
                       │
                       ▼
                  F (Settings TTS + spike CLI)
                  F1..F8
                       │
                       ▼
                  G (CLI: listen, listen --generate, maintenance)
                  G1..G3
                       │
                       ▼
                  H (Polish: Media Session, BroadcastChannel, library banner)
                  H1..H5
                       │
                       ▼
                  TN — Final verification
```

**[P]** = D and E are parallelizable after C lands; both depend on the same routes from B but write to non-overlapping frontend code.

---

## Decision Log

> Inherits 36 architecture decisions from the spec. Entries below are implementation-specific decisions made during planning.

| # | Decision | Options Considered | Rationale |
|---|----------|-------------------|-----------|
| P1 | Phase order matches spec §15 (A→B→C→D→E→F→G→H) | (a) spec phasing; (b) UI-first; (c) feature-vertical slices | (a). Backend foundation must land before API; API before frontend; reader before Audio tab. Each phase produces independently testable software. |
| P2 | All TTS backend code lives under `backend/app/services/tts/` (new package) | (a) `services/tts/`; (b) inline in `services/audio.py`; (c) split across `services/` | (a). Mirrors existing `services/summarizer/` package layout (provider ABC, factory, prompt templates). One discoverable surface. |
| P3 | All audio FastAPI routes in `routes/audio.py` (single module); position routes in `routes/audio_position.py` (separate) | (a) single module; (b) split | Position-route lifecycle (per-sentence PUT debounced) differs from generation-route lifecycle (long-running jobs); separation matches existing `processing.py` vs `summary.py` precedent. |
| P4 | Frontend audio composables live in `frontend/src/composables/audio/` subfolder | (a) flat `composables/`; (b) `composables/audio/` | (b). 6+ new composables (`useTtsEngine`, `useAudioApiError`, `useGenerateCost`, etc.) warrant a subfolder; existing `composables/` stays uncluttered. |
| P5 | Pinia stores live at `frontend/src/stores/{ttsPlayer,audioJob}.ts` (flat, matching existing pattern) | (a) flat; (b) `stores/audio/` | (a). Existing pattern: `stores/readerSettings.ts`, `stores/summarizationJob.ts` are flat. Two new stores fit the pattern. |
| P6 | Migration is ONE Alembic revision (not split per table/index) | (a) one revision; (b) one per table | (a). Per spec §10.2 ordering note: all changes wrap in one transaction; partial-application rolls back the whole revision per Alembic semantics. |
| P7 | Kokoro-dependent integration tests pytest-marked `@pytest.mark.kokoro` (opt-in) | (a) opt-in `kokoro` marker; (b) always-run; (c) skip in CI by default | (a). Default `pytest tests/` skips Kokoro tests (heavy: ~80MB model download + ~5s synthesis per test). CI runs `pytest -m "not kokoro"` by default. Power users run `pytest -m kokoro` after first model download. |
| P8 | ffmpeg required at install time for Kokoro engine; no PyPI MP3-encoder fallback (per spec D16) | (a) ffmpeg only; (b) lameenc PyPI fallback | (a). Per spec D16 + recon: matches existing Calibre `ebook-convert` detection pattern; one well-known dep. |
| P9 | Re-use existing `POST /api/v1/jobs/{id}/cancel` for audio cancel; do not introduce `/api/v1/audio/jobs/{id}/cancel` | (a) re-use; (b) audio-specific route | (a). The endpoint dispatches by `step`; audio cancel just calls `provider.terminate()` instead of LLM cancel. One cancel surface for the UI. |
| P10 | Voice picker reads from `voices-v1.0.bin` via a module-level `KOKORO_VOICES` dict, populated once at first KokoroProvider import | (a) module-level cache; (b) per-request scan; (c) hardcoded list | (a). Voices file ships with model; enumerate once via `kokoro_onnx.Kokoro.list_voices()`. Avoids re-reading the voices file per voice-list API call. |
| P11 | Defer Prometheus exposition to v1.x; v1 ships structlog log-lines only (per NFR-12) | (a) log-lines only; (b) Prometheus metrics endpoint | (a). `/metrics` endpoint adds a dep + scrape config; v1 single-user user reads logs. Histograms specified in NFR-12 are noted as the eventual contract. |
| P12 | Unit tests live alongside existing patterns: `backend/tests/unit/services/tts/`, `backend/tests/integration/`, `backend/tests/unit/repositories/` | — | Existing layout per CLAUDE.md. New `tests/unit/services/tts/` subfolder. |
| P13 | All TDD tasks: red first (run test, see failure), then implement, then green | (a) strict TDD; (b) test-after | (a). Per skill protocol; per project standard. Each task explicitly runs failing test before implementation. |

---

## Code Study Notes

Recon (from /spec phase) confirmed the following patterns are reused verbatim:

- **Provider ABC pattern** — `backend/app/services/summarizer/llm_provider.py:20-67` defines `LLMProvider` ABC with `_track_active`/`terminate`. New `TTSProvider` is independent (per spec D21) but uses the same shape (abstract `synthesize`, optional `terminate`, name attribute).
- **Factory pattern** — `services/summarizer/__init__.py:8-27` (`detect_llm_provider`, `create_llm_provider`). New `services/tts/__init__.py` mirrors.
- **Job queue + SSE** — `services/job_queue_worker.py:42-148, 241-417` promotes one job globally; emits events via `EventBus.publish` from `app/api/sse.py:15-55`. Frontend consumes via `frontend/src/composables/useBufferedJobStream.ts:29-121`.
- **Settings YAML** — `services/settings_service.py:55-149` with deep-merge PATCH; CLI reads `Settings()` directly.
- **Sanitizer analog** — `services/export_service.py:44-71`'s `_sanitize_image_urls()` regex pattern is the closest precedent (image URL: `/api/v1/images/{id}`).
- **No-auth blob serving** — `routes/images.py:11-27` and `routes/backup.py:51-64` (`FileResponse`, `Cache-Control: public, max-age=31536000, immutable`). MP3 routes mirror.
- **fastembed download UX** — `cli/commands/init_cmd.py:81-91` prints banner, lets `huggingface_hub` show progress, fail-soft. Kokoro download mirrors.
- **CLI command structure** — `cli/commands/summarize_cmd.py:1-220` (`@async_command`, `async with get_services() as svc:`, explicit `await svc["session"].commit()`). New `listen_cmd.py` mirrors.
- **Tab strip** — `frontend/src/views/BookOverviewView.vue:87-100` has the 3-tab strip. NOT BookDetailView (which is the reader). Spec text now corrected.
- **Re-import preserves section IDs** — CLAUDE.md gotcha #13: `_re_import_book` updates sections in-place by `order_index`. AudioFile rows tied to section_id remain valid unless section count changes.
- **ProcessingJob partial UNIQUE** — `db/models.py:295-331` has the per-book index. Spec replaces with `(book_id, step)` per FR-17 / D18.
- **ContentType enum** — `db/models.py:81-84` has 3 values; spec adds `ANNOTATIONS_PLAYLIST`. SQLite stores as TEXT; CHECK constraint enforces the union.
- **DESIGN.md** — light theme, indigo `#4f46e5` accent only, sticky-bottom playbar shape `bc-playbar`, sentence-active class `bc-sentence-active`, EngineChip atom (kokoro indigo / web-speech neutral), no second blue palette.
- **COMPONENTS.md** — new components flagged: `EngineChip`, `CoverageBar`, `Playbar`, `GenerateAudioModal`, `AnnotationPlaylistRow`. Reader-specific reuse: `ReaderHeader.vue:60` `<slot name="actions">` for TtsPlayButton; `MarkdownRenderer.vue` for sentence-wrap; `ContinueBanner.vue` for resume affordance.

---

## Prerequisites

- Working tree clean on `main` (`git status` empty before starting).
- `backend/` has `uv sync --dev` run successfully.
- `frontend/` has `npm install` run successfully.
- `ffmpeg` on `$PATH` for Kokoro generation (`brew install ffmpeg` on macOS) — required for Phase A onward.
- `~/Library/Application Support/bookcompanion/library.db` exists and migrations applied (`uv run bookcompanion init` once).
- For final verification: at least one book imported with summaries (`uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub` then summarize).
- For Playwright MCP: free port 8765 (per CLAUDE.md `Interactive verification` workflow).

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/app/services/tts/__init__.py` | `detect_tts_provider`, `create_tts_provider` factory |
| Create | `backend/app/services/tts/provider.py` | `TTSProvider` ABC + `SynthesisResult` dataclass |
| Create | `backend/app/services/tts/kokoro_provider.py` | KokoroProvider impl (per-sentence loop + ffmpeg) |
| Create | `backend/app/services/tts/markdown_to_speech.py` | Sanitizer + pysbd segmentation + `SANITIZER_VERSION` |
| Create | `backend/app/services/tts/id3_tagger.py` | ID3v2.3 tagging via mutagen |
| Create | `backend/app/services/audio_gen_service.py` | Orchestrator: sanitize → synthesize → tag → write file → UPSERT |
| Create | `backend/app/api/routes/audio.py` | All audio endpoints (POST /audio, GET /audio, lookup, sample, DELETE) |
| Create | `backend/app/api/routes/audio_position.py` | GET/PUT /audio_position |
| Create | `backend/app/api/routes/spikes.py` | GET /spikes/tts |
| Modify | `backend/app/api/routes/settings.py` | Add /settings/tts, /settings/tts/status |
| Create | `backend/app/db/repositories/audio_file_repo.py` | AudioFile CRUD + UPSERT-with-unlink |
| Create | `backend/app/db/repositories/audio_position_repo.py` | UPSERT + has_other_browser query |
| Modify | `backend/app/db/models.py` | Add AudioFile, AudioPosition, ANNOTATIONS_PLAYLIST, AUDIO step |
| Modify | `backend/app/db/repositories/annotation_repo.py:40-60` | `list_by_book` UNION over book_summary annotations |
| Create | `backend/app/migrations/versions/20260502_audiobook_mode.py` | Alembic revision: tables + index swap |
| Modify | `backend/app/services/job_queue_worker.py` | Dispatch `step=AUDIO` to AudioGenService |
| Modify | `backend/app/api/main.py:47-103` | Lifespan: pre-warm Kokoro + orphan-recovery scan |
| Modify | `backend/app/services/book_service.py` | Re-import audio reconciliation; book-delete cascade |
| Modify | `backend/app/config.py` | Add `TTSConfig` |
| Modify | `backend/app/cli/main.py` | Register `listen`, `spike tts`, `maintenance audio-positions-sweep` commands |
| Create | `backend/app/cli/commands/listen_cmd.py` | `bookcompanion listen [--generate]` |
| Create | `backend/app/cli/commands/spike_cmd.py` | `bookcompanion spike tts` |
| Create | `backend/app/cli/commands/maintenance_cmd.py` | `bookcompanion maintenance audio-positions-sweep` |
| Modify | `backend/app/cli/commands/init_cmd.py` | Add `--tts-engine kokoro` flag + ffmpeg check |
| Create | `frontend/src/stores/ttsPlayer.ts` | Pinia store: player state |
| Create | `frontend/src/stores/audioJob.ts` | Pinia store: audio gen job progress |
| Create | `frontend/src/composables/audio/useTtsEngine.ts` | Engine routing (Web Speech vs Mp3) |
| Create | `frontend/src/composables/audio/useAudioApiError.ts` | Generic API-error → toast mapping |
| Create | `frontend/src/composables/audio/useGenerateCost.ts` | Cost estimator |
| Create | `frontend/src/composables/audio/useEngineCopy.ts` | Engine + reason copy strings |
| Create | `frontend/src/composables/audio/usePlaylistMinutes.ts` | `estimatePlaylistMinutes(highlights, notes)` |
| Modify | `frontend/src/composables/useBufferedJobStream.ts` | Add 5-step subscribe→buffer→fetch→reconcile→live (FR-21a) |
| Create | `frontend/src/components/audio/Playbar.vue` | Sticky-bottom transport |
| Create | `frontend/src/components/audio/EngineChip.vue` | Engine + reason tooltip atom |
| Create | `frontend/src/components/audio/TtsPlayButton.vue` | Slots into ReaderHeader |
| Create | `frontend/src/components/audio/AudioTab.vue` | Audio tab content (4 states) |
| Create | `frontend/src/components/audio/AudioFileRow.vue` | Play / Download / Delete row |
| Create | `frontend/src/components/audio/GenerateAudioModal.vue` | Generate modal (3 states) |
| Create | `frontend/src/components/audio/AnnotationsTab.vue` | Annotations playlist tab |
| Create | `frontend/src/components/audio/AnnotationPlaylistRow.vue` | Annotation card with audio cue |
| Create | `frontend/src/components/audio/StaleSourceBanner.vue` | Banner with 3 stale_reason variants |
| Create | `frontend/src/components/audio/ResumeAffordance.vue` | "Resume from sentence X / Start" |
| Create | `frontend/src/components/settings/SettingsTtsPanel.vue` | TTS settings pane |
| Create | `frontend/src/components/settings/SpikeFindingsBlock.vue` | Reads `/spikes/tts` |
| Create | `frontend/src/components/settings/VoiceSampleButton.vue` | Sample on either engine |
| Create | `frontend/src/components/settings/KokoroStatusIndicator.vue` | warm / cold / not-downloaded / download_failed |
| Create | `frontend/src/components/library/RegenerateStaleAudioBanner.vue` | Library-level banner (FR-66) |
| Modify | `frontend/src/views/BookOverviewView.vue:87-122` | 3 → 5 tabs (add Audio + Annotations) |
| Modify | `frontend/src/router/index.ts` | Add child routes `audio` and `annotations` under `/books/:id` (mirrors existing `overview\|summary\|sections`) |
| Modify | `frontend/src/components/reader/ReaderHeader.vue:60` | TtsPlayButton in `actions` slot |
| Modify | `frontend/src/components/reader/MarkdownRenderer.vue` | Sentence-wrap pass with `data-sentence-index` |
| Modify | `frontend/src/components/reader/ReadingArea.vue:21-23` | Keybinding precedence (audio-active vs section-nav) |
| Modify | `frontend/src/views/SettingsView.vue` | Add TTS pane to settings nav |
| Modify | `frontend/src/views/LibraryView.vue` | Mount RegenerateStaleAudioBanner |
| Test | `backend/tests/unit/services/tts/test_markdown_to_speech.py` | Sanitizer fixtures (anti-pattern table) |
| Test | `backend/tests/unit/services/tts/test_pysbd_segmentation_stable.py` | pysbd version regression |
| Test | `backend/tests/unit/services/tts/test_provider_abc.py` | TTSProvider contract |
| Test | `backend/tests/unit/services/tts/test_kokoro_provider.py` | `@pytest.mark.kokoro` |
| Test | `backend/tests/unit/services/tts/test_kokoro_offsets.py` | `@pytest.mark.kokoro` strict-monotone offsets |
| Test | `backend/tests/unit/services/tts/test_id3_tagger.py` | Tag round-trip via mutagen |
| Test | `backend/tests/unit/repositories/test_audio_file_repo.py` | UPSERT atomicity |
| Test | `backend/tests/unit/repositories/test_audio_position_repo.py` | Debounce + has_other_browser |
| Test | `backend/tests/integration/conftest.py` | Shared fixtures: `FakeTTSProvider` (returns deterministic bytes + offsets, no Kokoro), `seeded_book_with_3_sections`, `running_audio_job`, `running_summarize_job` |
| Test | `backend/tests/integration/test_audio_job_e2e.py` | End-to-end job (FakeTTSProvider) |
| Test | `backend/tests/integration/test_audio_concurrency.py` | 409 self-heal + per-book/step coexistence |
| Test | `backend/tests/integration/test_audio_migration.py` | Migration round-trip |
| Test | `backend/tests/integration/test_annotation_playlist.py` | book_summary annotations included |
| Test | `backend/tests/integration/test_audio_lookup_stale.py` | source_hash + sanitizer_version + sentence_count gating |
| Test | `backend/tests/integration/test_sse_audio_events.py` | Producer/consumer event-name contract |
| Test | `backend/tests/integration/test_settings_tts.py` | settings.yaml round-trip + voice validation |
| Test | `backend/tests/e2e/test_listen_cli.py` | CLI smoke |
| Test | `frontend/src/components/audio/__tests__/Playbar.spec.ts` | Vitest unit |
| Test | `frontend/e2e/audiobook-generate.spec.ts` | Playwright J2 |
| Test | `frontend/e2e/audiobook-reader-play.spec.ts` | Playwright J1 |
| Test | `frontend/e2e/audiobook-annotations.spec.ts` | Playwright J3 |
| Test | `frontend/e2e/audiobook-settings.spec.ts` | Playwright settings |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `kokoro-onnx` PyPI install fails on macOS ARM64 (e.g., onnxruntime wheel mismatch) | Low | Pin exact version (`kokoro-onnx==0.5.0`); document `onnxruntime-silicon` fallback in README. Spike runs first to validate (per spec OQ-1). |
| ffmpeg not on user's PATH; user confused about install | Medium | `bookcompanion init` checks; clear error with `brew install ffmpeg`; spec FR-51. |
| Kokoro model download (80 MB) fails behind corporate proxy | Low | Per FR-05 post-sim: `KokoroModelDownloadError` surfaces in Settings TTS as actionable Retry button with proxy hint. |
| pysbd version drift between dev and CI breaks sentence offsets | Medium | Pin exact version; regression test against fixed corpus per FR-12b. |
| Long audio jobs (20+ min) block summarize on the global single-RUNNING worker | Accepted (D19) | Documented; revisit in v1.x if user reports blocking pain. |
| Web Speech voices missing on Linux Firefox | Medium | E2/E11 surfaces inline banner with one-click switch to Kokoro. |
| iOS Safari `speechSynthesis` stops on screen-lock; user loses Web Speech playback | Accepted (D26/E13) | "Limited controls" disclaimer in Player chrome explains the path to Kokoro pre-gen. |
| AudioFile size cap (NFR-13) too strict for some books | Low | 100 MB cap rare; UI surfaces "(too long for one audio file — split into sections)". |
| Frontend bundle size grows past Vite's default 500KB warning with sentence-wrap + Pinia stores | Low | Code-split audio chunk via dynamic import on first play; bundle check in TN. |

---

## Rollback

- **Migration fails:** `cd backend && uv run alembic -c app/migrations/alembic.ini downgrade -1` recreates the old `(book_id)` partial UNIQUE index and drops `audio_files`, `audio_positions`. MP3 files on disk become orphans — `rm -rf "$HOME/Library/Application Support/bookcompanion/audio/"` to clean.
- **Settings.yaml schema breaks Settings() parse:** delete the `tts:` section from `~/.config/bookcompanion/settings.yaml`; defaults (`extra="ignore"`) per NFR-11 keep server bootable.
- **Frontend deploy regresses reader:** revert `frontend/src/components/reader/{ReaderHeader,ReadingArea,MarkdownRenderer}.vue` to prior commit; rebuild + recopy to `backend/app/static/` per CLAUDE.md interactive verification workflow.
- **Worker crashes on ProcessingStep.AUDIO unknown value (mid-deploy old worker hits new job row):** old worker rejects unknown step → job stuck PENDING → new worker on next deploy promotes it. Documented as accepted pre-deploy ordering risk.
- **Kokoro install pollutes Python env:** `cd backend && uv sync --dev` re-resolves; remove `~/Library/Application Support/bookcompanion/models/tts/` to force re-download.

---

## Tasks

### Phase A — Backend foundation (A1–A17)

#### A1: Add `TTSConfig` to `app/config.py`

**Goal:** Settings model accepts TTS preferences from `~/.config/bookcompanion/settings.yaml` with safe defaults.
**Spec refs:** FR-42, NFR-11, D7

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/unit/test_config.py`

**Steps:**

- [ ] Step 1: Write failing test in `tests/unit/test_config.py`
  ```python
  def test_tts_config_defaults():
      settings = Settings()
      assert settings.tts.engine == "web-speech"
      assert settings.tts.voice == ""
      assert settings.tts.default_speed == 1.0
      assert settings.tts.auto_advance is True
      assert settings.tts.prewarm_on_startup is True
      assert settings.tts.annotation_context == "span"

  def test_tts_config_env_override(monkeypatch):
      monkeypatch.setenv("BOOKCOMPANION_TTS__ENGINE", "kokoro")
      monkeypatch.setenv("BOOKCOMPANION_TTS__VOICE", "af_sarah")
      settings = Settings()
      assert settings.tts.engine == "kokoro"
      assert settings.tts.voice == "af_sarah"

  def test_tts_config_invalid_engine_rejected():
      with pytest.raises(ValidationError):
          TTSConfig(engine="bogus")
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/test_config.py::test_tts_config_defaults -v` → expect FAIL (`AttributeError: 'Settings' object has no attribute 'tts'`).
- [ ] Step 3: Add `TTSConfig` to `app/config.py` with fields `engine: Literal["web-speech","kokoro"]`, `voice: str`, `default_speed: float = Field(1.0, ge=0.5, le=2.0)`, `auto_advance: bool`, `prewarm_on_startup: bool`, `annotation_context: Literal["span"]`. Mount on `Settings.tts: TTSConfig = Field(default_factory=TTSConfig)`.
- [ ] Step 4: `cd backend && uv run pytest tests/unit/test_config.py -k "tts" -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/config.py backend/tests/unit/test_config.py
  git commit -m "feat(tts): add TTSConfig to settings"
  ```

**Inline verification:**
- `cd backend && uv run ruff check app/config.py` — 0 errors
- `cd backend && uv run pytest tests/unit/test_config.py -v` — N+3 passed

---

#### A2: Extend `ContentType` and `ProcessingStep` enums

**Goal:** `ContentType.ANNOTATIONS_PLAYLIST` and `ProcessingStep.AUDIO` are accepted enum values.
**Spec refs:** D22, FR-16, FR-52

**Files:**
- Modify: `backend/app/db/models.py:48-56,81-84`
- Test: `backend/tests/unit/test_models.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_content_type_annotations_playlist():
      assert ContentType.ANNOTATIONS_PLAYLIST.value == "annotations_playlist"

  def test_processing_step_audio():
      assert ProcessingStep.AUDIO.value == "audio"
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/test_models.py -k "annotations_playlist or step_audio" -v` → expect FAIL.
- [ ] Step 3: Add `ANNOTATIONS_PLAYLIST = "annotations_playlist"` to `ContentType`; add `AUDIO = "audio"` to `ProcessingStep`.
- [ ] Step 4: `cd backend && uv run pytest tests/unit/test_models.py -k "annotations_playlist or step_audio" -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/db/models.py backend/tests/unit/test_models.py
  git commit -m "feat(tts): add ANNOTATIONS_PLAYLIST + AUDIO enum values"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/test_models.py -v` — all passed

---

#### A3: Alembic migration — `audio_files`, `audio_positions`, processing_jobs index swap

**Goal:** New tables exist; partial UNIQUE index is `(book_id, step)`; downgrade restores prior state.
**Spec refs:** FR-17, §10.1, §10.2, D18

**Files:**
- Create: `backend/app/migrations/versions/20260502_audiobook_mode.py`
- Test: `backend/tests/integration/test_audio_migration.py`

**Steps:**

- [ ] Step 1: Write failing test in `tests/integration/test_audio_migration.py`
  ```python
  import sqlalchemy as sa
  from app.db.models import ProcessingJob, ProcessingStep, JobStatus

  def test_audio_files_table_exists(migrated_db):
      tables = sa.inspect(migrated_db.bind).get_table_names()
      assert "audio_files" in tables
      assert "audio_positions" in tables

  def test_audio_files_unique_unit_index(migrated_db):
      indexes = sa.inspect(migrated_db.bind).get_indexes("audio_files")
      ux = next(i for i in indexes if i["name"] == "ux_audio_files_unit")
      assert ux["unique"] is True
      assert ux["column_names"] == ["book_id", "content_type", "content_id", "voice"]

  def test_processing_jobs_index_swap(migrated_db):
      indexes = sa.inspect(migrated_db.bind).get_indexes("processing_jobs")
      names = {i["name"] for i in indexes}
      assert "ix_processing_jobs_one_active_per_book_step" in names
      assert "ix_processing_jobs_one_active_per_book" not in names

  async def test_concurrent_audio_and_summarize_per_book(seeded_db):
      # Insert RUNNING summarize on book 1
      seeded_db.add(ProcessingJob(book_id=1, step=ProcessingStep.SUMMARIZE, status=JobStatus.RUNNING))
      # Insert RUNNING audio on same book — must succeed under new index
      seeded_db.add(ProcessingJob(book_id=1, step=ProcessingStep.AUDIO, status=JobStatus.RUNNING))
      await seeded_db.commit()
      assert (await seeded_db.scalar(sa.select(sa.func.count(ProcessingJob.id)))) == 2

  async def test_duplicate_same_step_same_book_rejected(seeded_db):
      seeded_db.add(ProcessingJob(book_id=1, step=ProcessingStep.AUDIO, status=JobStatus.RUNNING))
      await seeded_db.commit()
      with pytest.raises(sa.exc.IntegrityError):
          seeded_db.add(ProcessingJob(book_id=1, step=ProcessingStep.AUDIO, status=JobStatus.PENDING))
          await seeded_db.commit()

  def test_downgrade_restores_old_index(migrated_db):
      # Run downgrade
      run_alembic("downgrade -1")
      indexes = sa.inspect(migrated_db.bind).get_indexes("processing_jobs")
      names = {i["name"] for i in indexes}
      assert "ix_processing_jobs_one_active_per_book" in names
      assert "ix_processing_jobs_one_active_per_book_step" not in names
      tables = sa.inspect(migrated_db.bind).get_table_names()
      assert "audio_files" not in tables
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_migration.py -v` → expect FAIL (no migration yet).
- [ ] Step 3: Generate revision: `cd backend && uv run alembic -c app/migrations/alembic.ini revision -m "audiobook_mode"`. Edit the generated file to:
  - `op.create_table("audio_files", ...)` with columns per spec §10.1 (id, book_id, content_type, content_id, voice, engine, file_path, file_size_bytes, duration_seconds, sentence_count, sentence_offsets_json, source_hash, sanitizer_version, job_id, generated_at) + CHECK on content_type + UNIQUE(book_id, content_type, content_id, voice) + index on book_id.
  - `op.create_table("audio_positions", ...)` with PK (content_type, content_id, browser_id) + index on (content_type, content_id) + CHECK on content_type.
  - `op.batch_alter_table("processing_jobs") as batch:` drop `ix_processing_jobs_one_active_per_book`, create `ix_processing_jobs_one_active_per_book_step` partial UNIQUE on `(book_id, step)` `WHERE status IN ('PENDING','RUNNING')` via `batch.create_index(..., postgresql_where=...)` (SQLite respects via `sqlite_where`).
  - `downgrade()`: reverse order — drop new tables then restore old index.
- [ ] Step 4: `cd backend && uv run alembic -c app/migrations/alembic.ini upgrade head` then `uv run pytest tests/integration/test_audio_migration.py -v` → expect 6 passed.
- [ ] Step 5: Round-trip: `uv run alembic downgrade -1 && uv run alembic upgrade head` → no errors.
- [ ] Step 6: Commit
  ```bash
  git add backend/app/migrations/versions/20260502_audiobook_mode.py backend/tests/integration/test_audio_migration.py
  git commit -m "feat(tts): alembic migration for audio_files + audio_positions + index swap"
  ```

**Inline verification:**
- `cd backend && uv run alembic -c app/migrations/alembic.ini history` — new revision listed at head
- Migration round-trip: `uv run alembic downgrade -1 && uv run alembic upgrade head` — exits 0

---

#### A4: SQLAlchemy models — `AudioFile`, `AudioPosition`

**Goal:** ORM mappings exposing the new tables for repositories and services.
**Spec refs:** §10.1, FR-22

**Files:**
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/unit/test_models.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_audio_file_persist_round_trip(session):
      af = AudioFile(book_id=1, content_type=ContentType.SECTION_SUMMARY, content_id=42,
                     voice="af_sarah", engine="kokoro", file_path="audio/1/section_summary_42__af_sarah.mp3",
                     file_size_bytes=4_410_000, duration_seconds=367.4, sentence_count=47,
                     sentence_offsets_json="[0.0, 4.2]", source_hash="ab3c", sanitizer_version="1.0")
      session.add(af); await session.commit()
      loaded = await session.get(AudioFile, af.id)
      assert loaded.duration_seconds == 367.4 and loaded.sentence_count == 47

  async def test_audio_position_pk_composite(session):
      pos = AudioPosition(content_type=ContentType.SECTION_SUMMARY, content_id=42,
                          browser_id="abc-uuid", sentence_index=16)
      session.add(pos); await session.commit()
      loaded = await session.get(AudioPosition, (ContentType.SECTION_SUMMARY, 42, "abc-uuid"))
      assert loaded.sentence_index == 16
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/test_models.py -k "audio_file or audio_position" -v` → expect FAIL (model classes don't exist).
- [ ] Step 3: Add `AudioFile` and `AudioPosition` mapped classes in `db/models.py`. AudioFile: `Integer` PK, FK book_id with `ondelete="CASCADE"`, FK job_id with `ondelete="SET NULL"`, all columns from §10.1. AudioPosition: composite PK `(content_type, content_id, browser_id)`, no FKs (polymorphic).
- [ ] Step 4: `cd backend && uv run pytest tests/unit/test_models.py -k "audio_file or audio_position" -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/db/models.py backend/tests/unit/test_models.py
  git commit -m "feat(tts): AudioFile and AudioPosition ORM models"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/test_models.py -v` — all green

---

#### A5: `AudioFileRepository`

**Goal:** UPSERT-with-unlink for atomic regeneration; query helpers for inventory + lookup.
**Spec refs:** FR-22, FR-23, FR-24, FR-26

**Files:**
- Create: `backend/app/db/repositories/audio_file_repo.py`
- Test: `backend/tests/unit/repositories/test_audio_file_repo.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_upsert_creates_row_and_writes_file(repo, tmp_data_dir):
      af = await repo.upsert(book_id=1, content_type=ContentType.SECTION_SUMMARY,
          content_id=42, voice="af_sarah", engine="kokoro", mp3_bytes=b"ID3...",
          duration_seconds=10.0, sentence_count=3, sentence_offsets=[0.0, 3.0, 6.5],
          source_hash="abc", sanitizer_version="1.0", job_id=99)
      assert (tmp_data_dir / af.file_path).read_bytes().startswith(b"ID3")

  async def test_upsert_replaces_old_file(repo, tmp_data_dir):
      af1 = await repo.upsert(book_id=1, content_type=ContentType.SECTION_SUMMARY,
          content_id=42, voice="af_sarah", mp3_bytes=b"OLD", **base_kwargs)
      old_path = tmp_data_dir / af1.file_path
      af2 = await repo.upsert(book_id=1, content_type=ContentType.SECTION_SUMMARY,
          content_id=42, voice="af_sarah", mp3_bytes=b"NEW", **base_kwargs)
      assert af2.id == af1.id  # row replaced, not duplicated
      assert (tmp_data_dir / af2.file_path).read_bytes() == b"NEW"
      # If filename pattern is identical (same voice), old is overwritten — no orphan

  async def test_list_by_book_returns_inventory(repo):
      ...
      rows = await repo.list_by_book(book_id=1)
      assert len(rows) == 3 and all(r.book_id == 1 for r in rows)

  async def test_delete_all_for_book_unlinks_files(repo, tmp_data_dir):
      af = await repo.upsert(...)
      path = tmp_data_dir / af.file_path
      assert path.exists()
      deleted = await repo.delete_all_for_book(book_id=1)
      assert deleted == 1 and not path.exists()

  async def test_delete_one_unlinks_single_file(repo, tmp_data_dir):
      ...
      await repo.delete_one(book_id=1, content_type=ContentType.SECTION_SUMMARY, content_id=42)
      assert not (tmp_data_dir / af.file_path).exists()
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/repositories/test_audio_file_repo.py -v` → expect FAIL.
- [ ] Step 3: Implement repo with `upsert`, `list_by_book`, `lookup(book_id, content_type, content_id, voice)`, `delete_all_for_book`, `delete_one`. UPSERT writes to `*.tmp`, fsync, rename to final path, then `INSERT ... ON CONFLICT DO UPDATE` with the existing row's prior `file_path` captured for cleanup; if old path != new path, unlink old after row update.
- [ ] Step 4: `cd backend && uv run pytest tests/unit/repositories/test_audio_file_repo.py -v` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/db/repositories/audio_file_repo.py backend/tests/unit/repositories/test_audio_file_repo.py
  git commit -m "feat(tts): AudioFileRepository with atomic UPSERT-with-unlink"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/repositories/test_audio_file_repo.py -v` — 5 passed

---

#### A6: `AudioPositionRepository`

**Goal:** UPSERT debounced server-side; `has_other_browser` hint on read.
**Spec refs:** FR-37, FR-38, FR-39, FR-41

**Files:**
- Create: `backend/app/db/repositories/audio_position_repo.py`
- Test: `backend/tests/unit/repositories/test_audio_position_repo.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_upsert_inserts_then_updates(repo):
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 5)
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 10)
      pos = await repo.get(ContentType.SECTION_SUMMARY, 42, "browser-A")
      assert pos.sentence_index == 10  # latest write wins

  async def test_get_returns_has_other_browser_hint(repo):
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 10)
      await asyncio.sleep(0.01)
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-B", 25)
      result = await repo.get_with_hint(ContentType.SECTION_SUMMARY, 42, "browser-A")
      assert result.sentence_index == 10
      assert result.has_other_browser is True
      assert result.other_browser_updated_at > result.updated_at

  async def test_debounce_drops_writes_within_window(repo):
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 5)  # T=0
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 6)  # T=10ms — dropped
      await asyncio.sleep(0.6)
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-A", 7)  # T=600ms — accepted
      pos = await repo.get(ContentType.SECTION_SUMMARY, 42, "browser-A")
      assert pos.sentence_index == 7  # writes between 5 and 7 in <500ms collapsed

  async def test_cleanup_for_book(repo):
      await repo.upsert(ContentType.SECTION_SUMMARY, 42, "b", 1)  # section in book 1
      await repo.cleanup_for_book(book_id=1)  # FR-26b
      assert await repo.get(ContentType.SECTION_SUMMARY, 42, "b") is None
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/repositories/test_audio_position_repo.py -v` → expect FAIL.
- [ ] Step 3: Implement repo with `upsert` (in-memory rate-limit per (content_type, content_id, browser_id) at 500ms via a dict of last-write timestamps), `get`, `get_with_hint` (returns named-tuple with has_other_browser + other_browser_updated_at via second SELECT MAX(updated_at) WHERE same (ct, ci) AND browser_id != :bid), `cleanup_for_book` (DELETE per spec FR-26b cascade SQL).
- [ ] Step 4: `cd backend && uv run pytest tests/unit/repositories/test_audio_position_repo.py -v` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/db/repositories/audio_position_repo.py backend/tests/unit/repositories/test_audio_position_repo.py
  git commit -m "feat(tts): AudioPositionRepository with debounce + cross-browser hint"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/repositories/test_audio_position_repo.py -v` — 4 passed

---

#### A7: `MarkdownToSpeech` sanitizer

**Goal:** Anti-pattern passes (footnotes, code, image, links, math, abbrev) produce speech-clean text. Empty sanitizer raises `EmptySanitizedTextError`.
**Spec refs:** FR-08, FR-09a–f, FR-11, NFR-04, NFR-05

**Files:**
- Create: `backend/app/services/tts/markdown_to_speech.py`
- Create: `backend/tests/fixtures/tts/sanitizer_cases.json`
- Test: `backend/tests/unit/services/tts/test_markdown_to_speech.py`

**Steps:**

- [ ] Step 1: Write failing test (parametrized fixture-driven)
  ```python
  CASES = [
      ("Smith argued[3] that...", ["Smith argued that"], ["[3]", "3"]),
      ("```python\nx=1\n```", ["code block, 1 lines, skipped"], ["python", "x=1"]),
      ("![diagram](/api/v1/images/42)", ["figure: diagram"], ["/api/v1/images", "42"]),
      ("![](/api/v1/images/9)", [], ["/api/v1/images"]),  # no alt → omit
      ("e.g. apples, i.e. fruit, etc.", ["for example", "that is", "et cetera"], ["e.g.", "i.e.", "etc."]),
      ("Mass is $E=mc^2$ here.", ["equation, omitted"], ["E=mc^2"]),
      ("Equation \\[F=ma\\] block", ["equation, omitted"], ["F=ma"]),
      ("Dr. Smith met Mr. Jones on St. Pauls Rd.", ["Doctor", "Mister", "Saint"], ["Dr.", "Mr.", "St."]),
      ("See https://example.com here", [], ["https://", "example.com"]),
      ("[link text](https://example.com)", ["link text"], ["https://", "example.com"]),
  ]

  @pytest.mark.parametrize("md, expected_in, forbidden", CASES)
  def test_sanitizer_anti_patterns(md, expected_in, forbidden):
      result = sanitize(md)
      for s in expected_in: assert s in result.text
      for s in forbidden: assert s not in result.text

  def test_empty_sanitized_raises():
      with pytest.raises(EmptySanitizedTextError):
          sanitize("```\nonly code\n```\n\n![](/api/v1/images/1)")  # all stripped

  def test_whitespace_only_raises():
      with pytest.raises(EmptySanitizedTextError):
          sanitize("   \n\n   ")

  def test_sanitizer_perf_under_50ms():
      large = "Body text. " * 500  # ~5000 chars
      t0 = time.perf_counter()
      sanitize(large)
      assert (time.perf_counter() - t0) < 0.050
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/services/tts/test_markdown_to_speech.py -v` → expect FAIL.
- [ ] Step 3: Implement `sanitize(md: str) -> SanitizedText` in `markdown_to_speech.py`:
  - Use `markdown_it.MarkdownIt()` to tokenize.
  - Walk tokens; skip `fence` / `code_block` (replace with `"code block, N lines, skipped."`); strip `code_inline`.
  - Handle `image` token with alt → `"figure: alt"`, no alt → omit.
  - Handle `link` open/close: keep inner text, drop URL.
  - Regex pre-pass on raw markdown: strip `\[\d+\]`, `\^\d+` footnote markers; strip bare URLs `https?://\S+`; replace math `$...$`, `\[...\]`, `\(...\)` with `"equation, omitted."`.
  - Abbreviation expansion via static dict on word-boundary.
  - Collapse whitespace, strip.
  - If `len(stripped) == 0`, raise `EmptySanitizedTextError`.
  - Return `SanitizedText(text=str, source_md=str)` (offsets added in A8).
- [ ] Step 4: `cd backend && uv run pytest tests/unit/services/tts/test_markdown_to_speech.py -v` → expect 13 passed (10 cases + empty + whitespace + perf).
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/tts/markdown_to_speech.py backend/tests/unit/services/tts/test_markdown_to_speech.py backend/tests/fixtures/tts/sanitizer_cases.json
  git commit -m "feat(tts): markdown-to-speech sanitizer with anti-pattern fixtures"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/test_markdown_to_speech.py -v` — 13 passed
- `cd backend && uv run ruff check app/services/tts/markdown_to_speech.py` — 0 errors

---

#### A8: pysbd integration + `SANITIZER_VERSION` constant + `sentence_offsets_chars`

**Goal:** `sanitize()` returns `SanitizedText(text, sentence_offsets_chars, sanitizer_version)`. Sentences segmented per FR-10/D17; abbreviations don't split; module-level `SANITIZER_VERSION = "1.0"`.
**Spec refs:** FR-10, FR-12a, FR-12b, D17

**Files:**
- Modify: `backend/app/services/tts/markdown_to_speech.py`
- Modify: `backend/pyproject.toml` (pin `pysbd==0.3.4`)
- Test: extends `test_markdown_to_speech.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_sentence_offsets_present():
      result = sanitize("First sentence. Second sentence. Third one.")
      assert len(result.sentence_offsets_chars) == 3
      assert result.sentence_offsets_chars[0] == 0
      # Each offset points INTO result.text at sentence start
      for off in result.sentence_offsets_chars:
          assert 0 <= off < len(result.text)

  def test_sentence_offsets_after_abbreviation_expansion():
      # "e.g." expands to "for example" — offsets must be against post-expansion text
      result = sanitize("Apples e.g. Granny. Bananas next.")
      assert len(result.sentence_offsets_chars) == 2  # NOT 3 (abbrev shouldn't split)
      # Verify "for example" appears in text and offsets point into it
      assert "for example" in result.text

  def test_abbreviation_does_not_split_sentence():
      result = sanitize("Mr. Smith arrived. He left.")
      assert len(result.sentence_offsets_chars) == 2  # not 3

  def test_sanitizer_version_constant():
      from app.services.tts.markdown_to_speech import SANITIZER_VERSION
      assert SANITIZER_VERSION == "1.0"

  def test_zero_sentences_raises_empty():
      with pytest.raises(EmptySanitizedTextError):
          sanitize("```py\n```")  # only code → 0 sentences
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/services/tts/test_markdown_to_speech.py -v` → expect FAIL on new tests.
- [ ] Step 3: Add `pysbd==0.3.4` to `pyproject.toml`; `uv sync`. Add module-level `SANITIZER_VERSION = "1.0"`. Modify `sanitize()` to call `pysbd.Segmenter(language="en", clean=False)` AFTER abbreviation expansion + URL strip + math replace; record char-offset of each segmented sentence's start in the post-sanitized text. Return `SanitizedText(text, sentence_offsets_chars, sanitizer_version=SANITIZER_VERSION)`.
- [ ] Step 4: `cd backend && uv run pytest tests/unit/services/tts/test_markdown_to_speech.py -v` → expect all green.
- [ ] Step 5: Commit
  ```bash
  git add backend/pyproject.toml backend/uv.lock backend/app/services/tts/markdown_to_speech.py backend/tests/unit/services/tts/test_markdown_to_speech.py
  git commit -m "feat(tts): pysbd segmentation + SANITIZER_VERSION + sentence_offsets_chars"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/test_markdown_to_speech.py -v` — all green

---

#### A9: pysbd segmentation regression test (corpus-locked)

**Goal:** Future pysbd version bumps fail loudly via a corpus regression test.
**Spec refs:** FR-12b

**Files:**
- Create: `backend/tests/fixtures/tts/segmentation_corpus.txt`
- Create: `backend/tests/fixtures/tts/segmentation_expected.json`
- Test: `backend/tests/unit/services/tts/test_pysbd_segmentation_stable.py`

**Steps:**

- [ ] Step 1: Author corpus — 20 sentences in `segmentation_corpus.txt` covering: simple periods, abbreviations (Dr., Mr.), decimals (3.14), brackets `[1]`, ellipsis (…), questions, exclamations, semicolons, em-dashes. Each sentence on a paragraph; mix one and two newlines.
- [ ] Step 2: Run pysbd 0.3.4 once via `python -c "import pysbd, json; ..."` to capture expected list; commit to `segmentation_expected.json`.
- [ ] Step 3: Write test
  ```python
  def test_pysbd_corpus_stable():
      corpus = (FIXTURES / "segmentation_corpus.txt").read_text()
      expected = json.loads((FIXTURES / "segmentation_expected.json").read_text())
      seg = pysbd.Segmenter(language="en", clean=False)
      result = seg.segment(corpus)
      assert result == expected, f"pysbd output drift detected. Update corpus or pin version."
  ```
- [ ] Step 4: `cd backend && uv run pytest tests/unit/services/tts/test_pysbd_segmentation_stable.py -v` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/tests/fixtures/tts/segmentation_*.{txt,json} backend/tests/unit/services/tts/test_pysbd_segmentation_stable.py
  git commit -m "test(tts): pysbd corpus regression guard"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/test_pysbd_segmentation_stable.py -v` — 1 passed

---

#### A10: `TTSProvider` ABC + `SynthesisResult` dataclass

**Goal:** Abstract interface; subclasses agree on shape.
**Spec refs:** FR-01, D21

**Files:**
- Create: `backend/app/services/tts/provider.py`
- Test: `backend/tests/unit/services/tts/test_provider_abc.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_synthesis_result_shape():
      r = SynthesisResult(audio_bytes=b"ID3", sample_rate=24000, sentence_offsets=[0.0, 4.2])
      assert r.audio_bytes == b"ID3" and r.sample_rate == 24000 and r.sentence_offsets == [0.0, 4.2]

  def test_provider_abc_cannot_instantiate():
      with pytest.raises(TypeError):
          TTSProvider()  # abstract

  class FakeProvider(TTSProvider):
      name = "fake"
      def synthesize(self, text, voice, speed=1.0):
          return SynthesisResult(b"FAKE", 24000, [0.0])
      def list_voices(self):
          return [VoiceInfo(name="fake_v1", language="en")]

  def test_concrete_subclass_works():
      p = FakeProvider()
      assert p.name == "fake"
      assert p.synthesize("hi", "fake_v1").audio_bytes == b"FAKE"
      assert p.list_voices()[0].name == "fake_v1"
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/services/tts/test_provider_abc.py -v` → expect FAIL.
- [ ] Step 3: In `provider.py`: `@dataclass SynthesisResult(audio_bytes: bytes, sample_rate: int, sentence_offsets: list[float])`; `@dataclass VoiceInfo(name: str, language: str, gender: str | None = None)`; `class TTSProvider(ABC)` with `name: ClassVar[str]`, abstract `synthesize`, abstract `list_voices`, optional `terminate(self)` no-op default. Define `KokoroModelDownloadError`, `EmptySanitizedTextError`, `FfmpegEncodeError` exceptions in same module.
- [ ] Step 4: `cd backend && uv run pytest tests/unit/services/tts/test_provider_abc.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/tts/provider.py backend/tests/unit/services/tts/test_provider_abc.py
  git commit -m "feat(tts): TTSProvider ABC + SynthesisResult + exception types"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/test_provider_abc.py -v` — 3 passed

---

#### A11: `KokoroProvider` — per-sentence loop + ffmpeg

**Goal:** Concrete provider that synthesizes per sentence, concatenates buffers, encodes to MP3 via ffmpeg, returns offsets.
**Spec refs:** FR-03, D15, D16

**Files:**
- Create: `backend/app/services/tts/kokoro_provider.py`
- Test: `backend/tests/unit/services/tts/test_kokoro_provider.py` (`@pytest.mark.kokoro`)
- Test: `backend/tests/unit/services/tts/test_kokoro_offsets.py` (`@pytest.mark.kokoro`)

**Steps:**

- [ ] Step 1: Add `kokoro-onnx==0.5.0` and `soundfile` to `pyproject.toml`; `uv sync`.
- [ ] Step 2: Add `kokoro` marker to `pyproject.toml` `[tool.pytest.ini_options]` markers + filter `addopts = "-m 'not kokoro'"`.
- [ ] Step 3: Write failing test (offsets test gates the implementation):
  ```python
  @pytest.mark.kokoro
  def test_kokoro_synthesize_returns_mp3_bytes():
      p = KokoroProvider(model_dir=DATA_DIR / "models" / "tts")
      r = p.synthesize("Hello world.", voice="af_sarah")
      assert r.audio_bytes[:3] == b"ID3" or r.audio_bytes[:2] == b"\xff\xfb"  # MP3 frame
      assert r.sample_rate == 24000
      assert len(r.sentence_offsets) == 1 and r.sentence_offsets[0] == 0.0

  @pytest.mark.kokoro
  def test_kokoro_offsets_strict_monotone():
      sentences = "First. Second. Third. Fourth. Fifth."
      p = KokoroProvider(model_dir=DATA_DIR / "models" / "tts")
      r = p.synthesize(sentences, voice="af_sarah")
      assert len(r.sentence_offsets) == 5
      assert r.sentence_offsets[0] == 0.0
      for i in range(1, 5):
          assert r.sentence_offsets[i] > r.sentence_offsets[i-1]  # strict-monotone
      total = mutagen.File(io.BytesIO(r.audio_bytes)).info.length
      assert r.sentence_offsets[-1] < total

  @pytest.mark.kokoro
  def test_kokoro_ffmpeg_missing_raises():
      with mock.patch("shutil.which", return_value=None):
          with pytest.raises(FfmpegEncodeError):
              KokoroProvider(...).synthesize("hi", voice="af_sarah")
  ```
- [ ] Step 4: `cd backend && uv run pytest tests/unit/services/tts/test_kokoro_provider.py tests/unit/services/tts/test_kokoro_offsets.py -m kokoro -v` → expect FAIL.
- [ ] Step 5: Implement KokoroProvider per FR-03:
  - Constructor takes `model_dir: Path`; lazy-loads `Kokoro(str(model_dir / "kokoro-v1.0.onnx"), str(model_dir / "voices-v1.0.bin"))` on first call.
  - `synthesize(text, voice, speed=1.0)`: calls `markdown_to_speech.sanitize` to segment (or accepts pre-sanitized via overload? — keep simple: synthesize accepts already-segmented sentences via `synthesize_segmented(sentences: list[str], voice, speed)`. Plain `synthesize(text, voice)` re-uses segmentation for tests).
  - Per-sentence: `pcm, sr = self._kokoro.create(sentence, voice=voice, speed=speed)` (returns float32 numpy + sr=24000); buffers.append(pcm); cumulative_offsets compute.
  - Concatenate via `numpy.concatenate(buffers)`.
  - `_run_ffmpeg(pcm_joined, sample_rate=24000)`: spawn `subprocess.Popen(["ffmpeg", "-f", "f32le", "-ar", "24000", "-ac", "1", "-i", "-", "-codec:a", "libmp3lame", "-b:a", "96k", "-f", "mp3", "-"], stdin=PIPE, stdout=PIPE, stderr=PIPE)`; `proc.communicate(input=pcm.tobytes())`; check returncode; on non-zero or BrokenPipeError raise `FfmpegEncodeError(stderr_tail=stderr[-2048:].decode("utf-8", errors="replace"))`.
  - On `HfHubHTTPError`/`ConnectionError`/`OSError` from initial model load: raise `KokoroModelDownloadError(retry_after_seconds=None)`.
  - `terminate()`: sets a flag the synthesize loop checks; kills any active ffmpeg subprocess.
  - `name = "kokoro"` ClassVar.
- [ ] Step 6: `cd backend && uv run pytest tests/unit/services/tts/test_kokoro_provider.py tests/unit/services/tts/test_kokoro_offsets.py -m kokoro -v` → expect 4 passed (after one-time model download).
- [ ] Step 7: Commit
  ```bash
  git add backend/app/services/tts/kokoro_provider.py backend/tests/unit/services/tts/test_kokoro_*.py backend/pyproject.toml backend/uv.lock
  git commit -m "feat(tts): KokoroProvider per-sentence loop + ffmpeg encode"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/ -m kokoro -v` — 4 passed (manual run)
- `cd backend && uv run pytest tests/unit/services/tts/ -v` (default, `not kokoro`) — Kokoro tests deselected, others pass

---

#### A12: Kokoro model download path (`huggingface_hub`)

**Goal:** First synthesize call downloads `kokoro-v1.0.onnx` + `voices-v1.0.bin` via `hf_hub_download`. Failures map to `KokoroModelDownloadError`.
**Spec refs:** FR-05, D31

**Files:**
- Modify: `backend/app/services/tts/kokoro_provider.py`
- Test: `backend/tests/unit/services/tts/test_kokoro_download.py`

**Steps:**

- [ ] Step 1: Write failing test (mocked HF, no `kokoro` marker)
  ```python
  def test_download_succeeds(monkeypatch, tmp_data_dir):
      called = {"onnx": False, "voices": False}
      def fake_dl(repo_id, filename, cache_dir=None, **kw):
          called[filename.split("-")[0]] = True
          (Path(cache_dir) / filename).write_bytes(b"FAKE")
          return str(Path(cache_dir) / filename)
      monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_dl)
      KokoroProvider._ensure_model_downloaded(tmp_data_dir / "models" / "tts")
      assert called["onnx"] is True

  def test_download_http_error_raises_kokoro_model_download_error(monkeypatch, tmp_data_dir):
      from huggingface_hub.errors import HfHubHTTPError
      def fake_dl(*a, **kw): raise HfHubHTTPError("502")
      monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_dl)
      with pytest.raises(KokoroModelDownloadError):
          KokoroProvider._ensure_model_downloaded(tmp_data_dir / "models" / "tts")
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/services/tts/test_kokoro_download.py -v` → expect FAIL.
- [ ] Step 3: Add `_ensure_model_downloaded(model_dir: Path)` static method to KokoroProvider: if files missing, print banner, call `hf_hub_download(repo_id="onnx-community/Kokoro-82M-v1.0-ONNX", filename="kokoro-v1.0.onnx", cache_dir=str(model_dir))` and same for `voices-v1.0.bin`. Wrap in try/except for `HfHubHTTPError`, `ConnectionError`, `OSError` → raise `KokoroModelDownloadError`. Constructor calls this before instantiating `Kokoro(...)`.
- [ ] Step 4: `cd backend && uv run pytest tests/unit/services/tts/test_kokoro_download.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/tts/kokoro_provider.py backend/tests/unit/services/tts/test_kokoro_download.py
  git commit -m "feat(tts): Kokoro model download via huggingface_hub with error mapping"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/test_kokoro_download.py -v` — 2 passed

---

#### A13: `detect_tts_provider` + `create_tts_provider` factory

**Goal:** Auto-detect Kokoro availability; instantiate by name. Mirrors `services/summarizer/__init__.py`.
**Spec refs:** FR-04

**Files:**
- Create: `backend/app/services/tts/__init__.py`
- Test: `backend/tests/unit/services/tts/test_factory.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_detect_returns_kokoro_when_available(monkeypatch):
      monkeypatch.setattr("shutil.which", lambda c: "/opt/homebrew/bin/ffmpeg" if c == "ffmpeg" else None)
      monkeypatch.setattr("importlib.util.find_spec", lambda n: object() if n == "kokoro_onnx" else None)
      assert detect_tts_provider() == "kokoro"

  def test_detect_returns_none_when_ffmpeg_missing(monkeypatch):
      monkeypatch.setattr("shutil.which", lambda c: None)
      assert detect_tts_provider() is None

  def test_detect_returns_none_when_kokoro_not_installed(monkeypatch):
      monkeypatch.setattr("shutil.which", lambda c: "/usr/bin/ffmpeg")
      monkeypatch.setattr("importlib.util.find_spec", lambda n: None)
      assert detect_tts_provider() is None

  def test_create_kokoro_returns_instance(monkeypatch):
      monkeypatch.setattr("app.services.tts.kokoro_provider.KokoroProvider._ensure_model_downloaded", lambda _: None)
      p = create_tts_provider("kokoro", settings)
      assert isinstance(p, KokoroProvider)

  def test_create_unknown_returns_none(): assert create_tts_provider("bogus", settings) is None
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/unit/services/tts/test_factory.py -v` → expect FAIL.
- [ ] Step 3: Implement in `services/tts/__init__.py`:
  ```python
  def detect_tts_provider() -> str | None:
      if shutil.which("ffmpeg") and importlib.util.find_spec("kokoro_onnx"):
          return "kokoro"
      return None

  def create_tts_provider(name: str | None, settings: Settings) -> TTSProvider | None:
      if name in (None, "auto"):
          name = detect_tts_provider()
      if name == "kokoro":
          return KokoroProvider(model_dir=settings.data.directory / "models" / "tts")
      return None
  ```
- [ ] Step 4: `cd backend && uv run pytest tests/unit/services/tts/test_factory.py -v` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/tts/__init__.py backend/tests/unit/services/tts/test_factory.py
  git commit -m "feat(tts): detect + create TTS provider factory"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/ -v` — full A1-A13 suite green

---

#### A14: ID3 tagger (mutagen v2.3, embed cover)

**Goal:** `tag_mp3(mp3_path, book, section, track_n, track_total)` writes ID3v2.3 tags including embedded cover.
**Spec refs:** FR-27, D11

**Files:**
- Create: `backend/app/services/tts/id3_tagger.py`
- Test: `backend/tests/unit/services/tts/test_id3_tagger.py`

**Steps:**

- [ ] Step 1: Add `mutagen` to pyproject.toml; `uv sync`.
- [ ] Step 2: Write failing test
  ```python
  def test_tag_round_trip(tmp_path):
      mp3_path = tmp_path / "test.mp3"
      mp3_path.write_bytes(MINIMAL_MP3_BYTES)  # fixture: 1-second silence MP3
      cover_jpg = (FIXTURES / "cover.jpg").read_bytes()
      tag_mp3(mp3_path, title="Anchoring", artist="Daniel Kahneman",
              album="Thinking, Fast and Slow", track_n=1, track_total=47, cover_jpg=cover_jpg)
      tags = ID3(str(mp3_path))
      assert tags["TIT2"].text[0] == "Anchoring"
      assert tags["TPE1"].text[0] == "Daniel Kahneman"
      assert tags["TALB"].text[0] == "Thinking, Fast and Slow"
      assert tags["TRCK"].text[0] == "01/47"  # padded
      assert tags.getall("APIC")[0].data == cover_jpg
      assert tags.version == (2, 3, 0)
  ```
- [ ] Step 3: `cd backend && uv run pytest tests/unit/services/tts/test_id3_tagger.py -v` → expect FAIL.
- [ ] Step 4: Implement `tag_mp3(...)` in `id3_tagger.py`:
  ```python
  def tag_mp3(mp3_path, title, artist, album, track_n, track_total, cover_jpg=None):
      tags = ID3()
      tags.add(TIT2(encoding=3, text=title))
      tags.add(TPE1(encoding=3, text=artist))
      tags.add(TALB(encoding=3, text=album))
      tags.add(TRCK(encoding=3, text=f"{track_n:02d}/{track_total}"))
      if cover_jpg:
          tags.add(APIC(encoding=0, mime="image/jpeg", type=3, desc="Cover", data=cover_jpg))
      tags.save(str(mp3_path), v2_version=3)
  ```
- [ ] Step 5: `cd backend && uv run pytest tests/unit/services/tts/test_id3_tagger.py -v` → expect 1 passed.
- [ ] Step 6: Commit
  ```bash
  git add backend/app/services/tts/id3_tagger.py backend/tests/unit/services/tts/test_id3_tagger.py backend/tests/fixtures/cover.jpg backend/pyproject.toml backend/uv.lock
  git commit -m "feat(tts): ID3v2.3 tagger via mutagen"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/unit/services/tts/test_id3_tagger.py -v` — 1 passed

---

#### A15: Fix `AnnotationRepository.list_by_book` — UNION over `book_summary` annotations

**Goal:** `list_by_book` includes annotations on book summaries (currently silently dropped per recon C5).
**Spec refs:** D23, FR-53

**Files:**
- Modify: `backend/app/db/repositories/annotation_repo.py:40-60`
- Test: `backend/tests/integration/test_annotation_playlist.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_list_by_book_includes_book_summary_annotations(seeded_db):
      # Book 1 has 3 section annotations + 2 book_summary annotations
      seed_section_annotation(book_id=1, section_id=10, text="highlight A", order=1)
      seed_section_annotation(book_id=1, section_id=10, text="highlight B", order=2)
      seed_section_annotation(book_id=1, section_id=11, text="highlight C", order=1)
      summary = seed_book_summary(book_id=1)
      seed_annotation(content_type=ContentType.BOOK_SUMMARY, content_id=summary.id, text="bs hl 1")
      seed_annotation(content_type=ContentType.BOOK_SUMMARY, content_id=summary.id, text="bs hl 2")

      repo = AnnotationRepository(session)
      rows = await repo.list_by_book(book_id=1)
      texts = [r.selected_text for r in rows]
      assert texts == ["highlight A", "highlight B", "highlight C", "bs hl 1", "bs hl 2"]
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_annotation_playlist.py::test_list_by_book_includes_book_summary_annotations -v` → expect FAIL.
- [ ] Step 3: Modify `annotation_repo.py:40-60` `list_by_book` to UNION ALL: existing JOIN-via-BookSection query + new query for `content_type = BOOK_SUMMARY AND content_id IN (SELECT id FROM summaries WHERE book_id = :book_id)`. Order: section annotations by `(book_section.order_index, annotation.text_offset)`, book_summary annotations appended.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_annotation_playlist.py -v` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/db/repositories/annotation_repo.py backend/tests/integration/test_annotation_playlist.py
  git commit -m "fix(annotations): list_by_book unions over book_summary annotations"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_annotation_playlist.py -v` — 1 passed

---

#### A16: Book-delete cascade — unlink audio files + cleanup audio_positions

**Goal:** `BookService.delete_book(book_id)` removes audio MP3s + audio_position rows transactionally.
**Spec refs:** FR-26, FR-26b

**Files:**
- Modify: `backend/app/services/book_service.py`
- Test: `backend/tests/integration/test_book_delete_cascade.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_book_delete_unlinks_audio_files_and_positions(svc, tmp_data_dir):
      book = await svc.create_book(...)
      af = await svc.audio_repo.upsert(book.id, ContentType.SECTION_SUMMARY, 42, voice="af_sarah", mp3_bytes=b"X", **kw)
      pos_path = tmp_data_dir / af.file_path
      await svc.position_repo.upsert(ContentType.SECTION_SUMMARY, 42, "browser-X", 5)
      await svc.position_repo.upsert(ContentType.ANNOTATIONS_PLAYLIST, book.id, "browser-X", 3)

      await svc.delete_book(book.id)

      assert not pos_path.exists()
      assert (await svc.audio_repo.list_by_book(book.id)) == []
      assert (await svc.position_repo.get(ContentType.SECTION_SUMMARY, 42, "browser-X")) is None
      assert (await svc.position_repo.get(ContentType.ANNOTATIONS_PLAYLIST, book.id, "browser-X")) is None
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_book_delete_cascade.py -v` → expect FAIL.
- [ ] Step 3: In `book_service.py:delete_book(book_id)`: inside the existing transaction add `await self.audio_repo.delete_all_for_book(book_id)` (unlinks files + deletes rows), then `await self.position_repo.cleanup_for_book(book_id)` (per FR-26b SQL).
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_book_delete_cascade.py -v` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/book_service.py backend/tests/integration/test_book_delete_cascade.py
  git commit -m "feat(tts): book-delete cascade unlinks audio files + cleans audio_positions"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_book_delete_cascade.py -v` — 1 passed

---

#### A17: Re-import audio reconciliation in `_re_import_book`

**Goal:** Re-importing a book deletes orphaned AudioFile rows + marks remaining stale via lookup recompute.
**Spec refs:** FR-26a

**Files:**
- Modify: `backend/app/services/book_service.py:_re_import_book`
- Test: `backend/tests/integration/test_book_reimport_audio.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_reimport_deletes_orphan_audio(svc):
      book = await svc.import_book("art_of_war.epub")  # 13 sections
      await svc.audio_repo.upsert(book.id, ContentType.SECTION_SUMMARY, content_id=last_section_id, ...)
      # Simulate re-import where last section vanished (truncated EPUB)
      await svc._re_import_book(book.id, new_sections=[s for s in original if s.order_index < 12])
      remaining = await svc.audio_repo.list_by_book(book.id)
      assert all(r.content_id != last_section_id for r in remaining)

  async def test_reimport_with_changed_content_marks_stale(svc):
      book = await svc.import_book("...")
      af = await svc.audio_repo.upsert(book.id, ContentType.SECTION_SUMMARY, content_id=section_id,
                                       source_hash="OLD_HASH", **kw)
      # Re-import with edited section text → new sanitized hash
      await svc._re_import_book(book.id, new_sections=updated)
      lookup = await svc.audio_gen.lookup(book_id=book.id, content_type=ContentType.SECTION_SUMMARY,
                                          content_id=section_id, voice="af_sarah")
      assert lookup.stale is True
      assert lookup.stale_reason == "source_changed"
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_book_reimport_audio.py -v` → expect FAIL.
- [ ] Step 3: At end of `_re_import_book`: collect surviving `(book_section.id)` set; `await self.audio_repo.delete_orphans(book_id, surviving_section_ids)`; log `audio_reconciled {book_id, deleted_count}`. Add `delete_orphans(book_id, surviving_ids)` to repo if missing.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_book_reimport_audio.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/book_service.py backend/app/db/repositories/audio_file_repo.py backend/tests/integration/test_book_reimport_audio.py
  git commit -m "feat(tts): re-import reconciles AudioFile rows + marks stale"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_book_reimport_audio.py -v` — 2 passed

---

### Phase B — Job + API wiring (B1–B16)

#### B1: `AudioGenService` — orchestrator

**Goal:** One service that for a given (book_id, content_type, content_id, voice) sanitizes → segments → synthesizes → tags → atomically writes file → UPSERTs row. Used by worker (gen) and lookup (stale check).
**Spec refs:** FR-22, FR-23, FR-27, FR-12

**Files:**
- Create: `backend/app/services/audio_gen_service.py`
- Test: `backend/tests/integration/test_audio_gen_service.py`

**Steps:**

- [ ] Step 1: Write failing test (uses FakeTTSProvider returning fixed bytes + offsets)
  ```python
  async def test_generate_unit_creates_audio_file_row_and_writes_mp3(svc, tmp_data_dir):
      af = await svc.generate_unit(
          book_id=1, content_type=ContentType.SECTION_SUMMARY, content_id=42,
          voice="af_sarah", source_md="Hello world. Second sentence.", job_id=99,
      )
      mp3 = (tmp_data_dir / af.file_path).read_bytes()
      assert mp3.startswith(b"ID3")  # tagged
      assert af.sentence_count == 2
      assert af.source_hash == sha256(b"Hello world. Second sentence.").hexdigest()  # placeholder; real test sanitizes first
      assert af.sanitizer_version == "1.0"

  async def test_generate_unit_skips_on_empty_sanitizer(svc):
      with pytest.raises(EmptySanitizedTextError):
          await svc.generate_unit(book_id=1, content_type=ContentType.SECTION_SUMMARY,
                                  content_id=42, voice="af_sarah", source_md="```\n```", job_id=99)

  async def test_lookup_returns_stale_on_source_change(svc):
      await svc.generate_unit(..., source_md="Original.")
      result = await svc.lookup(book_id=1, content_type=..., content_id=42, voice="af_sarah",
                                current_source_md="Edited.")
      assert result.stale is True
      assert result.stale_reason == "source_changed"

  async def test_lookup_returns_stale_on_sanitizer_version_bump(svc, monkeypatch):
      await svc.generate_unit(..., source_md="X.")
      monkeypatch.setattr("app.services.tts.markdown_to_speech.SANITIZER_VERSION", "1.1")
      result = await svc.lookup(book_id=1, ..., current_source_md="X.")
      assert result.stale is True
      assert result.stale_reason == "sanitizer_upgraded"

  async def test_lookup_returns_stale_on_segmenter_drift(svc):
      # AudioFile sentence_count = 5, fresh segmentation = 6
      af = await svc.generate_unit(..., source_md="...")
      af.sentence_count = 6  # simulate
      await svc.session.commit()
      result = await svc.lookup(book_id=1, ..., current_source_md="originalsource")
      # Force fresh segmentation count to differ — assertion on stale_reason
      assert result.stale_reason in ("segmenter_drift", "source_changed")
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_gen_service.py -v` → expect FAIL.
- [ ] Step 3: Implement `AudioGenService(session, audio_repo, position_repo, annotation_repo, book_repo, summary_repo, tts_provider, settings)`:
  - `generate_unit(book_id, content_type, content_id, voice, source_md, job_id)`:
    1. `sanitized = sanitize(source_md)` → raises `EmptySanitizedTextError` propagating to worker.
    2. `result = self.tts.synthesize_segmented(sanitized.sentences, voice, speed=settings.tts.default_speed)` → returns SynthesisResult.
    3. Tag MP3 in-memory: write bytes to tmp, call `id3_tagger.tag_mp3(...)` with book/section/track metadata, read back.
    4. `repo.upsert(book_id, content_type, content_id, voice, mp3_bytes=tagged, duration_seconds=result.duration_total, sentence_count=len(sanitized.sentence_offsets_chars), sentence_offsets=result.sentence_offsets, source_hash=sha256(sanitized.text), sanitizer_version=SANITIZER_VERSION, job_id=job_id)`.
  - `lookup(book_id, content_type, content_id, voice, current_source_md)`:
    1. `af = await repo.lookup(book_id, content_type, content_id, voice)` (may be None).
    2. `sanitized_current = sanitize(current_source_md)` (or empty-skip).
    3. Return shape `LookupResult(pregenerated, sanitized_text, sentence_offsets_chars, url?, duration_seconds?, voice?, sentence_offsets_seconds?, source_hash_stored?, source_hash_current, sanitizer_version_stored?, sanitizer_version_current, stale, stale_reason)`. Compute stale per FR-12a precedence: `source_changed` first, else `sanitizer_upgraded`, else `segmenter_drift`.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_gen_service.py -v` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/audio_gen_service.py backend/tests/integration/test_audio_gen_service.py
  git commit -m "feat(tts): AudioGenService orchestrator + stale-detection lookup"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_gen_service.py -v` — 5 passed

---

#### B2: Worker dispatch for `step=AUDIO`

**Goal:** `JobQueueWorker` dispatches AUDIO jobs to `AudioGenService.run_job(job)`; emits per-unit SSE.
**Spec refs:** FR-19, FR-20, FR-21

**Files:**
- Modify: `backend/app/services/job_queue_worker.py`
- Modify: `backend/app/services/audio_gen_service.py` (add `run_job(job, on_event)`)
- Test: `backend/tests/integration/test_audio_job_e2e.py`

**Steps:**

- [ ] Step 1: Write failing test (uses FakeTTSProvider; full job lifecycle)
  ```python
  async def test_audio_job_runs_to_completion_with_sse(client, seeded_book_with_3_sections):
      events = []
      async def collect(): ...  # SSE listener
      asyncio.create_task(collect())
      r = await client.post(f"/api/v1/books/{book.id}/audio",
                            json={"scope": "sections", "section_ids": [s1, s2, s3], "voice": "af_sarah", "engine": "kokoro"})
      assert r.status_code == 202
      job_id = r.json()["job_id"]
      await wait_for_job(job_id, status="COMPLETED")

      # 3 section_audio_started + 3 section_audio_completed + 1 processing_started + 1 processing_completed
      kinds = [e["type"] for e in events]
      assert kinds.count("section_audio_started") == 3
      assert kinds.count("section_audio_completed") == 3
      assert "processing_completed" in kinds

      # AudioFile rows present
      rows = await audio_repo.list_by_book(book.id)
      assert len(rows) == 3

  async def test_audio_job_per_unit_failure_continues(client, seeded_book):
      # Section 2 has empty summary → EmptySanitizedTextError
      ...
      await wait_for_job(...)
      # Unit 2 emitted section_audio_failed{reason: "empty_after_sanitize"}; units 1+3 completed
      assert any(e["type"] == "section_audio_failed" and e["reason"] == "empty_after_sanitize" for e in events)
      rows = await audio_repo.list_by_book(book.id)
      assert len(rows) == 2  # 1 + 3, not the empty one
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_job_e2e.py -v` → expect FAIL.
- [ ] Step 3: In `job_queue_worker.py:_process_job`:
  ```python
  if job.step == ProcessingStep.AUDIO:
      await self.audio_gen_service.run_job(job, on_event=self._publish_sse)
      return
  # else existing summarize branch
  ```
  In `audio_gen_service.run_job(job, on_event)`: parse `job.request_params` for scope/section_ids/voice; enumerate units; emit `processing_started`. Loop:
  ```python
  for i, (kind, ref) in enumerate(units):
      on_event("section_audio_started", {job_id, kind, ref, index: i, total: N, last_event_at: now()})
      try:
          af = await self.generate_unit(...)
          job.progress["completed"] += 1
          on_event("section_audio_completed", {..., duration_seconds: af.duration_seconds, file_size_bytes: af.file_size_bytes})
      except EmptySanitizedTextError:
          on_event("section_audio_failed", {..., reason: "empty_after_sanitize"})
      except FfmpegEncodeError as e:
          on_event("section_audio_failed", {..., reason: "encode_failed"})
          job.error_message = (job.error_message or "")[-2048:] + e.stderr_tail
      except KokoroModelDownloadError:
          on_event("section_audio_failed", {..., reason: "model_download_failed"})
          job.status = JobStatus.FAILED  # whole-job per FR-05
          raise  # to outer
      await self.session.commit()  # persist progress incrementally
  ```
  After loop: if `job.progress.completed == 0`: status=FAILED; else COMPLETED. Emit final event.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_job_e2e.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/job_queue_worker.py backend/app/services/audio_gen_service.py backend/tests/integration/test_audio_job_e2e.py
  git commit -m "feat(tts): worker dispatch for step=AUDIO with per-unit SSE"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_job_e2e.py -v` — 2 passed

---

#### B3: SSE event names + `last_event_at` stamping + `section_audio_already_stale`

**Goal:** All audio-job SSE events carry monotonic `last_event_at`; stale-during-gen surfaces a counter.
**Spec refs:** FR-21, FR-21a, FR-32, §9.10

**Files:**
- Modify: `backend/app/api/sse.py:15-55` (or `EventBus.publish` if drift)
- Modify: `backend/app/services/audio_gen_service.py`
- Test: `backend/tests/integration/test_sse_audio_events.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_every_audio_event_has_last_event_at(audio_job_events):
      for ev in audio_job_events:
          assert "last_event_at" in ev["data"]
          assert isinstance(ev["data"]["last_event_at"], (int, float))

  async def test_last_event_at_strictly_monotone(audio_job_events):
      timestamps = [e["data"]["last_event_at"] for e in audio_job_events]
      assert timestamps == sorted(timestamps)
      assert len(set(timestamps)) == len(timestamps)  # strict (unique)

  async def test_section_audio_already_stale_emitted_on_mid_job_regen(svc, client):
      job_id = await start_long_audio_job(book_id=1)
      await wait_for_event("section_audio_started")
      # Simulate summary regen on section 2
      await svc.summary_service.regenerate(section_id=2, ...)
      events = await drain_events(job_id)
      assert any(e["type"] == "section_audio_already_stale" and e["data"]["section_id"] == 2 for e in events)
      job = await job_repo.get(job_id)
      assert job.progress["already_stale"] >= 1
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_sse_audio_events.py -v` → expect FAIL.
- [ ] Step 3: In `sse.py:EventBus.publish(event, data)`: ensure `data["last_event_at"] = time.time_ns()` (monotonic per process; ns precision sidesteps duplicate-timestamp risk). In `audio_gen_service.run_job`: add a per-unit hook that BEFORE writing the AudioFile, recomputes `current_source_hash` from the just-fetched `source_md` against `AudioFile.source_hash` for any prior generation of the same unit; if differs, emit `section_audio_already_stale` and increment `job.progress["already_stale"]`. (No-op if it's a brand-new unit.)
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_sse_audio_events.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/sse.py backend/app/services/audio_gen_service.py backend/tests/integration/test_sse_audio_events.py
  git commit -m "feat(tts): SSE last_event_at stamping + section_audio_already_stale event"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_sse_audio_events.py -v` — 3 passed

---

#### B4: `ProcessingJob.progress` JSON shape extension

**Goal:** `progress` includes `{completed, total, current_kind, current_ref, last_event_at, already_stale}`.
**Spec refs:** FR-21

**Files:**
- Modify: `backend/app/services/audio_gen_service.py`
- Test: `backend/tests/integration/test_audio_job_progress.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_progress_dict_keys(running_job_after_2_units):
      assert set(running_job_after_2_units.progress.keys()) >= {
          "completed", "total", "current_kind", "current_ref",
          "last_event_at", "already_stale"
      }
      assert running_job_after_2_units.progress["completed"] == 2

  async def test_progress_persisted_on_each_unit(svc, mid_job):
      # After unit 1, progress["completed"] == 1 in DB
      await wait_for_unit_complete(mid_job, 1)
      job = await job_repo.get(mid_job.id)
      assert job.progress["completed"] == 1
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_job_progress.py -v` → expect FAIL on shape.
- [ ] Step 3: In `audio_gen_service.run_job`: initialize `job.progress = {"completed": 0, "total": N, "current_kind": None, "current_ref": None, "last_event_at": time.time_ns(), "already_stale": 0}` and update on each event. Use `flag_modified(job, "progress")` after each mutation since SQLAlchemy doesn't auto-detect dict in-place changes on JSON columns.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_job_progress.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/audio_gen_service.py backend/tests/integration/test_audio_job_progress.py
  git commit -m "feat(tts): ProcessingJob.progress shape for audio jobs"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_job_progress.py -v` — 2 passed

---

#### B5: Worker-restart orphan-job recovery

**Goal:** Lifespan task on `bookcompanion serve` startup marks orphaned RUNNING audio jobs as FAILED with `error_message="server_restart"`.
**Spec refs:** FR-21b

**Files:**
- Modify: `backend/app/api/main.py:47-103` (lifespan)
- Create: `backend/app/services/audio_orphan_recovery.py`
- Test: `backend/tests/integration/test_orphan_recovery.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_orphan_audio_job_marked_failed_on_startup(seeded_db, monkeypatch):
      job = ProcessingJob(book_id=1, step=ProcessingStep.AUDIO, status=JobStatus.RUNNING, pid=99999)
      seeded_db.add(job); await seeded_db.commit()
      monkeypatch.setattr("os.kill", lambda pid, _: (_ for _ in ()).throw(ProcessLookupError()))

      await recover_orphan_audio_jobs(seeded_db)

      reloaded = await seeded_db.get(ProcessingJob, job.id)
      assert reloaded.status == JobStatus.FAILED
      assert reloaded.error_message == "server_restart"

  async def test_live_job_not_touched(seeded_db):
      job = ProcessingJob(book_id=1, step=ProcessingStep.AUDIO, status=JobStatus.RUNNING, pid=os.getpid())
      seeded_db.add(job); await seeded_db.commit()
      await recover_orphan_audio_jobs(seeded_db)
      reloaded = await seeded_db.get(ProcessingJob, job.id)
      assert reloaded.status == JobStatus.RUNNING

  async def test_no_audio_jobs_no_op(seeded_db):
      await recover_orphan_audio_jobs(seeded_db)  # should not error on empty
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_orphan_recovery.py -v` → expect FAIL.
- [ ] Step 3: Implement `recover_orphan_audio_jobs(session)` in `audio_orphan_recovery.py`:
  ```python
  async def recover_orphan_audio_jobs(session: AsyncSession) -> int:
      result = await session.execute(
          select(ProcessingJob)
          .where(ProcessingJob.status == JobStatus.RUNNING,
                 ProcessingJob.step == ProcessingStep.AUDIO)
      )
      count = 0
      for job in result.scalars():
          if job.pid is None or not _pid_alive(job.pid):
              job.status = JobStatus.FAILED
              job.error_message = "server_restart"
              count += 1
      await session.commit()
      return count

  def _pid_alive(pid: int) -> bool:
      try:
          os.kill(pid, 0); return True
      except (ProcessLookupError, PermissionError):
          return False
  ```
  In `main.py` lifespan: after migration check, before scheduler start, run `await recover_orphan_audio_jobs(session)` with a fresh session.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_orphan_recovery.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/main.py backend/app/services/audio_orphan_recovery.py backend/tests/integration/test_orphan_recovery.py
  git commit -m "feat(tts): worker-restart orphan recovery for step=AUDIO"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_orphan_recovery.py -v` — 3 passed

---

#### B6: Lifespan pre-warm Kokoro task

**Goal:** When `settings.tts.engine == "kokoro"`, lifespan task loads the model in a worker thread; on failure, logs and sets `app.state.tts_warm = False`.
**Spec refs:** FR-07, D32, S3

**Files:**
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/integration/test_kokoro_prewarm.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_prewarm_succeeds_sets_warm_true(monkeypatch, app):
      settings = Settings(tts=TTSConfig(engine="kokoro", prewarm_on_startup=True))
      monkeypatch.setattr("app.services.tts.kokoro_provider.KokoroProvider._ensure_model_downloaded", lambda _: None)
      monkeypatch.setattr("kokoro_onnx.Kokoro.__init__", lambda self, *a, **kw: None)
      async with lifespan(app, settings) as _:
          assert app.state.tts_warm is True

  async def test_prewarm_failure_logs_and_sets_false(monkeypatch, app, caplog):
      settings = Settings(tts=TTSConfig(engine="kokoro", prewarm_on_startup=True))
      def boom(self): raise KokoroModelDownloadError()
      monkeypatch.setattr("app.services.tts.kokoro_provider.KokoroProvider._ensure_model_downloaded", boom)
      async with lifespan(app, settings) as _:
          assert app.state.tts_warm is False
          assert any("kokoro_prewarm_failed" in r.message for r in caplog.records)

  async def test_prewarm_skipped_for_web_speech(app):
      settings = Settings(tts=TTSConfig(engine="web-speech"))
      async with lifespan(app, settings) as _:
          assert app.state.tts_warm is False  # not warmed (engine != kokoro)
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_kokoro_prewarm.py -v` → expect FAIL.
- [ ] Step 3: In `main.py` lifespan after orphan recovery:
  ```python
  app.state.tts_warm = False
  if settings.tts.engine == "kokoro" and settings.tts.prewarm_on_startup:
      try:
          await asyncio.to_thread(create_tts_provider("kokoro", settings))  # constructor does _ensure + Kokoro init
          app.state.tts_warm = True
          log.info("kokoro_prewarmed")
      except Exception as e:
          log.warning("kokoro_prewarm_failed", error=str(e))
          app.state.tts_warm = False
  ```
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_kokoro_prewarm.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/main.py backend/tests/integration/test_kokoro_prewarm.py
  git commit -m "feat(tts): Kokoro pre-warm lifespan task with graceful degradation"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_kokoro_prewarm.py -v` — 3 passed

---

#### B7: `POST /api/v1/books/{id}/audio` — race-safe queue

**Goal:** Validates input, BEGIN IMMEDIATE, INSERT job, returns 202 or 409-with-existing_job_id.
**Spec refs:** FR-18, §9.1

**Files:**
- Create: `backend/app/api/routes/audio.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_audio_concurrency.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_post_audio_queues_job(client, seeded_book):
      r = await client.post(f"/api/v1/books/{book.id}/audio",
                            json={"scope": "all", "voice": "af_sarah", "engine": "kokoro"})
      assert r.status_code == 202
      body = r.json()
      assert "job_id" in body and body["scope"] == "all" and body["total_units"] > 0

  async def test_post_audio_409_with_existing_job_id(client, seeded_book, running_audio_job):
      r = await client.post(f"/api/v1/books/{seeded_book.id}/audio",
                            json={"scope": "all", "voice": "af_sarah", "engine": "kokoro"})
      assert r.status_code == 409
      body = r.json()
      assert body["error"] == "audio_job_in_progress"
      assert body["existing_job_id"] == running_audio_job.id
      assert "started_at" in body

  async def test_post_audio_400_for_web_speech_engine(client, seeded_book):
      r = await client.post(f"/api/v1/books/{book.id}/audio",
                            json={"scope": "all", "voice": "default", "engine": "web-speech"})
      assert r.status_code == 400

  async def test_post_audio_503_when_ffmpeg_missing(client, seeded_book, monkeypatch):
      monkeypatch.setattr("shutil.which", lambda c: None)
      r = await client.post(f"/api/v1/books/{book.id}/audio", json={...})
      assert r.status_code == 503

  async def test_post_audio_concurrent_summarize_per_book_succeeds(client, seeded_book, running_summarize_job):
      r = await client.post(f"/api/v1/books/{book.id}/audio", json={...})
      assert r.status_code == 202  # different step, partial UNIQUE permits
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_concurrency.py -v` → expect FAIL.
- [ ] Step 3: Implement route:
  ```python
  @router.post("/api/v1/books/{book_id}/audio", status_code=202)
  async def queue_audio_job(book_id: int, body: AudioJobRequest, deps: Deps = Depends(get_deps)):
      validate(body)  # Pydantic
      if body.engine == "web-speech":
          raise HTTPException(400, {"error": "web_speech_not_pregeneratable"})
      if not shutil.which("ffmpeg"):
          raise HTTPException(503, {"error": "ffmpeg_missing"})
      if not deps.tts_provider:
          raise HTTPException(503, {"error": "kokoro_unavailable"})

      async with deps.session.begin():  # BEGIN IMMEDIATE
          existing = await deps.session.scalar(
              select(ProcessingJob).where(
                  ProcessingJob.book_id == book_id,
                  ProcessingJob.step == ProcessingStep.AUDIO,
                  ProcessingJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
              )
          )
          if existing:
              raise HTTPException(409, {"error": "audio_job_in_progress",
                                        "existing_job_id": existing.id,
                                        "scope": existing.request_params["scope"],
                                        "started_at": existing.created_at.isoformat()})
          total_units = await compute_total_units(deps.session, book_id, body)
          if total_units == 0:
              raise HTTPException(400, {"error": "no_units"})
          job = ProcessingJob(book_id=book_id, step=ProcessingStep.AUDIO,
                              status=JobStatus.PENDING, request_params=body.dict(),
                              progress={"completed": 0, "total": total_units, "last_event_at": time.time_ns()})
          deps.session.add(job)

      await deps.event_bus.publish("job_queued", {"job_id": job.id, "step": "audio"})
      return {"job_id": job.id, "scope": body.scope, "total_units": total_units}
  ```
  Define Pydantic `AudioJobRequest(BaseModel)` with `scope`, `section_ids: list[int] | None`, `voice: str`, `engine: Literal["kokoro"]`. Register router in `main.py:include_router(audio_router, prefix="")`.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_concurrency.py -v` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/app/api/main.py backend/tests/integration/test_audio_concurrency.py
  git commit -m "feat(tts): POST /audio race-safe queue with self-healing 409"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_concurrency.py -v` — 5 passed

---

#### B8: `GET /api/v1/books/{id}/audio` — inventory

**Goal:** Returns full AudioFile inventory + coverage tally.
**Spec refs:** §9.2

**Files:**
- Modify: `backend/app/api/routes/audio.py`
- Test: `backend/tests/integration/test_audio_inventory.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_inventory_returns_files_with_stale_flag(client, seeded_book_with_audio):
      r = await client.get(f"/api/v1/books/{book.id}/audio")
      assert r.status_code == 200
      body = r.json()
      assert body["book_id"] == book.id
      assert len(body["files"]) == 3
      f = body["files"][0]
      assert {"id", "content_type", "content_id", "voice", "url", "duration_seconds",
              "file_size_bytes", "generated_at", "source_hash", "stale"} <= f.keys()
      assert body["coverage"] == {"total": 47, "generated": 3, "stale": 1}
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_inventory.py -v` → expect FAIL.
- [ ] Step 3: Implement route. Use `audio_repo.list_by_book` + per-row `audio_gen.lookup` (efficient: batch the source-md fetches; or separately compute coverage by querying total_sections from BookSectionRepository + counting AudioFile rows).
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_inventory.py -v` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/test_audio_inventory.py
  git commit -m "feat(tts): GET /audio inventory with coverage + stale flags"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_inventory.py -v` — 1 passed

---

#### B9: `GET /api/v1/audio/lookup` — sanitize + segment + stale

**Goal:** Click-play single-content lookup; always returns sanitized text + offsets; stale computed server-side.
**Spec refs:** §9.6, FR-12a

**Files:**
- Modify: `backend/app/api/routes/audio.py`
- Test: `backend/tests/integration/test_audio_lookup_stale.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_lookup_returns_sanitized_text_when_no_pregen(client, seeded_section_with_summary):
      r = await client.get("/api/v1/audio/lookup",
                           params={"book_id": book.id, "content_type": "section_summary",
                                   "content_id": section.id})
      assert r.status_code == 200
      body = r.json()
      assert body["pregenerated"] is False
      assert body["sanitized_text"] != ""
      assert isinstance(body["sentence_offsets_chars"], list)
      assert "url" not in body or body["url"] is None

  async def test_lookup_pregen_includes_stale_false(client, seeded_section_with_audio):
      r = await client.get("/api/v1/audio/lookup", params={...})
      body = r.json()
      assert body["pregenerated"] is True
      assert body["stale"] is False
      assert body["url"].endswith(".mp3")
      assert body["sentence_offsets_seconds"] is not None
      assert body["source_hash_stored"] == body["source_hash_current"]

  async def test_lookup_pregen_stale_after_summary_edit(client, svc, seeded):
      await svc.summary_service.edit(section_id=42, new_md="Edited.")
      r = await client.get("/api/v1/audio/lookup", params={...})
      body = r.json()
      assert body["stale"] is True and body["stale_reason"] == "source_changed"
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_lookup_stale.py -v` → expect FAIL.
- [ ] Step 3: Implement route → calls `audio_gen.lookup(...)` and serializes `LookupResult` per §9.6.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_lookup_stale.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/test_audio_lookup_stale.py
  git commit -m "feat(tts): GET /audio/lookup with sanitize + segment + stale"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_lookup_stale.py -v` — 3 passed

---

#### B10: `GET /audio/{ct}/{ci}.mp3` — file fetch (no auth, range-aware)

**Goal:** Serve MP3 bytes via FastAPI `FileResponse` with `Cache-Control: public, max-age=86400`.
**Spec refs:** §9.3, D20

**Files:**
- Modify: `backend/app/api/routes/audio.py`
- Test: `backend/tests/integration/test_audio_serve.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_serve_returns_mp3_bytes(client, seeded_audio_file):
      r = await client.get(f"/api/v1/books/{book.id}/audio/section_summary/{section.id}.mp3")
      assert r.status_code == 200
      assert r.headers["content-type"] == "audio/mpeg"
      assert r.headers["cache-control"] == "public, max-age=86400"
      assert r.content[:3] == b"ID3"

  async def test_serve_404_when_missing(client, seeded_book):
      r = await client.get(f"/api/v1/books/{book.id}/audio/section_summary/999.mp3")
      assert r.status_code == 404

  async def test_serve_supports_range(client, seeded_audio_file):
      r = await client.get(f"/api/v1/books/{book.id}/audio/section_summary/{section.id}.mp3",
                           headers={"Range": "bytes=0-127"})
      assert r.status_code == 206
      assert len(r.content) == 128
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_serve.py -v` → expect FAIL.
- [ ] Step 3: Implement route returning `FileResponse(audio_file_path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})`. FastAPI's FileResponse handles Range automatically.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_serve.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/test_audio_serve.py
  git commit -m "feat(tts): GET /audio/{ct}/{ci}.mp3 file serve"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_serve.py -v` — 3 passed

---

#### B11: `DELETE /api/v1/books/{id}/audio` — cancel-then-delete

**Goal:** Cancels in-flight audio job (if any) before unlinking files + deleting rows.
**Spec refs:** FR-24

**Files:**
- Modify: `backend/app/api/routes/audio.py`
- Test: `backend/tests/integration/test_audio_delete.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_delete_all_returns_204_and_unlinks(client, seeded_audio_files):
      r = await client.delete(f"/api/v1/books/{book.id}/audio")
      assert r.status_code == 204
      rows = await audio_repo.list_by_book(book.id)
      assert rows == []
      assert not (DATA_DIR / "audio" / str(book.id)).exists()

  async def test_delete_cancels_in_flight_job(client, running_audio_job):
      r = await client.delete(f"/api/v1/books/{running_audio_job.book_id}/audio")
      assert r.status_code == 204
      await asyncio.sleep(1)  # allow cancel to propagate
      job = await job_repo.get(running_audio_job.id)
      assert job.status in (JobStatus.CANCELLED, JobStatus.FAILED)
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_delete.py -v` → expect FAIL.
- [ ] Step 3: Implement route: query for in-flight audio job for book; if exists, call existing job-cancel pathway (`POST /jobs/{id}/cancel` internally or service method); await with 5s timeout then SIGKILL; then `audio_repo.delete_all_for_book`. Return 204.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_delete.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/test_audio_delete.py
  git commit -m "feat(tts): DELETE /audio cancels in-flight job before cleanup"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_delete.py -v` — 2 passed

---

#### B12: `DELETE /api/v1/books/{id}/audio/{ct}/{ci}` — per-row delete with 409

**Goal:** Per-row delete; 409 if a RUNNING audio job is currently writing this unit.
**Spec refs:** FR-25

**Files:**
- Modify: `backend/app/api/routes/audio.py`
- Test: `backend/tests/integration/test_audio_delete.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_delete_one_returns_204(client, seeded_audio_files):
      r = await client.delete(f"/api/v1/books/{book.id}/audio/section_summary/42")
      assert r.status_code == 204

  async def test_delete_one_409_when_currently_writing(client, running_job_writing_section_42):
      r = await client.delete(f"/api/v1/books/{book.id}/audio/section_summary/42")
      assert r.status_code == 409
      body = r.json()
      assert "Wait or cancel job" in body["detail"]
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_delete.py::test_delete_one_409_when_currently_writing -v` → expect FAIL.
- [ ] Step 3: Implement route: check `ProcessingJob.progress.current_kind == ct AND current_ref == ci` for any RUNNING audio job for this book; if match return 409. Else `audio_repo.delete_one(...)`.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_delete.py -v` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/test_audio_delete.py
  git commit -m "feat(tts): DELETE per-row with 409-if-writing"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_delete.py -v` — 4 passed

---

#### B13: `POST /api/v1/audio/sample` — voice sample (rate-limited)

**Goal:** Returns 10-second Kokoro-synthesized MP3 of a fixed sample passage; rate-limit 5/min/IP.
**Spec refs:** §9.5, FR-46

**Files:**
- Modify: `backend/app/api/routes/audio.py`
- Test: `backend/tests/integration/test_audio_sample.py`

**Steps:**

- [ ] Step 1: Add `slowapi` to pyproject.toml; `uv sync`.
- [ ] Step 2: Write failing test
  ```python
  async def test_sample_returns_mp3(client, monkeypatch):
      monkeypatch.setattr(KokoroProvider, "synthesize", lambda self, text, voice, speed=1.0: SynthesisResult(b"ID3...", 24000, [0.0]))
      r = await client.post("/api/v1/audio/sample", json={"voice": "af_sarah"})
      assert r.status_code == 200
      assert r.headers["content-type"] == "audio/mpeg"
      assert r.content.startswith(b"ID3")

  async def test_sample_503_when_kokoro_unavailable(client, monkeypatch):
      monkeypatch.setattr("app.api.deps.get_tts_provider", lambda: None)
      r = await client.post("/api/v1/audio/sample", json={"voice": "af_sarah"})
      assert r.status_code == 503

  async def test_sample_rate_limit_after_5(client):
      for _ in range(5):
          r = await client.post("/api/v1/audio/sample", json={"voice": "af_sarah"})
          assert r.status_code == 200
      r6 = await client.post("/api/v1/audio/sample", json={"voice": "af_sarah"})
      assert r6.status_code == 429
  ```
- [ ] Step 3: `cd backend && uv run pytest tests/integration/test_audio_sample.py -v` → expect FAIL.
- [ ] Step 4: Implement route with `@limiter.limit("5/minute")` decorator (slowapi keyed on IP). Default sample text: `"This is a quick sample of the selected voice for the Book Companion audiobook feature."`.
- [ ] Step 5: `cd backend && uv run pytest tests/integration/test_audio_sample.py -v` → expect 3 passed.
- [ ] Step 6: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/test_audio_sample.py backend/pyproject.toml backend/uv.lock
  git commit -m "feat(tts): POST /audio/sample with rate limit"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_sample.py -v` — 3 passed

---

#### B14: `GET/PUT /api/v1/audio_position` — resume position routes

**Goal:** Position read returns `has_other_browser` hint; PUT debounces.
**Spec refs:** §9.7, §9.8, FR-37–FR-41

**Files:**
- Create: `backend/app/api/routes/audio_position.py`
- Modify: `backend/app/api/main.py` (register router)
- Test: `backend/tests/integration/test_audio_position_routes.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_put_then_get_position(client):
      await client.put("/api/v1/audio_position", json={
          "content_type": "section_summary", "content_id": 42,
          "browser_id": "uuid-A", "sentence_index": 16})
      r = await client.get("/api/v1/audio_position",
                           params={"content_type": "section_summary",
                                   "content_id": 42, "browser_id": "uuid-A"})
      assert r.status_code == 200
      assert r.json()["sentence_index"] == 16

  async def test_get_returns_has_other_browser(client):
      await client.put("/api/v1/audio_position", json={..., "browser_id": "A", "sentence_index": 10})
      await asyncio.sleep(0.01)
      await client.put("/api/v1/audio_position", json={..., "browser_id": "B", "sentence_index": 25})
      r = await client.get("/api/v1/audio_position", params={..., "browser_id": "A"})
      assert r.json()["has_other_browser"] is True

  async def test_get_404_when_no_position(client):
      r = await client.get("/api/v1/audio_position", params={"content_type": "section_summary",
                                                              "content_id": 99999, "browser_id": "X"})
      assert r.status_code == 404
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_position_routes.py -v` → expect FAIL.
- [ ] Step 3: Implement two routes calling `audio_position_repo.get_with_hint` and `.upsert`. Both routes use Pydantic models for validation.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_position_routes.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio_position.py backend/app/api/main.py backend/tests/integration/test_audio_position_routes.py
  git commit -m "feat(tts): GET/PUT /audio_position routes"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_position_routes.py -v` — 3 passed

---

#### B15: `GET /api/v1/spikes/tts` — spike doc lookup (mtime-newest glob)

**Goal:** Returns latest matching `docs/spikes/*tts-engine-spike.md` by mtime.
**Spec refs:** §9.9, FR-44

**Files:**
- Create: `backend/app/api/routes/spikes.py`
- Test: `backend/tests/integration/test_spikes_route.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_spike_route_returns_available_false_when_no_file(client, tmp_repo):
      r = client.get("/api/v1/spikes/tts")
      assert r.status_code == 200
      assert r.json() == {"available": False}

  def test_spike_route_returns_newest_match(client, tmp_repo):
      (tmp_repo / "docs" / "spikes" / "2026-05-10-tts-engine-spike.md").write_text("OLD")
      time.sleep(0.01)
      newest = tmp_repo / "docs" / "spikes" / "2026-05-15-tts-engine-spike.md"
      newest.write_text("# Spike findings")
      r = client.get("/api/v1/spikes/tts")
      body = r.json()
      assert body["available"] is True
      assert body["path"].endswith("2026-05-15-tts-engine-spike.md")
      assert body["content_md"] == "# Spike findings"
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_spikes_route.py -v` → expect FAIL.
- [ ] Step 3: Implement route: `glob("docs/spikes/*tts-engine-spike.md")` rooted at repo root (use `Path(__file__).parents[3]` or settings-derived); pick `max(matches, key=lambda p: p.stat().st_mtime)`. Read text. Return `{available, path, content_md}` or `{available: False}`.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_spikes_route.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/spikes.py backend/app/api/main.py backend/tests/integration/test_spikes_route.py
  git commit -m "feat(tts): GET /spikes/tts route (newest-by-mtime glob)"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_spikes_route.py -v` — 2 passed

---

#### B16: `GET/PUT /api/v1/settings/tts` + `GET /settings/tts/status`

**Goal:** TTS-specific settings round-trip with voice validation; warm-status endpoint.
**Spec refs:** FR-43, FR-47

**Files:**
- Modify: `backend/app/api/routes/settings.py`
- Test: `backend/tests/integration/test_settings_tts.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_get_settings_tts(client):
      r = await client.get("/api/v1/settings/tts")
      assert r.status_code == 200
      assert r.json()["engine"] == "web-speech"

  async def test_put_settings_tts_persists(client):
      r = await client.put("/api/v1/settings/tts",
                           json={"engine": "kokoro", "voice": "af_sarah", "default_speed": 1.25})
      assert r.status_code == 200
      r2 = await client.get("/api/v1/settings/tts")
      assert r2.json()["voice"] == "af_sarah"

  async def test_put_settings_tts_unknown_voice_422(client, monkeypatch):
      monkeypatch.setattr("app.services.tts.kokoro_provider.KOKORO_VOICES", {"af_sarah", "af_bella"})
      r = await client.put("/api/v1/settings/tts",
                           json={"engine": "kokoro", "voice": "af_typo"})
      assert r.status_code == 422
      assert "available" in r.json()

  async def test_get_status_warm(client, monkeypatch):
      monkeypatch.setattr("app.api.deps.get_app_state", lambda: SimpleNamespace(tts_warm=True))
      r = await client.get("/api/v1/settings/tts/status")
      assert r.json()["status"] == "warm"
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_settings_tts.py -v` → expect FAIL.
- [ ] Step 3: Implement two routes. PUT validates `voice` against the active engine's voice list (Kokoro: `KOKORO_VOICES` module-level dict; Web Speech: skip — frontend pre-validates). Status route reads `app.state.tts_warm` and Kokoro model file existence to return `"warm" | "cold" | "not_downloaded" | "download_failed"`.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_settings_tts.py -v` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/settings.py backend/tests/integration/test_settings_tts.py
  git commit -m "feat(tts): /settings/tts GET/PUT + /status routes"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_settings_tts.py -v` — 4 passed

---

### Phase C — Frontend reader playback (C1–C15)

#### C1: `ttsPlayer.ts` Pinia store

**Goal:** Reactive player state with `error` status + `errorKind`.
**Spec refs:** FR-28, FR-28a

**Files:**
- Create: `frontend/src/stores/ttsPlayer.ts`
- Test: `frontend/src/stores/__tests__/ttsPlayer.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  describe('ttsPlayerStore', () => {
    it('starts idle', () => {
      const s = useTtsPlayerStore();
      expect(s.status).toBe('idle');
      expect(s.isActive).toBe(false);
    });
    it('open(content) transitions to loading then playing', async () => {
      const s = useTtsPlayerStore();
      s.open({ contentType: 'section_summary', contentId: 42 });
      expect(s.status).toBe('loading');
      expect(s.isActive).toBe(true);
    });
    it('setError moves to error with errorKind', () => {
      const s = useTtsPlayerStore();
      s.setError('mp3_fetch_failed');
      expect(s.status).toBe('error');
      expect(s.errorKind).toBe('mp3_fetch_failed');
    });
    it('retry resets error and re-opens at sentenceIndex', () => {
      const s = useTtsPlayerStore();
      s.sentenceIndex = 5;
      s.setError('utterance_failed');
      const spy = vi.fn();
      s.$onAction(({ name, args }) => { if (name === 'open') spy(args); });
      s.retry();
      expect(s.errorKind).toBe(null);
    });
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- ttsPlayer` → expect FAIL.
- [ ] Step 3: Implement store with state per FR-28: `{isActive, contentType, contentId, sentenceIndex, totalSentences, status, engine, voice, mp3Url, sentenceOffsets, sentenceOffsetsChars, sanitizedText, stale, mediaSessionEnabled, errorKind, defaultEngine, activeEngineReason}`. Actions: `open`, `close`, `play`, `pause`, `nextSentence`, `prevSentence`, `setError`, `retry`.
- [ ] Step 4: `cd frontend && npm run test:unit -- ttsPlayer` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/stores/ttsPlayer.ts frontend/src/stores/__tests__/ttsPlayer.spec.ts
  git commit -m "feat(tts/fe): ttsPlayer Pinia store"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- ttsPlayer -v` — all green
- `cd frontend && npm run type-check` — 0 errors

---

#### C2: `useTtsEngine.ts` composable — engine routing skeleton

**Goal:** Composable returns the right engine implementation based on `lookup` response.
**Spec refs:** FR-30

**Files:**
- Create: `frontend/src/composables/audio/useTtsEngine.ts`
- Test: `frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test (mock `/audio/lookup` and engine impls)
  ```typescript
  it('routes to Mp3Engine when pregenerated=true', async () => {
    fetchMock.mockResolvedValue({ pregenerated: true, url: '/api/v1/.../42.mp3', sentence_offsets_seconds: [0, 4, 9] });
    const engine = await useTtsEngine().load({ contentType: 'section_summary', contentId: 42 });
    expect(engine.kind).toBe('mp3');
  });
  it('routes to WebSpeechEngine when pregenerated=false', async () => {
    fetchMock.mockResolvedValue({ pregenerated: false, sanitized_text: 'Hello.', sentence_offsets_chars: [0] });
    const engine = await useTtsEngine().load({ contentType: 'section_summary', contentId: 42 });
    expect(engine.kind).toBe('web-speech');
  });
  it('engine.play / pause / next emit highlight events', async () => {
    const eng = await useTtsEngine().load({ contentType: 'section_summary', contentId: 42 });
    const onSentence = vi.fn();
    eng.onSentenceChange(onSentence);
    await eng.play();
    expect(onSentence).toHaveBeenCalledWith(0);
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- useTtsEngine` → expect FAIL.
- [ ] Step 3: Implement `useTtsEngine` returning `{load(content)}` that fetches `/audio/lookup`, picks `Mp3Engine` (next task) or `WebSpeechEngine` (next task), and exposes a uniform contract: `{kind, play(), pause(), nextSentence(), prevSentence(), seek(idx), onSentenceChange(cb), onEnd(cb), terminate()}`.
- [ ] Step 4: `cd frontend && npm run test:unit -- useTtsEngine` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/useTtsEngine.ts frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts
  git commit -m "feat(tts/fe): useTtsEngine routing composable"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useTtsEngine -v` — 3 passed

---

#### C3: WebSpeechEngine — slice-by-offsets + per-sentence utterance

**Goal:** Slice `sanitized_text` by `sentence_offsets_chars`, iterate `SpeechSynthesisUtterance`, advance on `end`.
**Spec refs:** FR-30, D33

**Files:**
- Create: `frontend/src/composables/audio/webSpeechEngine.ts`
- Test: `frontend/src/composables/audio/__tests__/webSpeechEngine.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test (mock SpeechSynthesisUtterance)
  ```typescript
  it('slices text into sentences', () => {
    const eng = new WebSpeechEngine({
      sanitized_text: 'First. Second. Third.',
      sentence_offsets_chars: [0, 7, 15],
      voice: 'Samantha',
    });
    expect(eng.sentences).toEqual(['First.', 'Second.', 'Third.']);
  });
  it('advances on utterance end', async () => {
    const eng = new WebSpeechEngine({...});
    const onSentence = vi.fn();
    eng.onSentenceChange(onSentence);
    await eng.play();
    triggerUtteranceEnd();  // mock
    expect(onSentence).toHaveBeenLastCalledWith(1);
  });
  it('emits no-voices when getVoices returns empty', async () => {
    mockGetVoices([]);
    const eng = new WebSpeechEngine({...});
    const errSpy = vi.fn();
    eng.onError(errSpy);
    await eng.play();
    expect(errSpy).toHaveBeenCalledWith('engine_unavailable');
  });
  it('pause/resume restarts current utterance', async () => {
    const eng = new WebSpeechEngine({...});
    await eng.play();
    eng.pause();
    expect(speechSynthesis.paused).toBe(true);
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- webSpeechEngine` → expect FAIL.
- [ ] Step 3: Implement engine using `speechSynthesis.speak(new SpeechSynthesisUtterance(s))` per sentence; on `end` advance index + speak next; on `error` invoke `onError('utterance_failed')`. Pre-flight `getVoices()` after `voiceschanged` event; if empty, emit `engine_unavailable`. Pause via `speechSynthesis.pause()`.
- [ ] Step 4: `cd frontend && npm run test:unit -- webSpeechEngine` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/webSpeechEngine.ts frontend/src/composables/audio/__tests__/webSpeechEngine.spec.ts
  git commit -m "feat(tts/fe): WebSpeechEngine implementation"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- webSpeechEngine -v` — 4 passed

---

#### C4: Mp3Engine — `<audio>` + `timeupdate` against sentence_offsets

**Goal:** Drive playback from a hidden `<audio>` element; advance highlight when `currentTime` crosses next sentence offset.
**Spec refs:** FR-30, D33

**Files:**
- Create: `frontend/src/composables/audio/mp3Engine.ts`
- Test: `frontend/src/composables/audio/__tests__/mp3Engine.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test (use happy-dom Audio mock)
  ```typescript
  it('advances sentence on timeupdate crossing offset', async () => {
    const eng = new Mp3Engine({ url: '/.../42.mp3', sentence_offsets: [0.0, 4.2, 9.7] });
    const onSentence = vi.fn();
    eng.onSentenceChange(onSentence);
    await eng.play();
    eng._fakeTime(5.0);  // crosses 4.2
    expect(onSentence).toHaveBeenLastCalledWith(1);
    eng._fakeTime(10.0);  // crosses 9.7
    expect(onSentence).toHaveBeenLastCalledWith(2);
  });
  it('emits onEnd when audio ends', async () => {
    const eng = new Mp3Engine({...});
    const onEnd = vi.fn();
    eng.onEnd(onEnd);
    eng._fakeEnd();
    expect(onEnd).toHaveBeenCalled();
  });
  it('seek(idx) sets currentTime to offset', () => {
    const eng = new Mp3Engine({ url: '...', sentence_offsets: [0, 4.2, 9.7] });
    eng.seek(2);
    expect(eng.audio.currentTime).toBe(9.7);
  });
  it('emits mp3_fetch_failed on audio error', async () => {
    const eng = new Mp3Engine({...});
    const errSpy = vi.fn();
    eng.onError(errSpy);
    eng._fakeError();
    expect(errSpy).toHaveBeenCalledWith('mp3_fetch_failed');
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- mp3Engine` → expect FAIL.
- [ ] Step 3: Implement engine: create `Audio` element (not mounted to DOM yet); attach `timeupdate` listener that compares `currentTime` to next-offset and increments index on crossing; `ended` → `onEnd`; `error` → `onError('mp3_fetch_failed')`. `seek(idx)` sets `currentTime`. `play/pause` → `audio.play()/pause()`.
- [ ] Step 4: `cd frontend && npm run test:unit -- mp3Engine` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/mp3Engine.ts frontend/src/composables/audio/__tests__/mp3Engine.spec.ts
  git commit -m "feat(tts/fe): Mp3Engine with timeupdate-driven highlights"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- mp3Engine -v` — 4 passed

---

#### C5: Player error handling + Retry

**Goal:** Engine errors transition store to `error` status; Playbar shows banner with Retry that re-invokes engine at current sentenceIndex.
**Spec refs:** FR-28a

**Files:**
- Modify: `frontend/src/composables/audio/useTtsEngine.ts`
- Modify: `frontend/src/stores/ttsPlayer.ts`
- Test: `frontend/src/composables/audio/__tests__/useTtsEngine.spec.ts` (add cases)

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('engine error transitions store to error', async () => {
    const store = useTtsPlayerStore();
    const eng = await useTtsEngine().load({...});
    eng._fakeError('mp3_fetch_failed');
    expect(store.status).toBe('error');
    expect(store.errorKind).toBe('mp3_fetch_failed');
  });
  it('retry re-loads engine and seeks to current sentenceIndex', async () => {
    const store = useTtsPlayerStore();
    store.sentenceIndex = 7;
    store.setError('mp3_fetch_failed');
    await store.retry();
    expect(store.status).toBe('playing');
    // engine seeked to sentence 7
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- useTtsEngine` → expect FAIL on new cases.
- [ ] Step 3: Wire `onError` callback in `useTtsEngine.load(...)` to `store.setError(kind)`. `store.retry()` calls `useTtsEngine().load()` again, then `engine.seek(store.sentenceIndex)` and `engine.play()`.
- [ ] Step 4: `cd frontend && npm run test:unit -- useTtsEngine` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/useTtsEngine.ts frontend/src/stores/ttsPlayer.ts
  git commit -m "feat(tts/fe): player error state + Retry"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useTtsEngine -v` — 5 passed

---

#### C6: `useAudioApiError.ts` — generic API-error → toast mapping

**Goal:** All `/audio/*` route errors flow through one mapper that emits a Retry-capable toast.
**Spec refs:** §11.1.1

**Files:**
- Create: `frontend/src/composables/audio/useAudioApiError.ts`
- Test: `frontend/src/composables/audio/__tests__/useAudioApiError.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('503 maps to engine-unavailable toast', () => {
    const toastSpy = vi.fn();
    useAudioApiError(toastSpy)({ status: 503 });
    expect(toastSpy).toHaveBeenCalledWith({ kind: 'warning', text: expect.stringContaining('temporarily unavailable'), action: 'Retry' });
  });
  it('network error maps to reconnecting toast', () => { ... });
  it('429 maps to rate-limit toast', () => { ... });
  it('500 maps to generic error toast', () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- useAudioApiError` → expect FAIL.
- [ ] Step 3: Implement composable returning a function `(error) => void` that classifies error and calls `useToast().show(...)`.
- [ ] Step 4: `cd frontend && npm run test:unit -- useAudioApiError` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/useAudioApiError.ts frontend/src/composables/audio/__tests__/useAudioApiError.spec.ts
  git commit -m "feat(tts/fe): useAudioApiError generic mapping"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useAudioApiError -v` — 4 passed

---

#### C7: `Playbar.vue` — sticky-bottom transport

**Goal:** Sticky-bottom control surface with play/pause, prev/next sentence, speed selector, EngineChip, sentence index, elapsed/total.
**Spec refs:** FR-29, MSF N3, DESIGN.md `bc-playbar`
**Wireframe refs:** `docs/wireframes/2026-05-02-audiobook-mode/01_reader-section-player_desktop-web.html`, `01_reader-section-player_mobile-web.html`, `02_book-summary-player_desktop-web.html`, `02_book-summary-player_mobile-web.html`

**Files:**
- Create: `frontend/src/components/audio/Playbar.vue`
- Test: `frontend/src/components/audio/__tests__/Playbar.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  describe('Playbar', () => {
    it('renders only when store.isActive', () => {
      const store = useTtsPlayerStore();
      const wrap = mount(Playbar);
      expect(wrap.find('.bc-playbar').exists()).toBe(false);
      store.isActive = true;
      expect(wrap.find('.bc-playbar').exists()).toBe(true);
    });
    it('shows engine chip + sentence index + elapsed/total', () => {
      const store = useTtsPlayerStore();
      Object.assign(store, { isActive: true, engine: 'kokoro', voice: 'af_sarah',
                              sentenceIndex: 16, totalSentences: 47,
                              currentTime: 134, durationSeconds: 368 });
      const wrap = mount(Playbar);
      expect(wrap.text()).toContain('sentence 17 of 47');
      expect(wrap.text()).toContain('2:14 / 6:08');
    });
    it('shows Limited controls pill when engine=web-speech', () => {
      const store = useTtsPlayerStore();
      store.engine = 'web-speech'; store.isActive = true;
      const wrap = mount(Playbar);
      expect(wrap.find('[data-testid="limited-controls"]').exists()).toBe(true);
    });
    it('renders error banner with Retry on status=error', async () => {
      const store = useTtsPlayerStore();
      Object.assign(store, { isActive: true, status: 'error', errorKind: 'mp3_fetch_failed' });
      const wrap = mount(Playbar);
      const retry = wrap.find('button[data-testid="retry"]');
      expect(retry.exists()).toBe(true);
      const spy = vi.spyOn(store, 'retry');
      await retry.trigger('click');
      expect(spy).toHaveBeenCalled();
    });
    it('clicking play/pause toggles store.status', async () => { ... });
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- Playbar` → expect FAIL.
- [ ] Step 3: Author `Playbar.vue` — sticky bottom, `bc-playbar` class, white surface, 14px radius, raised shadow per DESIGN.md. Slot in Heroicon SVGs (existing pattern). Format duration via `M:SS / M:SS`. Apply host-app Tailwind tokens (do NOT copy wireframe pixel-for-pixel; use DESIGN.md tokens).
- [ ] Step 4: `cd frontend && npm run test:unit -- Playbar` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/Playbar.vue frontend/src/components/audio/__tests__/Playbar.spec.ts
  git commit -m "feat(tts/fe): Playbar sticky-bottom transport"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- Playbar -v` — 5 passed
- `cd frontend && npm run lint` — 0 errors

---

#### C8: `EngineChip.vue` — active engine + reason tooltip

**Goal:** Pill atom; shows ACTIVE engine; tooltip explains active≠default reason.
**Spec refs:** FR-32
**Wireframe refs:** `01_reader-section-player_*`, `02_book-summary-player_*`, `06_annotations-player_*`

**Files:**
- Create: `frontend/src/components/audio/EngineChip.vue`
- Create: `frontend/src/composables/audio/useEngineCopy.ts`
- Test: `frontend/src/components/audio/__tests__/EngineChip.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('shows kokoro chip with voice name', () => {
    const wrap = mount(EngineChip, { props: { engine: 'kokoro', voice: 'af_sarah' } });
    expect(wrap.text()).toContain('Kokoro · af_sarah');
    expect(wrap.classes()).toContain('bc-engine-chip--kokoro');
  });
  it('renders tooltip when active != default', () => {
    const wrap = mount(EngineChip, { props: { engine: 'web-speech', defaultEngine: 'kokoro', reason: 'no_pregen' } });
    expect(wrap.find('[role="tooltip"]').text())
      .toContain('Default is kokoro; using web-speech for this section because no pre-generated audio exists');
  });
  it('useEngineCopy returns reason copy for each kind', () => {
    expect(useEngineCopy('no_pregen', 'kokoro')).toContain('no pre-generated');
    expect(useEngineCopy('model_not_downloaded', 'kokoro')).toContain('not downloaded');
    expect(useEngineCopy('model_loading', 'kokoro')).toContain('loading');
    expect(useEngineCopy('engine_unavailable', 'kokoro')).toContain('unavailable');
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- EngineChip` → expect FAIL.
- [ ] Step 3: Author component + composable. Indigo pill for kokoro (`bc-engine-chip--kokoro` per DESIGN.md), neutral grey for web-speech.
- [ ] Step 4: `cd frontend && npm run test:unit -- EngineChip` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/EngineChip.vue frontend/src/composables/audio/useEngineCopy.ts frontend/src/components/audio/__tests__/EngineChip.spec.ts
  git commit -m "feat(tts/fe): EngineChip + useEngineCopy"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- EngineChip -v` — 3 passed

---

#### C9: `TtsPlayButton.vue` — slots into ReaderHeader

**Goal:** Play button injects via `<slot name="actions">`; disabled with tooltip when section has no summary.
**Spec refs:** FR-61
**Wireframe refs:** `01_reader-section-player_desktop-web.html`

**Files:**
- Create: `frontend/src/components/audio/TtsPlayButton.vue`
- Modify: `frontend/src/components/reader/ReaderHeader.vue` (no behavior change — just verify the slot consumer renders)
- Test: `frontend/src/components/audio/__tests__/TtsPlayButton.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders enabled when section has summary', () => {
    const wrap = mount(TtsPlayButton, { props: { contentType: 'section_summary', contentId: 42, hasSummary: true } });
    const btn = wrap.find('button');
    expect(btn.attributes('disabled')).toBeUndefined();
  });
  it('renders disabled with tooltip when no summary', () => {
    const wrap = mount(TtsPlayButton, { props: { hasSummary: false } });
    const btn = wrap.find('button');
    expect(btn.attributes('aria-disabled')).toBe('true');
    expect(btn.attributes('title')).toContain('Audio is only generated for summaries');
  });
  it('clicking calls store.open with the right content', async () => {
    const store = useTtsPlayerStore();
    const spy = vi.spyOn(store, 'open');
    const wrap = mount(TtsPlayButton, { props: { contentType: 'section_summary', contentId: 42, hasSummary: true } });
    await wrap.find('button').trigger('click');
    expect(spy).toHaveBeenCalledWith({ contentType: 'section_summary', contentId: 42 });
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- TtsPlayButton` → expect FAIL.
- [ ] Step 3: Author component. Use Heroicons play SVG. Inject via `BookDetailView.vue` consumer of `<ReaderHeader><template #actions><TtsPlayButton ... /></template>`.
- [ ] Step 4: `cd frontend && npm run test:unit -- TtsPlayButton` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/TtsPlayButton.vue frontend/src/views/BookDetailView.vue frontend/src/components/audio/__tests__/TtsPlayButton.spec.ts
  git commit -m "feat(tts/fe): TtsPlayButton in ReaderHeader actions slot"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- TtsPlayButton -v` — 3 passed

---

#### C10: `MarkdownRenderer.vue` sentence-wrap pass

**Goal:** Wrap each sentence in `<span class="bc-sentence" data-sentence-index="N">` after markdown parsing; per-block wrappers (one wrapper per `<p>`/`<li>`/etc.).
**Spec refs:** FR-13, FR-14, FR-15
**Wireframe refs:** `01_reader-section-player_desktop-web.html` (playing-with-highlight state)

**Files:**
- Modify: `frontend/src/components/reader/MarkdownRenderer.vue`
- Test: `frontend/src/components/reader/__tests__/MarkdownRenderer.sentence.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('wraps sentences with data-sentence-index', () => {
    const wrap = mount(MarkdownRenderer, { props: { md: 'First. Second. Third.', sentenceOffsetsChars: [0, 7, 15] } });
    const sentences = wrap.findAll('span.bc-sentence');
    expect(sentences).toHaveLength(3);
    expect(sentences[0].attributes('data-sentence-index')).toBe('0');
    expect(sentences[2].attributes('data-sentence-index')).toBe('2');
  });
  it('does not span across block boundaries', () => {
    const md = 'First.\n\nSecond.';  // two paragraphs
    const wrap = mount(MarkdownRenderer, { props: { md, sentenceOffsetsChars: [0, 7] } });
    const paragraphs = wrap.findAll('p');
    expect(paragraphs[0].findAll('span.bc-sentence')).toHaveLength(1);
    expect(paragraphs[1].findAll('span.bc-sentence')).toHaveLength(1);
  });
  it('applies bc-sentence-active to current sentenceIndex', () => {
    const store = useTtsPlayerStore();
    store.sentenceIndex = 1;
    const wrap = mount(MarkdownRenderer, { props: { md: 'A. B. C.', sentenceOffsetsChars: [0, 3, 6] } });
    const active = wrap.find('span.bc-sentence-active');
    expect(active.attributes('data-sentence-index')).toBe('1');
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "MarkdownRenderer.sentence"` → expect FAIL.
- [ ] Step 3: Add post-render pass: after markdown-it produces HTML, walk the DOM (use `DOMParser`); for each block-level element (`p, li, blockquote, h1-h6`), iterate text nodes and wrap text within sentence boundaries. Sentence boundaries: each char-offset boundary in `sentenceOffsetsChars` (text-content-cumulative). For each block, only wrap text that falls in that block. Apply `bc-sentence-active` class via reactive watcher on `store.sentenceIndex`.
- [ ] Step 4: `cd frontend && npm run test:unit -- "MarkdownRenderer.sentence"` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/reader/MarkdownRenderer.vue frontend/src/components/reader/__tests__/MarkdownRenderer.sentence.spec.ts
  git commit -m "feat(tts/fe): MarkdownRenderer sentence-wrap pass with block-boundary awareness"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "MarkdownRenderer.sentence" -v` — 3 passed

---

#### C11: Resume affordance — `<ResumeAffordance.vue>`

**Goal:** "Resume from sentence X / Start" CTA on default load when audio_status='complete' and a position exists.
**Spec refs:** FR-40
**Wireframe refs:** `01_reader-section-player_desktop-web.html` (paused-with-resume state)

**Files:**
- Create: `frontend/src/components/audio/ResumeAffordance.vue`
- Test: `frontend/src/components/audio/__tests__/ResumeAffordance.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('shows resume + start when position exists and audio complete', async () => {
    fetchMock.mockResolvedValue({ sentence_index: 16, has_other_browser: false });
    const wrap = mount(ResumeAffordance, { props: { contentType: 'section_summary', contentId: 42, audioStatus: 'complete', totalSentences: 47 } });
    await flushPromises();
    expect(wrap.text()).toContain('Resume from sentence 17 of 47');
    expect(wrap.find('[data-testid="start-from-beginning"]').exists()).toBe(true);
  });
  it('hides when no position', async () => {
    fetchMock.mockResolvedValue({ status: 404 });
    const wrap = mount(ResumeAffordance, { props: { ... } });
    await flushPromises();
    expect(wrap.html()).toBe('<!---->');
  });
  it('shows other-browser hint when has_other_browser', async () => {
    fetchMock.mockResolvedValue({ sentence_index: 16, has_other_browser: true,
                                   other_browser_updated_at: '2026-05-01T22:10:00Z' });
    const wrap = mount(ResumeAffordance, {...});
    await flushPromises();
    expect(wrap.text()).toContain('last listened on a different browser');
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- ResumeAffordance` → expect FAIL.
- [ ] Step 3: Author component; uses `useAudioApiError` for failure. Per FR-39 wording "from this browser" / "different browser".
- [ ] Step 4: `cd frontend && npm run test:unit -- ResumeAffordance` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/ResumeAffordance.vue frontend/src/components/audio/__tests__/ResumeAffordance.spec.ts
  git commit -m "feat(tts/fe): ResumeAffordance with cross-browser hint"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- ResumeAffordance -v` — 3 passed

---

#### C12: BroadcastChannel — single playing source per browser

**Goal:** Opening playback in tab B sends a message that pauses tab A.
**Spec refs:** FR-35

**Files:**
- Modify: `frontend/src/composables/audio/useTtsEngine.ts`
- Test: `frontend/src/composables/audio/__tests__/broadcastChannel.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('opening in tab B sends pause message; tab A receives and pauses', async () => {
    const tabA = useTtsEngine();
    const tabB = useTtsEngine();
    const aEng = await tabA.load({...});
    aEng.play();
    await tabB.load({...});  // opens new
    // Tab A receives broadcast and pauses
    expect(aEng.paused).toBe(true);
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- broadcastChannel` → expect FAIL.
- [ ] Step 3: Add `BroadcastChannel('bc-tts-player')` in `useTtsEngine`; on `load`, broadcast `{type: 'opening', tabId}`; listen for `opening` from other tabs and pause local engine if the other tabId differs.
- [ ] Step 4: `cd frontend && npm run test:unit -- broadcastChannel` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/useTtsEngine.ts frontend/src/composables/audio/__tests__/broadcastChannel.spec.ts
  git commit -m "feat(tts/fe): BroadcastChannel single-source-per-browser"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- broadcastChannel -v` — 1 passed

---

#### C13: Keybinding precedence — audio active vs section nav

**Goal:** When `playerStore.isActive`, ArrowLeft/ArrowRight skip sentences; otherwise revert to existing section nav.
**Spec refs:** FR-36, D25

**Files:**
- Modify: `frontend/src/components/reader/ReadingArea.vue:21-23`
- Test: `frontend/src/components/reader/__tests__/ReadingArea.keybindings.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('ArrowLeft skips sentence when player active', async () => {
    const store = useTtsPlayerStore();
    store.isActive = true; store.sentenceIndex = 5;
    const wrap = mount(ReadingArea, {...});
    await wrap.trigger('keydown', { key: 'ArrowLeft' });
    expect(store.sentenceIndex).toBe(4);
  });
  it('ArrowLeft navigates to previous section when player inactive', async () => {
    const store = useTtsPlayerStore();
    store.isActive = false;
    const navSpy = vi.fn();
    const wrap = mount(ReadingArea, { props: { onPrevSection: navSpy } });
    await wrap.trigger('keydown', { key: 'ArrowLeft' });
    expect(navSpy).toHaveBeenCalled();
  });
  it('Space toggles play/pause regardless', async () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "ReadingArea.keybindings"` → expect FAIL.
- [ ] Step 3: Modify keybinding handler to branch on `useTtsPlayerStore().isActive`.
- [ ] Step 4: `cd frontend && npm run test:unit -- "ReadingArea.keybindings"` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/reader/ReadingArea.vue frontend/src/components/reader/__tests__/ReadingArea.keybindings.spec.ts
  git commit -m "feat(tts/fe): keybinding precedence audio-active vs section-nav"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "ReadingArea.keybindings" -v` — 3 passed

---

#### C14: `StaleSourceBanner.vue` — three reason variants

**Goal:** Banner copy varies by `stale_reason` (`source_changed` | `sanitizer_upgraded` | `segmenter_drift`); offers Regenerate.
**Spec refs:** FR-12a, FR-62
**Wireframe refs:** `01_reader-section-player_desktop-web.html` (stale-source-banner state)

**Files:**
- Create: `frontend/src/components/audio/StaleSourceBanner.vue`
- Test: `frontend/src/components/audio/__tests__/StaleSourceBanner.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it.each([
    ['source_changed', 'Source updated since audio generated'],
    ['sanitizer_upgraded', 'Audio engine updated'],
    ['segmenter_drift', 'Sentence boundaries shifted'],
  ])('renders correct copy for stale_reason=%s', (reason, expected) => {
    const wrap = mount(StaleSourceBanner, { props: { staleReason: reason } });
    expect(wrap.text()).toContain(expected);
  });
  it('Regenerate click queues audio job', async () => {
    fetchMock.mockResolvedValueOnce({ status: 202, body: { job_id: 187 } });
    const wrap = mount(StaleSourceBanner, { props: { staleReason: 'source_changed', bookId: 1, contentType: 'section_summary', contentId: 42 } });
    await wrap.find('button[data-testid="regenerate"]').trigger('click');
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/audio'), expect.objectContaining({ method: 'POST' }));
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- StaleSourceBanner` → expect FAIL.
- [ ] Step 3: Author component using `bc-banner` per DESIGN.md (warning amber tint). Three copy variants per FR-12a.
- [ ] Step 4: `cd frontend && npm run test:unit -- StaleSourceBanner` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/StaleSourceBanner.vue frontend/src/components/audio/__tests__/StaleSourceBanner.spec.ts
  git commit -m "feat(tts/fe): StaleSourceBanner with 3 stale_reason variants"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- StaleSourceBanner -v` — 4 passed

---

#### C15: Mid-listen summary regen banner

**Goal:** When SSE indicates summary regen completed for currently-playing content, banner appears at next pause / section boundary; player completes current section first (D13).
**Spec refs:** FR-63, D13
**Wireframe refs:** `01_reader-section-player_desktop-web.html` (mid-listen-regen-banner state)

**Files:**
- Modify: `frontend/src/stores/ttsPlayer.ts` (add `pendingRegenBanner` flag)
- Modify: `frontend/src/components/audio/Playbar.vue` (consume flag)
- Test: `frontend/src/components/audio/__tests__/Playbar.midListenRegen.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('shows mid-listen regen banner when pendingRegenBanner true and status=paused', async () => {
    const store = useTtsPlayerStore();
    Object.assign(store, { isActive: true, status: 'paused', pendingRegenBanner: true });
    const wrap = mount(Playbar);
    expect(wrap.text()).toContain('Summary updated since this audio was generated');
  });
  it('does not show banner mid-section playback', async () => {
    const store = useTtsPlayerStore();
    Object.assign(store, { isActive: true, status: 'playing', pendingRegenBanner: true });
    const wrap = mount(Playbar);
    expect(wrap.text()).not.toContain('Summary updated since');
  });
  it('SSE summary_regenerated for current section sets pendingRegenBanner', async () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- Playbar.midListenRegen` → expect FAIL.
- [ ] Step 3: Subscribe to existing `summary_regenerated` SSE; if matches current play target, set `store.pendingRegenBanner = true`. Banner only renders when `status in ('paused', 'idle')` OR section-end fired.
- [ ] Step 4: `cd frontend && npm run test:unit -- Playbar.midListenRegen` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/stores/ttsPlayer.ts frontend/src/components/audio/Playbar.vue frontend/src/components/audio/__tests__/Playbar.midListenRegen.spec.ts
  git commit -m "feat(tts/fe): mid-listen summary-regen banner deferred to section boundary"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- Playbar.midListenRegen -v` — 3 passed

---

### Phase D — Audio tab + Generate modal (D1–D8)

#### D1: Extend `BookOverviewView.vue` from 3 to 5 tabs

**Goal:** Tab strip now `Overview | Summary | Sections | Audio | Annotations`. New tabs render placeholder text until D2/E1 mount real content.
**Spec refs:** FR-57
**Wireframe refs:** `03_book-detail-audio_desktop-web.html`, `06_annotations-player_desktop-web.html`

**Files:**
- Modify: `frontend/src/views/BookOverviewView.vue:87-122`
- Test: `frontend/src/views/__tests__/BookOverviewView.tabs.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders 5 tabs', () => {
    const wrap = mount(BookOverviewView, { props: { bookId: 1 } });
    const tabs = wrap.findAll('[role="tab"]');
    expect(tabs.map(t => t.text())).toEqual(['Overview', 'Summary', 'Sections', 'Audio', 'Annotations']);
  });
  it('clicking Audio tab activates it', async () => {
    const wrap = mount(BookOverviewView, { props: { bookId: 1 } });
    await wrap.findAll('[role="tab"]')[3].trigger('click');
    expect(wrap.find('[data-tab="audio"][aria-selected="true"]').exists()).toBe(true);
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "BookOverviewView.tabs"` → expect FAIL.
- [ ] Step 3: Modify the `v-for` array `['overview', 'summary', 'sections']` → `['overview', 'summary', 'sections', 'audio', 'annotations']`. **Tabs are URL-bound** per spec §11.1 — each tab maps to a child route in `frontend/src/router/index.ts`: `#/books/:id/overview`, `/summary`, `/sections`, `/audio`, `/annotations`. Update the existing book-detail router config to add `audio` and `annotations` children (same pattern as the existing 3 tabs). Tab clicks call `router.push({name: 'book-{tab}', params: {id}})`. Hard-reloading any of these URLs lands on the matching tab content (verified in TN). Add tab-content placeholders that render `<AudioTab>` (D2) and `<AnnotationsTab>` (E1) — for now, `<div>Audio tab placeholder</div>` so test passes; D2/E1 replace.
- [ ] Step 4: `cd frontend && npm run test:unit -- "BookOverviewView.tabs"` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/views/BookOverviewView.vue frontend/src/views/__tests__/BookOverviewView.tabs.spec.ts
  git commit -m "feat(tts/fe): BookOverviewView 5-tab strip"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "BookOverviewView.tabs" -v` — 2 passed

---

#### D2: `audioJob.ts` Pinia store + `AudioTab.vue` (4 states)

**Goal:** Audio tab renders `no-audio | partial | full | generating` states from inventory + job stream.
**Spec refs:** FR-58
**Wireframe refs:** `03_book-detail-audio_desktop-web.html` (4 states), `03_book-detail-audio_mobile-web.html`

**Files:**
- Create: `frontend/src/stores/audioJob.ts`
- Create: `frontend/src/components/audio/AudioTab.vue`
- Test: `frontend/src/components/audio/__tests__/AudioTab.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders no-audio state with Generate CTA when inventory empty', async () => {
    fetchMock.mockResolvedValue({ files: [], coverage: { total: 47, generated: 0, stale: 0 } });
    const wrap = mount(AudioTab, { props: { bookId: 1 } });
    await flushPromises();
    expect(wrap.text()).toContain('No audio yet');
    expect(wrap.find('button[data-testid="generate-audio"]').exists()).toBe(true);
  });
  it('renders partial state with coverage bar', async () => {
    fetchMock.mockResolvedValue({ files: [...3 rows], coverage: { total: 47, generated: 12, stale: 1 } });
    const wrap = mount(AudioTab, { props: { bookId: 1 } });
    await flushPromises();
    expect(wrap.text()).toContain('12 of 47 generated');
    expect(wrap.find('[data-testid="coverage-bar"]').exists()).toBe(true);
  });
  it('renders full state', async () => {
    fetchMock.mockResolvedValue({ files: [...47 rows], coverage: { total: 47, generated: 47, stale: 0 } });
    const wrap = mount(AudioTab, { props: { bookId: 1 } });
    await flushPromises();
    expect(wrap.text()).toContain('All 47 sections have audio');
  });
  it('renders generating state with progress + Cancel button', async () => {
    const jobStore = useAudioJobStore();
    jobStore.activeJob = { id: 187, completed: 12, total: 47, status: 'RUNNING' };
    const wrap = mount(AudioTab, { props: { bookId: 1 } });
    expect(wrap.text()).toContain('12 / 47');
    expect(wrap.find('button[data-testid="cancel-job"]').exists()).toBe(true);
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- AudioTab` → expect FAIL.
- [ ] Step 3: Implement `audioJob.ts` store with `activeJob`, `lastEventAt`, `apply(event)`. Implement `AudioTab.vue` reading inventory via `GET /audio` + audioJob store. Use `CoverageBar` and existing `ProcessingBar` patterns.
- [ ] Step 4: `cd frontend && npm run test:unit -- AudioTab` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/stores/audioJob.ts frontend/src/components/audio/AudioTab.vue frontend/src/components/audio/__tests__/AudioTab.spec.ts
  git commit -m "feat(tts/fe): AudioTab + audioJob store with 4 states"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- AudioTab -v` — 4 passed

---

#### D3: `AudioFileRow.vue` — Play / Download / Delete (per-row)

**Goal:** Per-row controls; Delete is trash icon + type-to-confirm; 409 on delete shows toast "Wait or cancel job".
**Spec refs:** FR-58, FR-25
**Wireframe refs:** `03_book-detail-audio_desktop-web.html`

**Files:**
- Create: `frontend/src/components/audio/AudioFileRow.vue`
- Test: `frontend/src/components/audio/__tests__/AudioFileRow.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders Play | Download | Delete', () => {
    const wrap = mount(AudioFileRow, { props: { file: SAMPLE_AUDIO_FILE } });
    expect(wrap.find('[data-testid="play"]').exists()).toBe(true);
    expect(wrap.find('a[data-testid="download"]').attributes('href')).toBe('/api/v1/.../42.mp3');
    expect(wrap.find('button[data-testid="delete-row"]').exists()).toBe(true);
  });
  it('Delete prompts type-to-confirm', async () => { ... });
  it('Delete calls DELETE endpoint then emits removed', async () => {
    fetchMock.mockResolvedValueOnce({ status: 204 });
    const wrap = mount(AudioFileRow, { ... });
    await deleteRow(wrap);
    expect(wrap.emitted().removed).toBeTruthy();
  });
  it('Delete 409 shows toast and does NOT emit removed', async () => {
    fetchMock.mockResolvedValueOnce({ status: 409, body: { detail: 'Wait or cancel job 187' } });
    const wrap = mount(AudioFileRow, { ... });
    await deleteRow(wrap);
    expect(wrap.emitted().removed).toBeFalsy();
    expect(toastSpy).toHaveBeenCalled();
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- AudioFileRow` → expect FAIL.
- [ ] Step 3: Author component. Trash glyph from prototype-driven decision (🗑 — actually use Heroicon trash SVG). Type-to-confirm via existing ConfirmDialog with `destructive` variant.
- [ ] Step 4: `cd frontend && npm run test:unit -- AudioFileRow` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/AudioFileRow.vue frontend/src/components/audio/__tests__/AudioFileRow.spec.ts
  git commit -m "feat(tts/fe): AudioFileRow with Play/Download/Delete"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- AudioFileRow -v` — 4 passed

---

#### D4: `useGenerateCost.ts` composable

**Goal:** Cost estimator returns `{minutes, megabytes}` from section count + flags.
**Spec refs:** FR-60

**Files:**
- Create: `frontend/src/composables/audio/useGenerateCost.ts`
- Test: `frontend/src/composables/audio/__tests__/useGenerateCost.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('returns expected estimate for 47 sections', () => {
    const { minutes, megabytes } = estimateGenerateCost({ totalUnits: 47 });
    expect(minutes).toBeCloseTo(47 * 0.20);  // ~9.4 min — formula: total_units × 0.20
    expect(megabytes).toBe(47 * 3.0);  // 141
  });
  it('returns zeros for zero units', () => {
    expect(estimateGenerateCost({ totalUnits: 0 })).toEqual({ minutes: 0, megabytes: 0 });
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- useGenerateCost` → expect FAIL.
- [ ] Step 3: Implement composable per spec FR-60: `minutes = total_units * 0.20`, `megabytes = total_units * 3.0`.
- [ ] Step 4: `cd frontend && npm run test:unit -- useGenerateCost` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/useGenerateCost.ts frontend/src/composables/audio/__tests__/useGenerateCost.spec.ts
  git commit -m "feat(tts/fe): useGenerateCost composable"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useGenerateCost -v` — 2 passed

---

#### D5: `GenerateAudioModal.vue` (3 states)

**Goal:** Modal with 3 checkboxes (summary/book/annotations) defaulted ON, voice picker with sample, cost preview, model-download-required + error states. Joins in-flight job on 409.
**Spec refs:** FR-60, S2 (annotations default ON), GS-7
**Wireframe refs:** `04_generate-audio-modal_desktop-web.html` (3 states), `04_generate-audio-modal_mobile-web.html`

**Files:**
- Create: `frontend/src/components/audio/GenerateAudioModal.vue`
- Test: `frontend/src/components/audio/__tests__/GenerateAudioModal.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('default state has 3 checkboxes all ON', () => {
    const wrap = mount(GenerateAudioModal, { props: { bookId: 1, totalUnits: 47 } });
    const checkboxes = wrap.findAll('input[type="checkbox"]');
    expect(checkboxes.every(c => c.element.checked)).toBe(true);
    expect(wrap.text()).toContain('Annotations');
    expect(wrap.text()).toContain('recommended');  // S2 pill
  });
  it('shows cost estimate inline', () => {
    const wrap = mount(GenerateAudioModal, { props: { bookId: 1, totalUnits: 47 } });
    expect(wrap.text()).toMatch(/~\d+ min · ~\d+ MB for 47 sections/);
  });
  it('confirm POSTs to /audio and joins job on 202', async () => {
    fetchMock.mockResolvedValue({ status: 202, body: { job_id: 187, total_units: 47 } });
    const wrap = mount(GenerateAudioModal, { ... });
    await wrap.find('button[data-testid="confirm"]').trigger('click');
    expect(useAudioJobStore().activeJob.id).toBe(187);
  });
  it('409 transparently joins existing job (no error toast)', async () => {
    fetchMock.mockResolvedValueOnce({ status: 409, body: { error: 'audio_job_in_progress', existing_job_id: 187, scope: 'all', started_at: '2026-05-02T14:11:00Z' } });
    const wrap = mount(GenerateAudioModal, { ... });
    const toastSpy = vi.fn();
    await wrap.find('button[data-testid="confirm"]').trigger('click');
    expect(toastSpy).not.toHaveBeenCalled();
    expect(useAudioJobStore().activeJob.id).toBe(187);
  });
  it('renders model-download-required state', () => {
    const wrap = mount(GenerateAudioModal, { props: { ..., kokoroStatus: 'not_downloaded' } });
    expect(wrap.text()).toContain('Download voice model? (~80 MB, one-time)');
    expect(wrap.find('button[data-testid="download-model"]').exists()).toBe(true);
  });
  it('renders error state on 503', async () => {
    fetchMock.mockResolvedValueOnce({ status: 503, body: { error: 'ffmpeg_missing' } });
    const wrap = mount(GenerateAudioModal, { ... });
    await wrap.find('button[data-testid="confirm"]').trigger('click');
    expect(wrap.text()).toContain('ffmpeg required');
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- GenerateAudioModal` → expect FAIL.
- [ ] Step 3: Author component. Default-ON checkboxes; "recommended" pill on Annotations row (S2). Voice picker filtered by current `engine === 'kokoro'`; Web Speech-only note inline (FR-60). Use ConfirmDialog backbone (DESIGN.md modal centered shape). Cost preview via `useGenerateCost`. 409 self-heals — joins existing_job_id without toast.
- [ ] Step 4: `cd frontend && npm run test:unit -- GenerateAudioModal` → expect 6 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/GenerateAudioModal.vue frontend/src/components/audio/__tests__/GenerateAudioModal.spec.ts
  git commit -m "feat(tts/fe): GenerateAudioModal with 3 states + 409 self-heal"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- GenerateAudioModal -v` — 6 passed

---

#### D6: `useBufferedJobStream.ts` 5-step reconnect contract

**Goal:** Subscribe → buffer → fetch snapshot → reconcile → live, applied on every connect AND reconnect.
**Spec refs:** FR-21a

**Files:**
- Modify: `frontend/src/composables/useBufferedJobStream.ts:29-121`
- Test: `frontend/src/composables/__tests__/useBufferedJobStream.reconnect.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('5-step sequence on initial connect', async () => {
    const events = []; const fetchSpy = vi.fn(async () => ({ progress: { completed: 5, total: 47, last_event_at: 100 }, sections: [] }));
    const stream = useBufferedJobStream({ jobId: 187, fetch: fetchSpy });
    es.dispatchMessage({ data: JSON.stringify({ type: 'section_audio_completed', last_event_at: 50 }) });  // before snapshot
    es.dispatchMessage({ data: JSON.stringify({ type: 'section_audio_completed', last_event_at: 110 }) }); // after snapshot
    await stream.connect();
    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(stream.state.completed).toBe(5);  // from snapshot, not the buffered <100 event
    // Drain phase: only the >100 event applied
    expect(stream.appliedEvents).toEqual([{ type: 'section_audio_completed', last_event_at: 110 }]);
  });
  it('5-step sequence on reconnect after disconnect', async () => {
    const stream = useBufferedJobStream({ jobId: 187 });
    await stream.connect();
    es.simulateError();
    await stream.reconnect();
    // fetchSpy called twice now (initial + reconnect)
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
  it('drops events with last_event_at <= snapshot.last_event_at', async () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "useBufferedJobStream.reconnect"` → expect FAIL.
- [ ] Step 3: Modify composable per FR-21a — internal status `connecting → fetching → live`; buffer events while not `live`; after snapshot, drain buffer dropping `last_event_at <= snapshot.last_event_at`. On EventSource error, exponential backoff and rerun.
- [ ] Step 4: `cd frontend && npm run test:unit -- "useBufferedJobStream.reconnect"` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/useBufferedJobStream.ts frontend/src/composables/__tests__/useBufferedJobStream.reconnect.spec.ts
  git commit -m "feat(tts/fe): 5-step subscribe-buffer-fetch-reconcile-live SSE contract"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- useBufferedJobStream -v` — all green

---

#### D7: `ProcessingBar` extension for AUDIO step

**Goal:** Sticky job-progress strip recognizes `step=audio` jobs; shows kind/ref + already_stale counter.
**Spec refs:** FR-58, FR-21
**Wireframe refs:** `docs/wireframes/2026-05-02-audiobook-mode/03_book-detail-audio_desktop-web.html` (generating state — top-of-page progress strip is consistent with the existing app shell ProcessingBar pattern)

**Files:**
- Modify: `frontend/src/components/app/ProcessingBar.vue`
- Test: `frontend/src/components/app/__tests__/ProcessingBar.audio.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders audio job with current section title', () => {
    const wrap = mount(ProcessingBar, { props: { job: { step: 'audio', progress: { completed: 12, total: 47, current_kind: 'section_summary', current_ref: '42', already_stale: 1 } } } });
    expect(wrap.text()).toContain('Generating audio');
    expect(wrap.text()).toContain('12 / 47');
    expect(wrap.text()).toContain('1 already stale');
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "ProcessingBar.audio"` → expect FAIL.
- [ ] Step 3: Add `step=audio` branch in ProcessingBar render; wire copy.
- [ ] Step 4: `cd frontend && npm run test:unit -- "ProcessingBar.audio"` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/app/ProcessingBar.vue frontend/src/components/app/__tests__/ProcessingBar.audio.spec.ts
  git commit -m "feat(tts/fe): ProcessingBar audio job rendering"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "ProcessingBar.audio" -v` — 1 passed

---

#### D8: Cancel-job UI on Audio tab + Sections tab

**Goal:** RUNNING audio jobs expose `Cancel` button on Audio tab + Sections tab generating row.
**Spec refs:** FR-25a
**Wireframe refs:** `03_book-detail-audio_desktop-web.html` (generating state), `08_sections-tab-audio_desktop-web.html`

**Files:**
- Modify: `frontend/src/components/audio/AudioTab.vue`
- Modify: `frontend/src/components/audio/SectionsAudioRow.vue` (created in E4)
- Test: `frontend/src/components/audio/__tests__/AudioTab.cancel.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('Cancel button calls POST /jobs/{id}/cancel', async () => {
    const jobStore = useAudioJobStore();
    jobStore.activeJob = { id: 187, status: 'RUNNING' };
    fetchMock.mockResolvedValueOnce({ status: 200 });
    const wrap = mount(AudioTab, { props: { bookId: 1 } });
    await wrap.find('button[data-testid="cancel-job"]').trigger('click');
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/jobs/187/cancel'), expect.objectContaining({ method: 'POST' }));
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "AudioTab.cancel"` → expect FAIL.
- [ ] Step 3: Add Cancel button to generating state of AudioTab; click handler calls existing `/api/v1/jobs/{id}/cancel`. Show confirm-cancel ConfirmDialog (non-destructive, since data is preserved).
- [ ] Step 4: `cd frontend && npm run test:unit -- "AudioTab.cancel"` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/AudioTab.vue frontend/src/components/audio/__tests__/AudioTab.cancel.spec.ts
  git commit -m "feat(tts/fe): Cancel-job UI on Audio tab"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "AudioTab.cancel" -v` — 1 passed

---

### Phase E — Annotations + Sections audio (E1–E7)

#### E1: `AnnotationsTab.vue` — wraps existing /annotations + Play-as-audio

**Goal:** Annotations tab (new) on BookOverviewView wraps existing per-book annotation UI plus a Play-as-audio CTA.
**Spec refs:** FR-57
**Wireframe refs:** `06_annotations-player_desktop-web.html` (default-list state), `06_annotations-player_mobile-web.html`

**Files:**
- Create: `frontend/src/components/audio/AnnotationsTab.vue`
- Test: `frontend/src/components/audio/__tests__/AnnotationsTab.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders Play-as-audio CTA when book has highlights', async () => {
    fetchMock.mockResolvedValue({ annotations: SAMPLE_3_HIGHLIGHTS });
    const wrap = mount(AnnotationsTab, { props: { bookId: 1 } });
    await flushPromises();
    expect(wrap.find('button[data-testid="play-all-annotations"]').exists()).toBe(true);
    expect(wrap.text()).toMatch(/~\d+ min · 3 highlights/);
  });
  it('hides Play-as-audio when zero highlights', async () => {
    fetchMock.mockResolvedValue({ annotations: [] });
    const wrap = mount(AnnotationsTab, { props: { bookId: 1 } });
    await flushPromises();
    expect(wrap.find('button[data-testid="play-all-annotations"]').exists()).toBe(false);
    expect(wrap.text()).toContain('No highlights yet');
  });
  it('clicking Play-as-audio opens annotations playlist mode', async () => {
    const store = useTtsPlayerStore();
    const spy = vi.spyOn(store, 'open');
    const wrap = mount(AnnotationsTab, { props: { bookId: 1 } });
    await flushPromises();
    await wrap.find('button[data-testid="play-all-annotations"]').trigger('click');
    expect(spy).toHaveBeenCalledWith({ contentType: 'annotations_playlist', contentId: 1 });
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- AnnotationsTab` → expect FAIL.
- [ ] Step 3: Author component. Use `usePlaylistMinutes` (next task) for cost preview.
- [ ] Step 4: `cd frontend && npm run test:unit -- AnnotationsTab` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/AnnotationsTab.vue frontend/src/components/audio/__tests__/AnnotationsTab.spec.ts
  git commit -m "feat(tts/fe): AnnotationsTab with Play-as-audio CTA"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- AnnotationsTab -v` — 3 passed

---

#### E2: `usePlaylistMinutes.ts` helper

**Goal:** Shared `estimatePlaylistMinutes(highlights, notes)` returning ceil minutes.
**Spec refs:** FR-60a

**Files:**
- Create: `frontend/src/composables/audio/usePlaylistMinutes.ts`
- Test: `frontend/src/composables/audio/__tests__/usePlaylistMinutes.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('formula = ceil((highlights*30 + notes*30)/60)', () => {
    expect(estimatePlaylistMinutes(18, 6)).toBe(Math.ceil((18*30 + 6*30) / 60));  // 12
    expect(estimatePlaylistMinutes(0, 0)).toBe(0);
    expect(estimatePlaylistMinutes(1, 0)).toBe(1);  // ceil(0.5)
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- usePlaylistMinutes` → expect FAIL.
- [ ] Step 3: Implement per FR-60a.
- [ ] Step 4: `cd frontend && npm run test:unit -- usePlaylistMinutes` → expect 1 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/usePlaylistMinutes.ts frontend/src/composables/audio/__tests__/usePlaylistMinutes.spec.ts
  git commit -m "feat(tts/fe): usePlaylistMinutes helper"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- usePlaylistMinutes -v` — 1 passed

---

#### E3: `AnnotationPlaylistRow.vue` — annotation card with audible cue

**Goal:** Annotation row visualizes `♪ pause` divider + tone-shift cue between highlight and note (MSF N4).
**Spec refs:** FR-54, MSF N4
**Wireframe refs:** `06_annotations-player_desktop-web.html` (playing state)

**Files:**
- Create: `frontend/src/components/audio/AnnotationPlaylistRow.vue`
- Test: `frontend/src/components/audio/__tests__/AnnotationPlaylistRow.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders highlight + ♪ divider + note when annotation has note', () => {
    const wrap = mount(AnnotationPlaylistRow, { props: { annotation: { selected_text: 'highlighted text', note: 'my thought' } } });
    expect(wrap.text()).toContain('highlighted text');
    expect(wrap.find('[data-testid="audible-cue"]').exists()).toBe(true);
    expect(wrap.text()).toContain('my thought');
  });
  it('hides cue when no note', () => {
    const wrap = mount(AnnotationPlaylistRow, { props: { annotation: { selected_text: 'just hl', note: null } } });
    expect(wrap.find('[data-testid="audible-cue"]').exists()).toBe(false);
  });
  it('applies bc-sentence-active to currently-playing row', () => {
    const wrap = mount(AnnotationPlaylistRow, { props: { annotation: {...}, isActive: true } });
    expect(wrap.classes()).toContain('bc-sentence-active');
  });
  it('clicking row calls onJumpTo with annotation index', async () => {
    const onJumpTo = vi.fn();
    const wrap = mount(AnnotationPlaylistRow, { props: { annotation: {...}, index: 5, onJumpTo } });
    await wrap.trigger('click');
    expect(onJumpTo).toHaveBeenCalledWith(5);
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- AnnotationPlaylistRow` → expect FAIL.
- [ ] Step 3: Author component with the audible-cue divider (♪ icon, host-app DESIGN.md tokens).
- [ ] Step 4: `cd frontend && npm run test:unit -- AnnotationPlaylistRow` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/AnnotationPlaylistRow.vue frontend/src/components/audio/__tests__/AnnotationPlaylistRow.spec.ts
  git commit -m "feat(tts/fe): AnnotationPlaylistRow with audible-cue divider"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- AnnotationPlaylistRow -v` — 4 passed

---

#### E4: Sections tab audio columns + per-row actions

**Goal:** Sections tab gains audio-status pill + per-row Play / Regenerate / Delete; bulk-actions; stale filter.
**Spec refs:** FR-59
**Wireframe refs:** `08_sections-tab-audio_desktop-web.html` (3 states), `08_sections-tab-audio_mobile-web.html`

**Files:**
- Create: `frontend/src/components/audio/SectionsAudioRow.vue`
- Modify: `frontend/src/components/sections/SectionsTab.vue` (existing — extends columns)
- Test: `frontend/src/components/audio/__tests__/SectionsAudioRow.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders status pill: none | ready | stale | generating', () => {
    for (const status of ['none', 'ready', 'stale', 'generating']) {
      const wrap = mount(SectionsAudioRow, { props: { sectionId: 42, audioStatus: status } });
      expect(wrap.find(`[data-testid="audio-status-${status}"]`).exists()).toBe(true);
    }
  });
  it('Play button visible only when status=ready or stale', () => { ... });
  it('Regenerate visible when status=stale', () => { ... });
  it('Delete-row visible when status=ready', () => { ... });
  it('bulk-actions toolbar shows when 2+ rows selected', () => { ... });
  it('stale filter hides ready rows', () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- SectionsAudioRow` → expect FAIL.
- [ ] Step 3: Author row component; extend SectionsTab to include audio columns + filter dropdown + bulk-action toolbar (per wireframe 08).
- [ ] Step 4: `cd frontend && npm run test:unit -- SectionsAudioRow` → expect 6 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/audio/SectionsAudioRow.vue frontend/src/components/sections/SectionsTab.vue frontend/src/components/audio/__tests__/SectionsAudioRow.spec.ts
  git commit -m "feat(tts/fe): SectionsTab audio columns + per-row actions"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- SectionsAudioRow -v` — 6 passed

---

#### E5: Annotations playlist content shape — span + 0.5s pause + note

**Goal:** Worker generates annotations playlist as: per-highlight span synthesized → 0.5s silence (numpy zeros) → note synthesized → 0.5s silence between annotations.
**Spec refs:** FR-54, D28

**Files:**
- Modify: `backend/app/services/audio_gen_service.py` — add `generate_annotations_playlist(book_id, voice)` branch
- Test: `backend/tests/integration/test_annotations_playlist_audio.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_annotations_playlist_audio_concatenates_with_silences(svc, seeded_book_with_3_annotations):
      af = await svc.generate_annotations_playlist(book_id=seeded_book.id, voice="af_sarah")
      # 3 annotations × (highlight + pause + note?) → expected sentence count
      # Source has 3 highlights, 2 with notes
      assert af.sentence_count == 5  # 3 highlights + 2 notes
      # Verify 0.5s silence segments are present (audio file >= sum of synthesis + 4 × 0.5s)
      assert af.duration_seconds >= 4 * 0.5

  async def test_annotations_playlist_skips_when_zero_highlights(svc, seeded_empty_book):
      with pytest.raises(EmptySanitizedTextError):
          await svc.generate_annotations_playlist(book_id=seeded_empty_book.id, voice="af_sarah")
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_annotations_playlist_audio.py -v` → expect FAIL.
- [ ] Step 3: Implement `generate_annotations_playlist`: list_by_book → for each annotation, sanitize+synthesize selected_text, append `numpy.zeros(int(0.5 * 24000), dtype=np.float32)` silence, if note synthesize note + same silence; concatenate; ffmpeg-encode; UPSERT AudioFile with `content_type=ANNOTATIONS_PLAYLIST, content_id=book_id`.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_annotations_playlist_audio.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/audio_gen_service.py backend/tests/integration/test_annotations_playlist_audio.py
  git commit -m "feat(tts): annotations playlist audio with silence cues"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_annotations_playlist_audio.py -v` — 2 passed

---

#### E6: Annotations playlist Web Speech runtime (FR-55)

**Goal:** When no pre-gen MP3 exists for `(annotations_playlist, book_id)`, `GET /audio/lookup` returns sanitized concatenation + `pregenerated: false` so the frontend can play via Web Speech.
**Spec refs:** FR-55, OQ-10

**Files:**
- Modify: `backend/app/services/audio_gen_service.py:lookup`
- Test: `backend/tests/integration/test_audio_lookup_annotations.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_lookup_annotations_no_pregen_returns_sanitized_concat(client, seeded_book_with_3_annotations):
      # Book has 3 highlights (2 with notes); NO AudioFile row exists for (annotations_playlist, book_id)
      r = await client.get("/api/v1/audio/lookup",
                           params={"book_id": book.id, "content_type": "annotations_playlist",
                                   "content_id": book.id})
      assert r.status_code == 200
      body = r.json()
      assert body["pregenerated"] is False
      assert body["sanitized_text"] != ""
      # 3 highlights + 2 notes = 5 sentence-shaped units
      assert len(body["sentence_offsets_chars"]) == 5
      assert "highlighted text 1" in body["sanitized_text"]
      assert "my note about hl 1" in body["sanitized_text"]
      # No url / no stale fields when not pre-generated
      assert "url" not in body or body["url"] is None
      assert body.get("stale") is None

  async def test_lookup_annotations_pregen_returns_url_and_stale(client, seeded_book_with_3_annotations_and_audio):
      r = await client.get("/api/v1/audio/lookup",
                           params={"book_id": book.id, "content_type": "annotations_playlist",
                                   "content_id": book.id})
      body = r.json()
      assert body["pregenerated"] is True
      assert body["url"].endswith(".mp3")
      assert body["stale"] is False

  async def test_lookup_annotations_zero_highlights_returns_empty(client, seeded_book_no_annotations):
      r = await client.get("/api/v1/audio/lookup",
                           params={"book_id": book.id, "content_type": "annotations_playlist",
                                   "content_id": book.id})
      body = r.json()
      assert body["pregenerated"] is False
      assert body["sanitized_text"] == ""
      assert body["sentence_offsets_chars"] == []
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_lookup_annotations.py -v` → expect FAIL (lookup currently has no annotations_playlist branch).
- [ ] Step 3: In `audio_gen_service.lookup`, add a branch: when `content_type == ContentType.ANNOTATIONS_PLAYLIST`, fetch annotations via `AnnotationRepository.list_by_book(content_id /* == book_id */)`. Build a synthetic source_md by joining each annotation's `selected_text` and (if present) `note` with `"\n\n"`. Sanitize + segment via `markdown_to_speech.sanitize`. Return `LookupResult` with `pregenerated=False` (or `True` if AudioFile exists), `sanitized_text`, `sentence_offsets_chars` from the segmentation result.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_lookup_annotations.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/audio_gen_service.py backend/tests/integration/test_audio_lookup_annotations.py
  git commit -m "feat(tts): annotations playlist Web Speech runtime fallback in lookup"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_lookup_annotations.py -v` — 3 passed

---

#### E7: Annotations playlist resume-position keying

**Goal:** Position routes accept `content_type=annotations_playlist` and roundtrip `(content_type, content_id=book_id, browser_id)` → `sentence_index` correctly. Sentence index counts across all highlight+note units in playlist order.
**Spec refs:** FR-56

**Files:**
- Modify: `backend/app/api/routes/audio_position.py` (Pydantic enum / Literal accepts the new value)
- Modify: `backend/app/db/repositories/audio_position_repo.py` (CHECK constraint already permits per A3)
- Test: `backend/tests/integration/test_annotations_playlist_resume.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  async def test_put_position_for_annotations_playlist(client, seeded_book):
      r = await client.put("/api/v1/audio_position", json={
          "content_type": "annotations_playlist", "content_id": seeded_book.id,
          "browser_id": "uuid-A", "sentence_index": 12})
      assert r.status_code == 204

  async def test_get_position_for_annotations_playlist(client, seeded_book):
      await client.put("/api/v1/audio_position", json={
          "content_type": "annotations_playlist", "content_id": seeded_book.id,
          "browser_id": "uuid-A", "sentence_index": 12})
      r = await client.get("/api/v1/audio_position",
                           params={"content_type": "annotations_playlist",
                                   "content_id": seeded_book.id, "browser_id": "uuid-A"})
      assert r.status_code == 200
      assert r.json()["sentence_index"] == 12

  async def test_position_independent_per_browser_for_playlist(client, seeded_book):
      await client.put("/api/v1/audio_position", json={
          "content_type": "annotations_playlist", "content_id": seeded_book.id,
          "browser_id": "browser-A", "sentence_index": 5})
      await asyncio.sleep(0.01)
      await client.put("/api/v1/audio_position", json={
          "content_type": "annotations_playlist", "content_id": seeded_book.id,
          "browser_id": "browser-B", "sentence_index": 10})
      r = await client.get("/api/v1/audio_position",
                           params={"content_type": "annotations_playlist",
                                   "content_id": seeded_book.id, "browser_id": "browser-A"})
      body = r.json()
      assert body["sentence_index"] == 5
      assert body["has_other_browser"] is True
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_annotations_playlist_resume.py -v` → expect FAIL (B14 routes likely use a Literal that excludes `annotations_playlist`, or Pydantic content_type enum needs widening).
- [ ] Step 3: In `routes/audio_position.py`, ensure the request/query model uses `content_type: ContentType` (the enum, which now includes `ANNOTATIONS_PLAYLIST` per A2). Verify CHECK constraint in `audio_positions` permits the value (per A3 schema). Wire repo path through.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_annotations_playlist_resume.py -v` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio_position.py backend/tests/integration/test_annotations_playlist_resume.py
  git commit -m "feat(tts): audio_position routes accept annotations_playlist content_type"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_annotations_playlist_resume.py -v` — 3 passed

---

### Phase F — Settings TTS + spike CLI + warm status (F1–F8)

#### F1: `SettingsTtsPanel.vue` — main settings pane

**Goal:** Settings TTS panel with engine radios, voice picker, sample buttons on both engines, status indicator, spike findings block.
**Spec refs:** FR-43, FR-45, FR-47, M1, S1, S3
**Wireframe refs:** `07_settings-tts_desktop-web.html` (4 states), `07_settings-tts_mobile-web.html`

**Files:**
- Create: `frontend/src/components/settings/SettingsTtsPanel.vue`
- Modify: `frontend/src/views/SettingsView.vue` (mount the panel)
- Test: `frontend/src/components/settings/__tests__/SettingsTtsPanel.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders engine radios with both Web Speech and Kokoro selectable', () => {
    const wrap = mount(SettingsTtsPanel);
    expect(wrap.find('input[type="radio"][value="web-speech"]').exists()).toBe(true);
    expect(wrap.find('input[type="radio"][value="kokoro"]').exists()).toBe(true);
  });
  it('Sample button on Web Speech row uses speechSynthesis directly', async () => { ... });
  it('Sample button on Kokoro row POSTs /audio/sample', async () => {
    fetchMock.mockResolvedValueOnce({ status: 200, body: new Blob([new Uint8Array([0x49, 0x44, 0x33])], { type: 'audio/mpeg' }) });
    const wrap = mount(SettingsTtsPanel);
    await wrap.find('button[data-testid="sample-kokoro-af_sarah"]').trigger('click');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/audio/sample', expect.objectContaining({ method: 'POST', body: expect.stringContaining('af_sarah') }));
  });
  it('PUT settings on save', async () => {
    fetchMock.mockResolvedValueOnce({ status: 200 });
    const wrap = mount(SettingsTtsPanel);
    await wrap.find('input[type="radio"][value="kokoro"]').setValue();
    await wrap.find('button[data-testid="save"]').trigger('click');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/settings/tts', expect.objectContaining({ method: 'PUT' }));
  });
  it('renders 4 states (default / sample-loading / model-not-downloaded / no-voices-available)', () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- SettingsTtsPanel` → expect FAIL.
- [ ] Step 3: Author panel. Includes `SpikeFindingsBlock` (F2), `KokoroStatusIndicator` (F4), `VoiceSampleButton` (F3) on both rows. Save action calls PUT `/settings/tts`.
- [ ] Step 4: `cd frontend && npm run test:unit -- SettingsTtsPanel` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/settings/SettingsTtsPanel.vue frontend/src/views/SettingsView.vue frontend/src/components/settings/__tests__/SettingsTtsPanel.spec.ts
  git commit -m "feat(tts/fe): SettingsTtsPanel with 4 states"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- SettingsTtsPanel -v` — 5 passed

---

#### F2: `SpikeFindingsBlock.vue` — reads /spikes/tts

**Goal:** Renders 2-3 sentence spike-derived comparison + "Listen to comparison" button + link to spike doc.
**Spec refs:** FR-44, M1
**Wireframe refs:** `07_settings-tts_desktop-web.html`

**Files:**
- Create: `frontend/src/components/settings/SpikeFindingsBlock.vue`
- Test: `frontend/src/components/settings/__tests__/SpikeFindingsBlock.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('renders spike findings when available', async () => {
    fetchMock.mockResolvedValue({ available: true, path: 'docs/spikes/2026-05-15-tts-engine-spike.md', content_md: '# Findings\n\nKokoro sounded richer. Web Speech sounded flatter.' });
    const wrap = mount(SpikeFindingsBlock);
    await flushPromises();
    expect(wrap.text()).toContain('Kokoro sounded richer');
    expect(wrap.find('a[href$="2026-05-15-tts-engine-spike.md"]').exists()).toBe(true);
    expect(wrap.find('button[data-testid="listen-comparison"]').exists()).toBe(true);
  });
  it('renders run-spike message when not available', async () => {
    fetchMock.mockResolvedValue({ available: false });
    const wrap = mount(SpikeFindingsBlock);
    await flushPromises();
    expect(wrap.text()).toContain('Spike not yet run');
    expect(wrap.text()).toContain('bookcompanion spike tts');
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- SpikeFindingsBlock` → expect FAIL.
- [ ] Step 3: Author component. Render markdown via existing markdown-it with DOMPurify; "Listen to comparison" plays the same passage in both engines via existing sample API + speechSynthesis.
- [ ] Step 4: `cd frontend && npm run test:unit -- SpikeFindingsBlock` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/settings/SpikeFindingsBlock.vue frontend/src/components/settings/__tests__/SpikeFindingsBlock.spec.ts
  git commit -m "feat(tts/fe): SpikeFindingsBlock with comparison listen"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- SpikeFindingsBlock -v` — 2 passed

---

#### F3: `VoiceSampleButton.vue` — engine-agnostic sampler

**Goal:** Single component dispatches to `speechSynthesis.speak()` for Web Speech voices and `POST /audio/sample` for Kokoro voices.
**Spec refs:** FR-45, S1
**Wireframe refs:** `07_settings-tts_desktop-web.html`

**Files:**
- Create: `frontend/src/components/settings/VoiceSampleButton.vue`
- Test: `frontend/src/components/settings/__tests__/VoiceSampleButton.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('Web Speech sample uses speechSynthesis directly', async () => {
    const speakSpy = vi.spyOn(speechSynthesis, 'speak');
    const wrap = mount(VoiceSampleButton, { props: { engine: 'web-speech', voice: 'Samantha' } });
    await wrap.trigger('click');
    expect(speakSpy).toHaveBeenCalled();
  });
  it('Kokoro sample POSTs /audio/sample and plays returned bytes', async () => {
    fetchMock.mockResolvedValueOnce({ status: 200, headers: { 'content-type': 'audio/mpeg' }, body: new Blob([new Uint8Array([0x49, 0x44, 0x33])]) });
    const wrap = mount(VoiceSampleButton, { props: { engine: 'kokoro', voice: 'af_sarah' } });
    await wrap.trigger('click');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/audio/sample', expect.objectContaining({ body: expect.stringContaining('af_sarah') }));
  });
  it('shows loading spinner during sample', async () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- VoiceSampleButton` → expect FAIL.
- [ ] Step 3: Author component; uses `useAudioApiError` for failure paths.
- [ ] Step 4: `cd frontend && npm run test:unit -- VoiceSampleButton` → expect 3 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/settings/VoiceSampleButton.vue frontend/src/components/settings/__tests__/VoiceSampleButton.spec.ts
  git commit -m "feat(tts/fe): VoiceSampleButton dispatches by engine"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- VoiceSampleButton -v` — 3 passed

---

#### F4: `KokoroStatusIndicator.vue` — warm/cold/not-downloaded/download-failed

**Goal:** Polls `/settings/tts/status` every 10s; renders 4 states with green/grey/warning indicator.
**Spec refs:** FR-47, S3
**Wireframe refs:** `07_settings-tts_desktop-web.html`

**Files:**
- Create: `frontend/src/components/settings/KokoroStatusIndicator.vue`
- Test: `frontend/src/components/settings/__tests__/KokoroStatusIndicator.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it.each([
    ['warm', '🟢', 'Kokoro: warm'],
    ['cold', '⚪', 'Kokoro: cold'],
    ['not_downloaded', '⚠️', 'Model not downloaded'],
    ['download_failed', '⚠️', 'Download failed'],
  ])('renders status=%s', async (status, icon, label) => {
    fetchMock.mockResolvedValue({ status });
    const wrap = mount(KokoroStatusIndicator);
    await flushPromises();
    expect(wrap.text()).toContain(label);
  });
  it('Download button visible when not_downloaded', async () => {
    fetchMock.mockResolvedValue({ status: 'not_downloaded' });
    const wrap = mount(KokoroStatusIndicator);
    await flushPromises();
    expect(wrap.find('button[data-testid="download-model"]').exists()).toBe(true);
  });
  it('Retry button visible when download_failed', async () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- KokoroStatusIndicator` → expect FAIL.
- [ ] Step 3: Author component. Polls every 10s via `setInterval`. Use Heroicons or DESIGN.md anti-pattern-compliant indicators (avoid emoji per DESIGN.md voice rules — replace icons in the test with DOM markers like `[data-status="warm"]`).
- [ ] Step 4: `cd frontend && npm run test:unit -- KokoroStatusIndicator` → expect 6 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/components/settings/KokoroStatusIndicator.vue frontend/src/components/settings/__tests__/KokoroStatusIndicator.spec.ts
  git commit -m "feat(tts/fe): KokoroStatusIndicator with 4 states"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- KokoroStatusIndicator -v` — 6 passed

---

#### F5: `bookcompanion spike tts` CLI command

**Goal:** Generates a Kokoro MP3 of a chosen passage to `docs/spikes/clip-kokoro.mp3`; opens browser localhost helper that plays the same passage in Web Speech; emits `docs/spikes/<YYYY-MM-DD>-tts-engine-spike.md`.
**Spec refs:** FR-50, D30

**Files:**
- Create: `backend/app/cli/commands/spike_cmd.py`
- Create: `backend/app/cli/templates/spike_tts_findings.md.j2`
- Modify: `backend/app/cli/main.py` (register `spike` subcommand)
- Test: `backend/tests/e2e/test_spike_cli.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_spike_tts_writes_template(tmp_repo, monkeypatch):
      monkeypatch.setattr("app.services.tts.kokoro_provider.KokoroProvider.synthesize",
                          lambda self, text, voice, speed=1.0: SynthesisResult(b"ID3", 24000, [0.0]))
      result = runner.invoke(app, ["spike", "tts", "--book-id", "1", "--section-id", "2"])
      assert result.exit_code == 0
      doc = next((tmp_repo / "docs" / "spikes").glob("*-tts-engine-spike.md"))
      assert doc.exists()
      assert "Kokoro" in doc.read_text() and "Web Speech" in doc.read_text()
      assert (tmp_repo / "docs" / "spikes" / "clip-kokoro.mp3").exists()

  def test_spike_tts_help():
      result = runner.invoke(app, ["spike", "tts", "--help"])
      assert result.exit_code == 0
      assert "--book-id" in result.output
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/e2e/test_spike_cli.py -v` → expect FAIL.
- [ ] Step 3: Implement `spike_cmd.py`:
  - Typer subcommand `spike tts(book_id: int, section_id: int)`.
  - Load section markdown via service.
  - `KokoroProvider.synthesize(text, voice="af_sarah")` → write MP3 to `docs/spikes/clip-kokoro.mp3`.
  - Render Jinja template (with placeholders for `kokoro_adjective`, `web_speech_adjective`, `recommended_default`) → write `docs/spikes/<today_iso>-tts-engine-spike.md`.
  - Print: "Open http://localhost:8765/spike-helper.html to listen to Web Speech version of same passage. Edit the spike doc with your impressions."
- [ ] Step 4: `cd backend && uv run pytest tests/e2e/test_spike_cli.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/cli/commands/spike_cmd.py backend/app/cli/templates/spike_tts_findings.md.j2 backend/app/cli/main.py backend/tests/e2e/test_spike_cli.py
  git commit -m "feat(tts): bookcompanion spike tts CLI"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/e2e/test_spike_cli.py -v` — 2 passed
- `cd backend && uv run bookcompanion spike tts --help` — exits 0

---

#### F6: `bookcompanion init --tts-engine kokoro` flag

**Goal:** When `--tts-engine kokoro`, init eagerly downloads the Kokoro model.
**Spec refs:** FR-06

**Files:**
- Modify: `backend/app/cli/commands/init_cmd.py`
- Test: `backend/tests/e2e/test_init_tts.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_init_tts_engine_kokoro_downloads(tmp_data_dir, monkeypatch):
      called = {"hf_dl": False}
      monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda **kw: called.__setitem__("hf_dl", True) or "/fake/path")
      result = runner.invoke(app, ["init", "--tts-engine", "kokoro"])
      assert result.exit_code == 0
      assert called["hf_dl"] is True

  def test_init_without_flag_does_not_download(tmp_data_dir, monkeypatch):
      called = {"hf_dl": False}
      monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda **kw: called.__setitem__("hf_dl", True))
      result = runner.invoke(app, ["init"])
      assert result.exit_code == 0
      assert called["hf_dl"] is False
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/e2e/test_init_tts.py -v` → expect FAIL.
- [ ] Step 3: Add `--tts-engine` Typer option to `init_cmd.py`; if `"kokoro"`, call `KokoroProvider._ensure_model_downloaded(settings.data.directory / "models" / "tts")`.
- [ ] Step 4: `cd backend && uv run pytest tests/e2e/test_init_tts.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/cli/commands/init_cmd.py backend/tests/e2e/test_init_tts.py
  git commit -m "feat(tts): init --tts-engine kokoro eager download"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/e2e/test_init_tts.py -v` — 2 passed

---

#### F7: `bookcompanion init` ffmpeg check (Kokoro engine)

**Goal:** `init` checks `shutil.which("ffmpeg")` if `settings.tts.engine == "kokoro"`; clear actionable error.
**Spec refs:** FR-51

**Files:**
- Modify: `backend/app/cli/commands/init_cmd.py`
- Test: `backend/tests/e2e/test_init_tts.py` (extends)

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_init_kokoro_without_ffmpeg_errors(monkeypatch):
      monkeypatch.setattr("shutil.which", lambda c: None if c == "ffmpeg" else "/usr/bin/" + c)
      monkeypatch.setattr("app.config.Settings.tts", TTSConfig(engine="kokoro"))
      result = runner.invoke(app, ["init"])
      assert result.exit_code == 1
      assert "ffmpeg" in result.output and "brew install" in result.output

  def test_init_web_speech_without_ffmpeg_succeeds(monkeypatch):
      monkeypatch.setattr("shutil.which", lambda c: None if c == "ffmpeg" else "/usr/bin/" + c)
      monkeypatch.setattr("app.config.Settings.tts", TTSConfig(engine="web-speech"))
      result = runner.invoke(app, ["init"])
      assert result.exit_code == 0  # Web Speech doesn't need ffmpeg
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/e2e/test_init_tts.py -v` → expect FAIL on new tests.
- [ ] Step 3: Add ffmpeg check at end of `init_cmd.py` only when engine=kokoro.
- [ ] Step 4: `cd backend && uv run pytest tests/e2e/test_init_tts.py -v` → expect 4 passed (includes F7's 2).
- [ ] Step 5: Commit
  ```bash
  git add backend/app/cli/commands/init_cmd.py backend/tests/e2e/test_init_tts.py
  git commit -m "feat(tts): init checks ffmpeg when engine=kokoro"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/e2e/test_init_tts.py -v` — 4 passed

---

### Phase G — CLI: listen + maintenance (G1–G3)

#### G1: `bookcompanion listen <book_id>` — local-device playback

**Goal:** CLI plays book summary via Kokoro + `sounddevice` to local audio device; keybindings space=pause, n=next, p=prev sentence.
**Spec refs:** FR-48

**Files:**
- Create: `backend/app/cli/commands/listen_cmd.py`
- Modify: `backend/app/cli/main.py`
- Test: `backend/tests/e2e/test_listen_cli.py`

**Steps:**

- [ ] Step 1: Add `sounddevice` to pyproject.toml; `uv sync`.
- [ ] Step 2: Write failing test
  ```python
  def test_listen_command_help():
      result = runner.invoke(app, ["listen", "--help"])
      assert result.exit_code == 0
      assert "--generate" in result.output

  def test_listen_invokes_kokoro_then_sounddevice(monkeypatch, seeded_book_with_book_summary):
      played = []
      monkeypatch.setattr("sounddevice.play", lambda data, sr: played.append((len(data), sr)))
      monkeypatch.setattr("sounddevice.wait", lambda: None)
      monkeypatch.setattr("app.services.tts.kokoro_provider.KokoroProvider.synthesize",
                          lambda self, text, voice, speed=1.0: SynthesisResult(b"x", 24000, [0.0]))
      result = runner.invoke(app, ["listen", str(seeded_book.id)], input="q\n")  # quit immediately
      assert result.exit_code == 0
      assert len(played) >= 1  # at least one sentence played
  ```
- [ ] Step 3: `cd backend && uv run pytest tests/e2e/test_listen_cli.py -v` → expect FAIL.
- [ ] Step 4: Implement `listen_cmd.py`:
  - `@async_command def listen(book_id: int, generate: bool = False, scope: str = "book", voice: str = "")`
  - If `generate`: queues a `step=AUDIO` job (G2).
  - Else: fetch book summary via service; for each sentence (use `markdown_to_speech.sanitize`); call `provider.synthesize_segmented` per sentence; `sounddevice.play(pcm, samplerate=24000)`; `sounddevice.wait()`; check stdin non-blocking for "p"/"n"/"q" key (use `tty.setcbreak` + `select.select`).
- [ ] Step 5: `cd backend && uv run pytest tests/e2e/test_listen_cli.py -v` → expect 2 passed.
- [ ] Step 6: Commit
  ```bash
  git add backend/app/cli/commands/listen_cmd.py backend/app/cli/main.py backend/pyproject.toml backend/uv.lock backend/tests/e2e/test_listen_cli.py
  git commit -m "feat(tts): bookcompanion listen CLI playback"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/e2e/test_listen_cli.py -v` — 2 passed
- `cd backend && uv run bookcompanion listen --help` — exits 0

---

#### G2: `bookcompanion listen --generate` — CLI queue parity

**Goal:** CLI queues the same `step=AUDIO` job as the UI button; streams SSE with Rich progress; prints final paths + total disk on completion.
**Spec refs:** FR-49

**Files:**
- Modify: `backend/app/cli/commands/listen_cmd.py`
- Test: `backend/tests/e2e/test_listen_cli.py` (extends)

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_listen_generate_queues_job_and_streams(seeded_book_with_3_sections, client):
      result = runner.invoke(app, ["listen", "--generate", str(book.id), "--scope", "sections"])
      assert result.exit_code == 0
      assert "3 / 3" in result.output  # progress bar
      assert ".mp3" in result.output   # paths printed
      assert "Total disk:" in result.output
      # Verify rows persisted
      rows = await audio_repo.list_by_book(book.id)
      assert len(rows) == 3
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/e2e/test_listen_cli.py -v` → expect FAIL on new test.
- [ ] Step 3: In `listen_cmd.py`, when `--generate`: POST `/api/v1/books/{id}/audio` to localhost server (or call services directly via `get_services` if no server running). Stream SSE via `httpx`/`aiohttp-sse-client`. Render Rich `Progress` bar updating per `section_audio_completed`. On terminal events: print per-row `file_path` + `file_size_bytes`; sum and print `f"Total disk: {humanize.naturalsize(total)}"`.
- [ ] Step 4: `cd backend && uv run pytest tests/e2e/test_listen_cli.py -v` → expect 3 passed (includes G1's 2).
- [ ] Step 5: Commit
  ```bash
  git add backend/app/cli/commands/listen_cmd.py backend/tests/e2e/test_listen_cli.py
  git commit -m "feat(tts): bookcompanion listen --generate CLI queue parity"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/e2e/test_listen_cli.py -v` — 3 passed

---

#### G3: `bookcompanion maintenance audio-positions-sweep`

**Goal:** Weekly maintenance command sweeps audio_positions whose content_id no longer resolves.
**Spec refs:** FR-26b

**Files:**
- Create: `backend/app/cli/commands/maintenance_cmd.py`
- Modify: `backend/app/cli/main.py`
- Test: `backend/tests/e2e/test_maintenance_cli.py`

**Steps:**

- [ ] Step 1: Write failing test
  ```python
  def test_audio_positions_sweep_removes_orphans(seeded_db):
      # Position pointing at deleted section
      seeded_db.add(AudioPosition(content_type=ContentType.SECTION_SUMMARY, content_id=99999,
                                  browser_id="X", sentence_index=1))
      await seeded_db.commit()
      result = runner.invoke(app, ["maintenance", "audio-positions-sweep"])
      assert result.exit_code == 0
      assert "Removed 1 orphan" in result.output
      remaining = await seeded_db.execute(select(AudioPosition).where(AudioPosition.content_id == 99999))
      assert remaining.scalars().first() is None

  def test_sweep_preserves_valid_rows(seeded_db, valid_section):
      seeded_db.add(AudioPosition(content_type=ContentType.SECTION_SUMMARY, content_id=valid_section.id,
                                  browser_id="X", sentence_index=1))
      await seeded_db.commit()
      result = runner.invoke(app, ["maintenance", "audio-positions-sweep"])
      remaining = await seeded_db.execute(select(AudioPosition).where(AudioPosition.content_id == valid_section.id))
      assert remaining.scalars().first() is not None
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/e2e/test_maintenance_cli.py -v` → expect FAIL.
- [ ] Step 3: Implement `maintenance audio-positions-sweep` Typer subcommand executing the SQL: for each row in audio_positions, validate content_id resolves to an existing row (BookSection, Summary, or Book per content_type); delete unresolved.
- [ ] Step 4: `cd backend && uv run pytest tests/e2e/test_maintenance_cli.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/cli/commands/maintenance_cmd.py backend/app/cli/main.py backend/tests/e2e/test_maintenance_cli.py
  git commit -m "feat(tts): maintenance audio-positions-sweep CLI"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/e2e/test_maintenance_cli.py -v` — 2 passed

---

### Phase H — Polish (H1–H5)

#### H1: Media Session API integration (Kokoro `<audio>` only)

**Goal:** When engine=kokoro and Mp3Engine active, set `navigator.mediaSession.metadata`, `playbackState`, and action handlers.
**Spec refs:** FR-33, D34
**Wireframe refs:** `01_reader-section-player_desktop-web.html` (playing state), `02_book-summary-player_desktop-web.html`

**Files:**
- Modify: `frontend/src/composables/audio/mp3Engine.ts`
- Test: `frontend/src/composables/audio/__tests__/mp3Engine.mediaSession.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('sets MediaMetadata on play', async () => {
    const eng = new Mp3Engine({ url: '/...', sentence_offsets: [0,4.2], book: { title: 'T', author: 'A', cover_url: '/c.jpg' }, sectionTitle: 'Anchoring' });
    await eng.play();
    expect(navigator.mediaSession.metadata.title).toBe('Anchoring');
    expect(navigator.mediaSession.metadata.artist).toBe('A');
    expect(navigator.mediaSession.metadata.album).toBe('T');
  });
  it('registers play/pause/seekto handlers', async () => { ... });
  it('updates positionState on timeupdate', () => { ... });
  it('does NOT set metadata when WebSpeechEngine active', () => { /* WebSpeechEngine should not touch mediaSession */ });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "mp3Engine.mediaSession"` → expect FAIL.
- [ ] Step 3: In `mp3Engine.ts` after `play()`, set metadata + handlers. Implement `setPositionState({duration, position, playbackRate})` per timeupdate. WebSpeechEngine: explicitly NO mediaSession wiring.
- [ ] Step 4: `cd frontend && npm run test:unit -- "mp3Engine.mediaSession"` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/mp3Engine.ts frontend/src/composables/audio/__tests__/mp3Engine.mediaSession.spec.ts
  git commit -m "feat(tts/fe): Media Session API for Kokoro Mp3Engine only"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "mp3Engine.mediaSession" -v` — 4 passed

---

#### H2: `chapterInfo` for book-summary playback

**Goal:** When playing a book summary, set `MediaMetadata.chapterInfo` to enumerate sections; lock-screen surfaces them.
**Spec refs:** FR-33

**Files:**
- Modify: `frontend/src/composables/audio/mp3Engine.ts`
- Test: extends `mp3Engine.mediaSession.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('sets chapterInfo when playing book summary', async () => {
    const eng = new Mp3Engine({ url: '...', contentType: 'book_summary', sectionList: [{title: 'Ch 1', startTime: 0}, {title: 'Ch 2', startTime: 120}] });
    await eng.play();
    expect(navigator.mediaSession.metadata.chapterInfo).toEqual([
      { title: 'Ch 1', startTime: 0 }, { title: 'Ch 2', startTime: 120 }
    ]);
  });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "mp3Engine.mediaSession"` → expect FAIL on new test.
- [ ] Step 3: In Mp3Engine, when `contentType === "book_summary"` and `sectionList` provided, set `chapterInfo` array.
- [ ] Step 4: `cd frontend && npm run test:unit -- "mp3Engine.mediaSession"` → expect 5 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/mp3Engine.ts frontend/src/composables/audio/__tests__/mp3Engine.mediaSession.spec.ts
  git commit -m "feat(tts/fe): chapterInfo for book summary playback"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "mp3Engine.mediaSession" -v` — 5 passed

---

#### H3: `RegenerateStaleAudioBanner.vue` — library-level

**Goal:** When ≥2 books have stale audio, render banner above book grid; click queues one job per stale book.
**Spec refs:** FR-66, MSF N2
**Wireframe refs:** None — this banner is a post-prototype scope addition (req-doc MSF N2 / FR-66) and was not drawn in `docs/wireframes/2026-05-02-audiobook-mode/`. Implementation follows DESIGN.md `bc-banner--info` shape (indigo `#eef2ff` bg, `#c7d2fe` border, `#3730a3` text per the second-blue anti-pattern rule) and `x-content` voice/copy conventions; place above the existing book grid in `LibraryView.vue` using the standard inline-banner pattern from existing components like `SummaryFailureBanner`.

**Files:**
- Create: `frontend/src/components/library/RegenerateStaleAudioBanner.vue`
- Modify: `frontend/src/views/LibraryView.vue` (mount)
- Modify: `backend/app/api/routes/audio.py` (add `GET /api/v1/audio/stale-books` returning books with stale audio)
- Test: `frontend/src/components/library/__tests__/RegenerateStaleAudioBanner.spec.ts`
- Test: `backend/tests/integration/test_stale_books_endpoint.py`

**Steps:**

- [ ] Step 1: Write failing tests
  ```python
  # backend
  async def test_stale_books_endpoint(client, seeded_books_with_stale_audio):
      r = await client.get("/api/v1/audio/stale-books")
      assert r.status_code == 200
      assert len(r.json()["books"]) == 3
  ```
  ```typescript
  // frontend
  it('renders banner when ≥2 stale books', async () => {
    fetchMock.mockResolvedValue({ books: [{id:1, title:'A'}, {id:2, title:'B'}, {id:3, title:'C'}] });
    const wrap = mount(RegenerateStaleAudioBanner);
    await flushPromises();
    expect(wrap.text()).toContain('3 books have stale audio');
  });
  it('hidden when <2', async () => {
    fetchMock.mockResolvedValue({ books: [{id:1, title:'A'}] });
    const wrap = mount(RegenerateStaleAudioBanner);
    await flushPromises();
    expect(wrap.html()).toBe('<!---->');
  });
  it('Regenerate queues one POST per stale book', async () => {
    fetchMock.mockResolvedValueOnce({ books: [{id:1}, {id:2}] });
    fetchMock.mockResolvedValue({ status: 202 });
    const wrap = mount(RegenerateStaleAudioBanner);
    await flushPromises();
    await wrap.find('button[data-testid="regenerate-all"]').trigger('click');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/books/1/audio', expect.any(Object));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/books/2/audio', expect.any(Object));
  });
  it('Dismiss sets 24h cookie', async () => {
    fetchMock.mockResolvedValue({ books: [{id:1},{id:2}] });
    const wrap = mount(RegenerateStaleAudioBanner);
    await flushPromises();
    await wrap.find('button[data-testid="dismiss"]').trigger('click');
    expect(document.cookie).toContain('bc_stale_audio_banner_dismissed');
  });
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_stale_books_endpoint.py -v && cd ../frontend && npm run test:unit -- RegenerateStaleAudioBanner` → expect FAIL on both.
- [ ] Step 3: Implement endpoint: enumerate AudioFile rows whose stale flag is true (compute via lookup logic) grouped by book_id; return list. Frontend banner reads endpoint, mounts `bc-banner--info` (indigo), Dismiss sets `Set-Cookie` 24h.
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_stale_books_endpoint.py -v && cd ../frontend && npm run test:unit -- RegenerateStaleAudioBanner` → expect 1 + 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/api/routes/audio.py backend/tests/integration/test_stale_books_endpoint.py frontend/src/components/library/RegenerateStaleAudioBanner.vue frontend/src/views/LibraryView.vue frontend/src/components/library/__tests__/RegenerateStaleAudioBanner.spec.ts
  git commit -m "feat(tts): library-level Regenerate stale audio banner"
  ```

**Inline verification:**
- Backend: `uv run pytest tests/integration/test_stale_books_endpoint.py -v` — 1 passed
- Frontend: `npm run test:unit -- RegenerateStaleAudioBanner -v` — 4 passed

---

#### H4: Auto-advance to next section's audio

**Goal:** When current section ends and `settings.tts.auto_advance && next_section.has_pre_gen_audio` (or Web Speech path), load next; otherwise stop.
**Spec refs:** FR-34, D27

**Files:**
- Modify: `frontend/src/composables/audio/useTtsEngine.ts`
- Test: `frontend/src/composables/audio/__tests__/useTtsEngine.autoAdvance.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  ```typescript
  it('loads next section on end when auto_advance true and next has audio', async () => {
    const settings = { tts: { auto_advance: true } };
    const eng = await useTtsEngine().load({ contentType: 'section_summary', contentId: 42, nextSectionId: 43 });
    fetchMock.mockResolvedValue({ pregenerated: true, url: '/...43.mp3' });
    eng._fakeEnd();
    await flushPromises();
    expect(useTtsPlayerStore().contentId).toBe(43);
  });
  it('falls back to Web Speech when next has no MP3 (D14)', async () => { ... });
  it('does not advance when settings.tts.auto_advance=false', async () => { ... });
  it('stops at end of book (no nextSectionId)', async () => { ... });
  ```
- [ ] Step 2: `cd frontend && npm run test:unit -- "useTtsEngine.autoAdvance"` → expect FAIL.
- [ ] Step 3: Wire `engine.onEnd(...)` → if auto_advance + nextSectionId present, call `useTtsEngine().load({nextSectionId})` (which routes to MP3 or Web Speech via lookup per D14).
- [ ] Step 4: `cd frontend && npm run test:unit -- "useTtsEngine.autoAdvance"` → expect 4 passed.
- [ ] Step 5: Commit
  ```bash
  git add frontend/src/composables/audio/useTtsEngine.ts frontend/src/composables/audio/__tests__/useTtsEngine.autoAdvance.spec.ts
  git commit -m "feat(tts/fe): auto-advance with D14 Web Speech fallback"
  ```

**Inline verification:**
- `cd frontend && npm run test:unit -- "useTtsEngine.autoAdvance" -v` — 4 passed

---

#### H5: Per-AudioFile size cap (NFR-13)

**Goal:** KokoroProvider rejects synthesis of inputs > 50,000 sanitized chars; emits `section_audio_failed{reason: "too_large"}`.
**Spec refs:** NFR-13

**Files:**
- Modify: `backend/app/services/tts/kokoro_provider.py`
- Modify: `backend/app/services/audio_gen_service.py` (catch + map to SSE)
- Test: `backend/tests/integration/test_audio_size_cap.py`

**Steps:**

- [ ] Step 1: Write failing test (asserts on **post-sanitizer** length, per NFR-13 wording)
  ```python
  async def test_synthesis_rejected_when_sanitized_over_50k_chars(svc):
      # Build raw input that survives sanitization to >50k chars (no code blocks / images / math to strip)
      huge_raw = "This is a perfectly normal sentence. " * 1500  # ~55,500 chars; sanitizer keeps almost all
      sanitized = sanitize(huge_raw)
      assert len(sanitized.text) > 50_000  # confirm fixture is on the wrong side of the cap
      with pytest.raises(TooLargeError):
          await svc.tts_provider.synthesize(huge_raw, voice="af_sarah")

  async def test_synthesis_accepts_when_sanitizer_strips_below_cap(svc):
      # Raw input is large but sanitizer reduces below cap (lots of code blocks / images stripped)
      raw_with_chunks = "Short sentence.\n\n" + ("```py\n" + "x=1\n" * 1000 + "```\n\n") * 50
      sanitized = sanitize(raw_with_chunks)
      assert len(sanitized.text) < 50_000  # post-sanitizer below cap
      # Should NOT raise TooLargeError; synthesis proceeds
      result = await svc.tts_provider.synthesize(raw_with_chunks, voice="af_sarah")
      assert result.audio_bytes  # non-empty

  async def test_audio_job_emits_too_large_for_huge_section(client, seeded_huge_section):
      # Section's source_md sanitizes to >50k chars
      r = await client.post(f"/api/v1/books/{book.id}/audio", json={"scope": "sections", "section_ids": [seeded_huge_section.id], "voice": "af_sarah", "engine": "kokoro"})
      job_id = r.json()["job_id"]
      events = await drain_events(job_id)
      assert any(e["type"] == "section_audio_failed" and e["data"]["reason"] == "too_large" for e in events)
  ```
- [ ] Step 2: `cd backend && uv run pytest tests/integration/test_audio_size_cap.py -v` → expect FAIL.
- [ ] Step 3: In KokoroProvider.synthesize, AFTER `sanitize()` returns, check `len(sanitized.text) > 50_000` → raise `TooLargeError`. Add to provider exceptions module. In AudioGenService.run_job, catch `TooLargeError` → emit `section_audio_failed{reason: "too_large"}` and skip the unit (per-unit failure, not whole-job).
- [ ] Step 4: `cd backend && uv run pytest tests/integration/test_audio_size_cap.py -v` → expect 2 passed.
- [ ] Step 5: Commit
  ```bash
  git add backend/app/services/tts/kokoro_provider.py backend/app/services/tts/provider.py backend/app/services/audio_gen_service.py backend/tests/integration/test_audio_size_cap.py
  git commit -m "feat(tts): per-unit size cap with too_large SSE reason"
  ```

**Inline verification:**
- `cd backend && uv run pytest tests/integration/test_audio_size_cap.py -v` — 2 passed

---

### TN: Final Verification

**Goal:** Verify the entire audiobook-mode implementation works end-to-end on a clean install.

**Spec refs:** all FRs (G1–G10 done-when criteria)

- [ ] **Lint & format (backend):** `cd backend && uv run ruff check app/services/tts app/api/routes/audio.py app/api/routes/audio_position.py app/api/routes/spikes.py app/cli/commands/{listen,spike,maintenance}_cmd.py && uv run ruff format --check .`
  Expected: 0 errors, 0 reformat needed.
- [ ] **Lint & type-check (frontend):** `cd frontend && npm run lint && npm run type-check && npm run format`
  Expected: 0 errors.
- [ ] **Unit tests (backend, fast):** `cd backend && uv run pytest tests/unit/ tests/integration/ -m "not kokoro" -v`
  Expected: ~440 existing tests + ~50 new audio tests pass; 0 failed.
- [ ] **Kokoro integration tests (opt-in, manual):** `cd backend && uv run pytest -m kokoro -v`
  Expected: 4–6 Kokoro tests pass after one-time model download.
- [ ] **Frontend unit tests:** `cd frontend && npm run test:unit`
  Expected: ~existing + ~50 new audio component/composable tests pass.
- [ ] **Migration round-trip:** `cd backend && uv run alembic -c app/migrations/alembic.ini upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
  Expected: exits 0; tables created/dropped/recreated cleanly.
- [ ] **Build frontend into backend static dir** (per CLAUDE.md interactive verification):
  ```bash
  cd frontend && npm run build
  rm -rf ../backend/app/static && cp -R dist ../backend/app/static
  ```
- [ ] **Start verification server:**
  ```bash
  cd backend && uv run bookcompanion serve --port 8765 &
  sleep 2 && curl -sf http://localhost:8765/api/v1/health
  ```
  Expected: `{"status": "ok"}`.
- [ ] **API smoke (POST /audio):**
  ```bash
  BOOK_ID=$(sqlite3 ~/Library/Application\ Support/bookcompanion/library.db "SELECT id FROM books LIMIT 1")
  curl -X POST http://localhost:8765/api/v1/books/$BOOK_ID/audio \
       -H "Content-Type: application/json" \
       -d '{"scope":"book","voice":"af_sarah","engine":"kokoro"}' | python3 -m json.tool
  ```
  Expected: `{"job_id": <int>, "scope": "book", "total_units": 1}`.
- [ ] **API smoke (GET /audio/lookup):** `curl -sf "http://localhost:8765/api/v1/audio/lookup?book_id=$BOOK_ID&content_type=section_summary&content_id=1" | python3 -m json.tool` → expect `pregenerated: true|false`, `sanitized_text` non-empty, `sentence_offsets_chars` array.
- [ ] **API smoke (GET /spikes/tts):** `curl -sf http://localhost:8765/api/v1/spikes/tts | python3 -m json.tool` → expect `{available: false}` until spike runs (or `{available: true, ...}` if spike doc exists).
- [ ] **CLI smoke:** `cd backend && uv run bookcompanion listen --help && uv run bookcompanion spike tts --help && uv run bookcompanion maintenance audio-positions-sweep --help` → all exit 0.
- [ ] **Frontend smoke (Playwright MCP, automated):** `cd frontend && npm run test:e2e -- audiobook` → expect 4 e2e specs pass (J1, J2, J3, settings).
- [ ] **Frontend smoke (Playwright MCP, manual driver):**
  1. **Authenticate:** N/A (single-user, no auth).
  2. **Navigate:** Open `http://localhost:8765/#/books/$BOOK_ID/overview`.
  3. **Verify Audio tab visible:** click Audio → expect tab content (no-audio or partial state).
  4. **Walk J2:** click "Generate audio" → confirm modal with annotations checkbox checked → confirm → progress card appears → wait completion → AudioFiles list populates with rows.
  5. **Walk J1:** Navigate to a section (`#/books/$BOOK_ID/section/<section_id>`) → click Play button in ReaderHeader → Playbar appears with engine chip → sentence highlights advance within 1s.
  6. **Walk J3:** Annotations tab → click Play-as-audio → playlist mode active.
  7. **Take screenshot.**
  8. **Hard-reload every parameterized route** (open in fresh tab, not in-app nav):
     - `#/books/$BOOK_ID/overview` → renders Overview tab content
     - `#/books/$BOOK_ID/audio` → renders Audio tab content (NOT Overview)
     - `#/books/$BOOK_ID/annotations` → renders Annotations tab content
     - `#/books/$BOOK_ID/section/$SECTION_ID` → renders the requested section (NOT first section)
     - `#/settings/tts` → renders TTS settings panel
  9. **Force at least one error path:**
     - Stop the backend (`kill $(lsof -ti:8765)`) → click Play → expect player error banner with Retry button (not silent failure).
     - Restart backend; click Retry → playback resumes.
- [ ] **UX polish checklist:**
  - `document.title` updates per route (e.g., "Audiobook Mode — Settings" on `/settings/tts`).
  - No internal IDs leaked (e.g., `section_summary` should not appear in user-facing copy verbatim — UI uses "Section summary").
  - Casing/date formats consistent (DESIGN.md: "May 2, 2026").
  - Image `alt` set on EngineChip / cover thumbnails.
  - No dead disabled affordances (every aria-labeled control either has handler or `aria-disabled="true"`; per prototype-finding #1).
  - Zero uncaught console errors during the J1+J2+J3 journey: `await browser_console_messages({level:'error'})` returns `[]`.
  - Navigation labels match destination titles (Audio tab → "Audio" on tab, "Audio" or "Audiobook" in tab content header).
- [ ] **Wireframe diff** (each affected screen open side-by-side with live UI; classify deltas):
  - `01_reader-section-player_*` vs `/section/X`: IA / copy / states (default, playing, paused-resume, loading-voice, no-summary-disabled, stale-source-banner, mid-listen-regen-banner) — every state reachable.
  - `02_book-summary-player_*` vs `/summary` view with audio.
  - `03_book-detail-audio_*` vs Audio tab — 4 states reachable (no-audio, partial, full, generating).
  - `04_generate-audio-modal_*` vs Generate modal — 3 states reachable.
  - `06_annotations-player_*` vs Annotations tab playlist mode.
  - `07_settings-tts_*` vs `/settings/tts` — 4 states reachable.
  - `08_sections-tab-audio_*` vs Sections tab — 3 states.
  - Visual style differences (color, spacing, typography) classified as `intentional — style adaptation` (host-app DESIGN.md tokens). Behavior/copy differences classified as `intentional — decision` (cite reason) or `regression` (fix before completion).
- [ ] **Latency spot-check (NFR-01/02/03 manual gates):**
  - **NFR-01 (≤200ms Web Speech click-to-audio):** in Chrome DevTools Performance panel, record while clicking Play on a section without pre-gen MP3; expected: first audio output within 200ms of click. Manual stopwatch acceptable.
  - **NFR-02 (≤2s Kokoro pre-gen click-to-play):** record while clicking Play on a section with pre-gen MP3; expected: `<audio>` `playing` event within 2s of click. Cold-load (first invocation post-page-load) is the tested case.
  - **NFR-03 (≥3x RTF Kokoro generation):** `cd backend && time uv run pytest tests/unit/services/tts/test_kokoro_offsets.py -m kokoro -v`; expected: 5-sentence synthesis completes in <(audio_total_seconds / 3). Eyeball-check in stdout.
  - Automated benchmarks deferred to /verify Phase 4 (pytest-benchmark + Playwright performance.timing) — too flaky for inline CI.
- [ ] **Manual spot check — durability invariants:**
  - Edit a section's summary; reopen reader → stale banner appears with "Source updated" copy (FR-12a path 1).
  - Bump `SANITIZER_VERSION` to "1.1" in dev; restart server; lookup → stale banner with "Audio engine updated" copy (FR-12a path 2).
  - Verify `section_audio_already_stale` event count appears in progress card when summary regen happens mid-job.
- [ ] **Manual spot check — concurrency:**
  - Open Generate modal in tab A; submit. While running, open Generate modal in tab B; submit → modal closes silently and joins tab A's progress card (no error toast — GS-7 self-heal).
  - With audio gen running on book 1, queue summarize on book 1 → INSERTs successfully (status=PENDING, the widened `(book_id, step)` partial UNIQUE index per D18/FR-17 permits coexistence). The summarize job RUNS only after the audio job completes — D19 keeps the worker single-RUNNING globally.
- [ ] **Manual spot check — recovery:**
  - With audio gen RUNNING, kill backend; restart → orphan job marked FAILED with `error_message="server_restart"`; Audio tab shows partial state with "Resume" affordance (FR-21b).
- [ ] **Manual spot check — cross-browser hint:**
  - On browser A, listen to section 42; pause at sentence 16. On browser B, open same section → resume affordance shows "last listened on a different browser" (FR-39).
- [ ] **Cleanup:**
  - Stop verification server: `kill $(lsof -ti:8765)`.
  - Remove generated test MP3s if any: `rm -rf "$HOME/Library/Application Support/bookcompanion/audio/<test_book_id>"`.
  - Remove `frontend/dist` build artifacts if not needed: leave (recopied next run).
  - Update `docs/changelog.md` with a user-facing entry for audiobook-mode v1.
  - Update `CLAUDE.md` if architecture sections need new gotchas (e.g., "ffmpeg required for Kokoro engine"; "audio jobs use step=AUDIO; partial UNIQUE is per (book_id, step)").
  - Run `git status` — verify only intended files changed.

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | (a) F5 was a no-op marker task (no test, no impl, no commit) referencing tests in B16 — violates "every task is independently committable" rule; (b) E6 + E7 used "expect already PASS / If failing, ensure" anti-pattern that violates strict TDD red/green; (c) D7 (UI-touching ProcessingBar extension) lacked Wireframe refs; H3 (library-level Regenerate Stale Audio banner) had no wireframe but no explicit "no wireframe — follows DESIGN.md X" note; (d) TN's "Manual concurrency check" wording "queue summarize on book 1 → succeeds" was ambiguous about D19's single-RUNNING worker behavior. | (a) Removed F5 entirely; renamed F6→F5, F7→F6, F8→F7. (b) Rewrote E6 with three behavioral cases (no-pregen returns sanitized concat, pregen returns url+stale, zero-highlights returns empty) — implementation now adds an `annotations_playlist` branch to `audio_gen_service.lookup`. Rewrote E7 with three behavioral cases (PUT/GET roundtrip, browser-independent positions with has_other_browser hint) — implementation now widens the routes' Pydantic enum to accept `annotations_playlist`. (c) Added Wireframe refs to D7 (`03_book-detail-audio_desktop-web.html` generating state) and explicit "No wireframe — follows DESIGN.md `bc-banner--info`" note on H3. (d) Tightened TN concurrency wording to "INSERTs successfully (status=PENDING)…runs only after audio completes" with explicit D18/D19 cross-refs. |
| 2 | (a) AudioGenService constructor in B1 lacked `annotation_repo`/`position_repo`/`book_repo`/`summary_repo` deps that downstream tasks (E5/E6/B14/B16) need; (b) D1 (BookOverviewView 5-tab strip) didn't specify URL-bound vs tab-state-bound — TN's hard-reload step assumed URL-bound; (c) H5 (NFR-13 size cap) test asserted on raw text length, but spec says post-sanitizer 50k chars. | (a) Updated B1's constructor signature to include all five repos. (b) D1 now specifies URL-bound child routes (`#/books/:id/{overview\|summary\|sections\|audio\|annotations}`) with router config update; matches existing 3-tab precedent. (c) H5 test rewritten with two cases: (1) raw text that survives sanitization to >50k → TooLargeError; (2) raw text that sanitizer strips below cap → succeeds. Implementation note clarifies the check happens AFTER `sanitize()`. |
| Final | (a) `FakeTTSProvider` referenced in B2/B11/E5 tests had no defined home; (b) `frontend/src/router/index.ts` modify (needed by D1's URL-bound tabs) was not in the File Map; (c) NFR-01/02/03 latency targets had no verification step in TN. | (a) Added `backend/tests/integration/conftest.py` to File Map with explicit fixture list (FakeTTSProvider + seeded job fixtures). (b) Added `frontend/src/router/index.ts` to File Map (Modify) with the rationale that D1 adds two child routes mirroring the existing 3-tab pattern. (c) Added a TN "Latency spot-check" section with three manual gates (DevTools Performance for NFR-01/02; `time uv run pytest -m kokoro` for NFR-03 RTF) and noted that automated benchmarks defer to /verify Phase 4 to avoid CI flakes. |




