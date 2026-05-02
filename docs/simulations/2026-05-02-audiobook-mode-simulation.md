# Audiobook Mode — Spec Simulation

**Date:** 2026-05-02
**Spec:** `docs/specs/2026-05-02-audiobook-mode-spec.md`
**Tier:** 3
**Outcome:** 26 gaps surfaced, 26 patches applied to the spec inline. No accepted risks; no new open questions.

---

## 1. Scope

**In scope (drove gap discovery):**
- Persistence: `audio_files`, `audio_positions` tables; `ContentType` + `ProcessingStep` enum extensions; `processing_jobs` partial-UNIQUE index migration.
- API: `POST/GET/DELETE /audio`, `GET /audio/lookup`, `POST /audio/sample`, `GET/PUT /audio_position`, `GET /spikes/tts`, 3 new SSE events.
- Backend services: `TTSProvider` ABC, `KokoroProvider`, `MarkdownToSpeech` sanitizer, `AudioGenService`, `ID3Tagger`, lifespan pre-warm.
- Frontend: `ttsPlayerStore`, `Playbar`, `TtsPlayButton`, `BookOverviewView` 5-tab strip (Overview | Summary | Sections | Audio | Annotations), `GenerateAudioModal`, `SettingsTtsPanel`, sentence-wrap render.
- CLI: `bookcompanion listen [--generate]`, `bookcompanion spike tts`, `init` ffmpeg/Kokoro check.
- Operational: ffmpeg as required system dep when Kokoro engine selected; HuggingFace model download UX; structlog logging; Prometheus-shape metrics counters.

**Out of scope:** Cloud TTS engines; RSS podcast feed (v1.1); word-level karaoke; voice cloning; true cross-device handoff (D9 best-effort only); stream-on-demand from Kokoro; full original `content_md` TTS; multi-user.

**Companion specs:** None — single Tier 3 spec.

**Anticipated downstream consumers:** v1.1 RSS podcast feed (per D4) — flagged in Phase 5 forward-compat (MP3 ID3 + signed URL hooks).

---

## 2. Scenario Inventory

40 scenarios; full table in §3 coverage matrix. Distribution:

| Source | Count | Examples |
|--------|-------|----------|
| Spec-derived (J1-J3, J4 setup, JCLI; E1-E20) | 26 | S1-S26 |
| Variants (size, entry, recovery) | 3 | S27 (200-section), S28 (re-import), S29 (CLI+UI parallel) |
| Adversarial (10-category) | 12 | S30 (HF down), S31 (ffmpeg crash), S32 (concurrency), S33 (worker crash), S34 (double-submit), S35 (SSE reconnect), S36 (timeout-but-started), S37 (regen mid-job), S38 (whitespace-only), S39 (0 sentences), S40 (500-highlight playlist), S41 (unicode voice) |
| Model-driven (design-specific) | 5 | S42 (sanitizer dict drift), S43 (pysbd version drift), S44 (audio_position orphan), S45 (active vs default engine confusion), S46 (migration atomicity) |

Adversarial categories applied: dependency-down, concurrency, partial-failure, retry/idempotency, stale-data/timing, data-size/boundary, network/timeout, ordering, malformed-input. Permission/auth skipped (single-user local-first).

---

## 3. Coverage Matrix (compressed)

Spec-derived scenarios S1-S26 all map to existing FRs / sequence diagrams / edge cases in the spec — none surfaced gaps; coverage confirmed by Phase 3 walk. Below: only the scenarios that surfaced findings.

| Scenario | Step needing new artifact | Status before sim | Gap ID |
|----------|---------------------------|--------------------|--------|
| S27 200-section book | Cost estimator formula (modal preview) | hardcoded constants | GS-1 |
| S28 Re-import w/ existing audio | AudioFile reconciliation when sections deleted/added | unspecified | GS-2 |
| S30 HF down during model download | KokoroProvider download-failure handling | "fail-soft" only | GS-3 |
| S31 ffmpeg crash mid-encode | Subprocess error → per-unit failure | unspecified | GS-4 |
| S32 Two-tab Generate | BEGIN IMMEDIATE explicit | inherited but not stated | GS-5 |
| S33 Worker crash mid-job | Orphan-job recovery for step=AUDIO | unspecified | GS-6 |
| S34+S36 Double-submit / timeout-retry | 409 must include existing_job_id | missing | GS-7 |
| S35 SSE reconnect race | Subscribe/buffer/fetch/reconcile/live | unspecified | GS-8 |
| S37 Regen mid-gen-job | Stale-on-arrival counter | invisible | GS-9 |
| S38+S39 Empty sanitized text | Skip-unit semantics + UI placeholder | unspecified | GS-10 |
| S40 500-highlight playlist | Per-AudioFile size cap | unspecified | GS-11 (→ NFR-13) |
| S41 Unicode voice name | Voice validation at PUT settings | first-synthesize-fail | GS-12 |
| S42 Sanitizer dict change | `SANITIZER_VERSION` invariant + stale_reason | mass-stale silent | GS-13 |
| S43 pysbd version drift | Version pin + segmentation regression test | not pinned | GS-14 |
| S44 audio_position orphan | App-level cleanup in book-delete cascade | no FK / no cleanup | GS-15 |
| S45 Active vs default engine | EngineChip shows ACTIVE + reason tooltip | identical pill | GS-16 |
| S46 Migration ordering | Explicit op order + batch_alter_table note | implicit | GS-17 |

---

## 4. Artifact Fitness Findings

### Bucket 1: Data & Storage

| # | Finding | Severity |
|---|---------|----------|
| GB-1 | `AudioFile` lacked `job_id` traceback to producing ProcessingJob (debug aid) | minor |
| GB-2 | `sentence_offsets_json` had no validation hook | minor (deferred to runtime) |
| GS-13 | No `sanitizer_version` column → mass-stale silent on dict changes | significant |
| GS-15 | `audio_positions` polymorphic content_id has no FK, no cleanup hook | minor |

### Bucket 2: Service Interfaces

| # | Finding | Severity |
|---|---------|----------|
| GS-7 | 409 on `POST /audio` lacked existing_job_id → UI can't self-heal double-submit / retry | significant |
| GB-3 | `DELETE /audio` behavior with in-flight job unspecified | significant |
| GS-3 | Sample endpoint 503 retry shape unspecified | significant |
| GS-8 | SSE reconnect-recovery contract absent | significant |

### Bucket 3: Behavior

| # | Finding | Severity |
|---|---------|----------|
| GB-4 | No Cancel UI for RUNNING audio job (jobs run 20+ min — Cancel is essential) | significant |
| GB-5 | `ttsPlayerStore` lacked `error` state for mid-playback failures | significant |
| GS-9 | Mid-gen summary regen → no signal; produced audio silently stale | minor |

### Bucket 4: Interface

| # | Finding | Severity |
|---|---------|----------|
| GS-16 | EngineChip showed default-engine, hiding D14 fallback path | minor |
| GW-1 | No generic API-error → user mapping for /audio routes | minor |

### Bucket 6: Operational

| # | Finding | Severity |
|---|---------|----------|
| GB-6 | Firefox playback stance unstated | minor |
| GB-7 | No metrics counter naming guidance | minor |
| GB-8 | Migration ordering implicit | minor |
| GS-1 | Cost estimator constants hardcoded without formula | minor |
| GS-12 | Voice validation: silent fail at first synthesize | minor |

---

## 5. Cross-Reference (Frontend ↔ API)

### Forward table

| # | Interaction | Trigger | Endpoint | Req | Res | Errors | Notes |
|---|-------------|---------|----------|-----|-----|--------|-------|
| W1 | Click TtsPlayButton | ReaderHeader | GET /audio/lookup | ✓ | ✓ (post-sim adds `stale_reason`, `sanitizer_version_*`) | maps via §11.1.1 | clean post-patch |
| W2 | Confirm Generate Audio | GenerateAudioModal | POST /audio | ✓ | ✓ | 409 self-heals (FR-18 post-sim) | clean post-patch |
| W3 | Sample Web Speech voice | SettingsTtsPanel | (browser only — speechSynthesis) | n/a | n/a | n/a | clean |
| W4 | Sample Kokoro voice | SettingsTtsPanel | POST /audio/sample | ✓ | ✓ | 429 ✓; 503 with Retry-After (post-sim) | clean post-patch |
| W5 | Spike findings block | SettingsTtsPanel | GET /spikes/tts | ✓ | ✓ | available:false ✓ | clean |
| W6 | Sentence boundary advance | useTtsEngine | PUT /audio_position | ✓ | 204 | maps via §11.1.1 | clean post-patch |
| W7 | Resume affordance | TtsPlayButton | GET /audio_position | ✓ | ✓ | 404 → "no resume" | clean |
| W8 | Audio tab list | AudioTab | GET /audio | ✓ | ✓ | maps via §11.1.1 | clean post-patch |
| W9 | Per-row delete | AudioFileRow | DELETE /audio/{ct}/{ci} | ✓ | 204 | 409 if writing (FR-25 post-sim) | clean post-patch |
| W10 | Delete all audio | DeleteAllAudioButton | DELETE /audio | ✓ | 204 | 409 / cancel-first (FR-24 post-sim) | clean post-patch |
| W11 | Job progress card | useBufferedJobStream | SSE + REST snapshot | ✓ | ✓ (post-sim FR-21a contract) | reconnect race closed | clean post-patch |
| W12 | Save TTS settings | SettingsTtsPanel | PUT /settings/tts | ✓ | ✓ | 422 unknown_voice (FR-43 post-sim) | clean post-patch |
| W13 | Kokoro warm status | SettingsTtsPanel | GET /settings/tts/status | ✓ | ✓ (post-sim adds `download_failed` state) | maps via §11.1.1 | clean post-patch |
| W14 | Cancel running job | Audio tab + Sections tab | POST /jobs/{id}/cancel (existing) | ✓ | ✓ | n/a | clean post-FR-25a |

### Reverse scan

All endpoints have at least one consumer. No orphans.

---

## 6. Pseudocode (3 flows)

### Flow 1: `KokoroProvider.synthesize()` per-sentence loop with offsets

**Entry:** Worker calls `provider.synthesize(text, voice, speed)` for each content unit during a `step=AUDIO` job.

```
FUNCTION synthesize(text: str, voice: str, speed: float) -> SynthesisResult:
  # 1. Sanitize + segment
  sanitized = MarkdownToSpeech.sanitize(text)        # may raise EmptySanitizedTextError
  sentences = pysbd.Segmenter("en", clean=False).segment(sanitized.text)
  IF len(sentences) == 0:
      RAISE EmptySanitizedTextError

  # 2. Per-sentence Kokoro synthesis
  buffers = []
  cumulative_seconds = 0.0
  offsets = [0.0]
  FOR sentence IN sentences:
      pcm, sr = kokoro_onnx.create(sentence, voice=voice, speed=speed)  # returns float32 numpy, sr=24000
      buffers.append(pcm)
      cumulative_seconds += len(pcm) / sr
      offsets.append(cumulative_seconds)
  offsets = offsets[:-1]  # drop trailing (we want sentence START offsets)

  joined = numpy.concatenate(buffers)  # float32 PCM, sr=24000

  # 3. Encode via ffmpeg subprocess
  TRY:
      mp3_bytes = run_ffmpeg(joined, sample_rate=24000)
  EXCEPT (NonZeroExitCode, BrokenPipeError) AS e:
      stderr_tail = e.stderr_bytes[-2048:].decode("utf-8", errors="replace")
      RAISE FfmpegEncodeError(stderr_tail=stderr_tail)

  RETURN SynthesisResult(bytes=mp3_bytes, sample_rate=24000, sentence_offsets=offsets)


FUNCTION run_ffmpeg(pcm: ndarray, sample_rate: int) -> bytes:
  proc = subprocess.Popen(
    ["ffmpeg", "-f", "f32le", "-ar", str(sample_rate), "-ac", "1",
     "-i", "-", "-codec:a", "libmp3lame", "-b:a", "96k", "-f", "mp3", "-"],
    stdin=PIPE, stdout=PIPE, stderr=PIPE,
  )
  stdout, stderr = proc.communicate(input=pcm.tobytes())
  IF proc.returncode != 0:
      RAISE NonZeroExitCode(stderr=stderr)
  RETURN stdout
```

**DB calls:** none (this is pure synthesis).

**State transitions:** none at this layer; worker handles ProcessingJob state.

**Error branches:**
- `EmptySanitizedTextError` → worker `section_audio_failed{reason: "empty_after_sanitize"}`, skip unit (FR-10)
- `KokoroModelDownloadError` → worker fails WHOLE job (FR-05)
- `FfmpegEncodeError` → worker `section_audio_failed{reason: "encode_failed"}`, skip unit, capture stderr_tail (FR-03)
- numpy `MemoryError` (e.g., 500-highlight playlist) → guard via NFR-13 size cap before entering loop

**Concurrency notes:** KokoroProvider keeps a single `Kokoro` model instance (process-local). Worker is single-RUNNING globally (D19), so no inter-job race. `terminate()` on cancel kills the ffmpeg subprocess + drops the partial buffers via try/finally cleanup.

---

### Flow 2: `POST /api/v1/books/{id}/audio` race-safe INSERT

**Entry:** FastAPI route handler.

```
ROUTE POST /api/v1/books/{book_id}/audio:
  body = {scope, section_ids?, voice, engine}
  validate(body)                                        # 400 on bad input

  IF engine == "web-speech":
      RETURN 400 {"error": "web_speech_not_pregeneratable"}

  # Pre-flight: ffmpeg + Kokoro available
  IF NOT shutil.which("ffmpeg"):
      RETURN 503 {"error": "ffmpeg_missing"}
  IF NOT app.state.tts_provider:
      RETURN 503 {"error": "kokoro_unavailable"}

  # Race-safe duplicate-check + INSERT (mirrors processing.py)
  ASYNC WITH session.begin():                           # BEGIN IMMEDIATE per FR-18 post-sim
      existing = SELECT id, scope, started_at
                 FROM processing_jobs
                 WHERE book_id = :book_id
                   AND step = 'audio'
                   AND status IN ('PENDING', 'RUNNING')
                 LIMIT 1
      IF existing:
          RETURN 409 {
            "error": "audio_job_in_progress",
            "existing_job_id": existing.id,
            "scope": existing.scope,
            "started_at": existing.started_at,
          }

      total_units = compute_total_units(book_id, scope, section_ids)
      IF total_units == 0:
          RETURN 400 {"error": "no_units"}            # e.g. annotations scope but 0 highlights

      job = INSERT INTO processing_jobs
            (book_id, step, status, request_params, progress)
            VALUES (:book_id, 'audio', 'PENDING',
                    :body_json,
                    {"completed":0, "total":total_units, "last_event_at":now()})
            RETURNING *

  # Outside transaction
  event_bus.publish("job_queued", {"job_id": job.id, "step": "audio", ...})

  RETURN 202 {"job_id": job.id, "scope": body.scope, "total_units": total_units}
```

**DB calls:**
- SELECT processing_jobs (predicate uses partial UNIQUE index)
- INSERT processing_jobs (UNIQUE constraint enforces race-safety)

**State transitions:** new ProcessingJob `(none) → PENDING`.

**Error branches:**
- 400 invalid input
- 409 self-healing payload
- 503 dependency missing
- IntegrityError on INSERT (race lost) → catch + re-SELECT to return 409

**Concurrency notes:** `BEGIN IMMEDIATE` upgrades the transaction to a write-lock at start, so the SELECT-then-INSERT pattern is atomic — second concurrent caller blocks on lock, then SELECT sees the first INSERT, returns 409. The partial UNIQUE index is the belt-and-braces backstop if BEGIN IMMEDIATE is missed.

---

### Flow 3: SSE reconnect 5-step subscribe-buffer-fetch-reconcile-live (FR-21a)

**Entry:** Frontend `useBufferedJobStream(jobId)` composable mounts OR reconnects after disconnect.

```
COMPOSABLE useBufferedJobStream(jobId):
  uiState = reactive({completed: 0, total: 0, last_event_at: null, sections: []})
  buffer = []
  status = "connecting"

  # 1. Subscribe (don't apply yet)
  es = new EventSource(`/api/v1/jobs/stream?job_id=${jobId}`)
  es.addEventListener("message", (ev) => {
      data = JSON.parse(ev.data)
      IF status == "connecting" || status == "fetching":
          buffer.push(data)               # buffer until reconciled
      ELSE:                                # status == "live"
          applyEvent(uiState, data)
          uiState.last_event_at = data.last_event_at
  })

  # 2 + 3. Fetch snapshot (the truth)
  status = "fetching"
  snapshot = AWAIT fetch(`/api/v1/jobs/${jobId}`).then(r => r.json())
  uiState.completed = snapshot.progress.completed
  uiState.total = snapshot.progress.total
  uiState.last_event_at = snapshot.progress.last_event_at
  uiState.sections = snapshot.sections   # full state

  # 4. Drain buffer with de-dup
  FOR ev IN buffer:
      IF ev.last_event_at <= uiState.last_event_at:
          CONTINUE                          # already reflected in snapshot
      applyEvent(uiState, ev)
      uiState.last_event_at = ev.last_event_at
  buffer.length = 0

  # 5. Live
  status = "live"

  # On disconnect: rerun all 5 steps
  es.addEventListener("error", (e) => {
      status = "connecting"
      buffer.length = 0
      setTimeout(() => useBufferedJobStream(jobId), backoff_ms)
  })
```

**DB calls:** server-side, the snapshot fetch issues `SELECT * FROM processing_jobs WHERE id = ?`. SSE emits go through `EventBus.publish` (no DB at emit time).

**State transitions:** UI status `connecting → fetching → live` on every connect/reconnect. Backend ProcessingJob state unchanged by this flow.

**Error branches:**
- Snapshot 404 → job was deleted (rare); UI shows "Job no longer available"
- Snapshot 5xx → exponential backoff retry, surface "reconnecting…" toast
- EventSource `error` → reconnect with backoff (existing `useBufferedJobStream` pattern)
- Buffer overflow protection: if buffer grows past 1000 events while fetching, drop oldest (snapshot will repopulate)

**Concurrency notes:** Multiple useBufferedJobStream instances (e.g., Audio tab + Sections tab in two open routes) for the same job_id share via Pinia store; only one EventSource per job_id per browser. BroadcastChannel `bc-tts-jobs` notifies sibling tabs of significant transitions (`processing_completed`, `processing_failed`) so each tab can refetch its snapshot.

---

## 7. Gap Register

| # | Gap | Exposed By | Severity | Disposition |
|---|-----|-----------|---------|-------------|
| GS-1 | Cost estimator constants hardcoded | S27 | minor | Apply (FR-60 formula) |
| GS-2 | Re-import audio reconciliation | S28 | significant | Apply (FR-26a) |
| GS-3 | HF model-download failure handling | S30 | significant | Apply (FR-05) |
| GS-4 | ffmpeg subprocess failure handling | S31 | significant | Apply (FR-03) |
| GS-5 | BEGIN IMMEDIATE pattern not stated | S32 | minor | Apply (§9.1) |
| GS-6 | Worker-restart orphan recovery | S33 | significant | Apply (FR-21b) |
| GS-7 | 409 self-healing payload + UI join | S34, S36 | significant | Apply (FR-18, §9.1) |
| GS-8 | SSE reconnect contract | S35 | significant | Apply (FR-21a) |
| GS-9 | Mid-gen-job summary regen signal | S37 | minor | Apply (new SSE event) |
| GS-10 | Empty sanitized text handling | S38, S39 | significant | Apply (FR-10) |
| GS-11 | Per-AudioFile size cap | S40 | minor | Apply (NFR-13) |
| GS-12 | Voice validation at PUT settings | S41 | minor | Apply (FR-43) |
| GS-13 | Sanitizer version invariant | S42 | significant | Apply (FR-12a, schema) |
| GS-14 | pysbd version pin + regression test | S43 | significant | Apply (FR-12b) |
| GS-15 | audio_positions cleanup on book delete | S44 | minor | Apply (FR-26b) |
| GS-16 | Active-vs-default engine chip | S45 | minor | Apply (FR-32) |
| GS-17 | Migration ordering note | S46 | minor | Apply (§10.2) |
| GB-1 | AudioFile.job_id traceback column | Bucket 1 | minor | Apply (schema) |
| GB-2 | sentence_offsets_json validation | Bucket 1 | minor | Defer to runtime guard |
| GB-3 | DELETE /audio vs in-flight job | Bucket 2 | significant | Apply (FR-24) |
| GB-4 | Cancel-job UI | Bucket 3 | significant | Apply (FR-25a) |
| GB-5 | ttsPlayerStore error state | Bucket 3+4 | significant | Apply (FR-28a) |
| GB-6 | Firefox best-effort stance | Bucket 6 | minor | Apply (NFR-09) |
| GB-7 | Metrics counters | Bucket 6 | minor | Apply (NFR-12) |
| GB-8 | Enum migration ordering | Bucket 6 | minor | Apply (§10.2) |
| GW-1 | Generic API-error mapping | Phase 5 | minor | Apply (§11.1.1) |

**Total: 26 gaps; all Apply.**

---

## 8. Accepted Risks

None. Every gap was applied as a spec patch.

---

## 9. Open Questions

No new open questions surfaced from simulation. The spec's existing §17 (OQ-1, OQ-2, OQ-5, OQ-6.1, NEW-OQ-1, NEW-OQ-2, NEW-OQ-3) carries forward unchanged.

---

## 10. Spec Patches Applied

| Patch | Spec section | Type |
|-------|--------------|------|
| FR-03 expanded with per-sentence loop + ffmpeg failure semantics | §7.1 | Edit |
| FR-05 expanded with `KokoroModelDownloadError` + 503 retry | §7.1 | Edit |
| FR-10 expanded with `EmptySanitizedTextError` + skip-unit semantics | §7.2 | Edit |
| FR-12a sanitizer version invariant | §7.2 | New |
| FR-12b pysbd pin + regression test | §7.2 | New |
| FR-18 expanded with BEGIN IMMEDIATE + 409 self-healing payload | §7.4 | Edit |
| FR-21 add `last_event_at` field | §7.4 | Edit |
| FR-21a SSE reconnect contract | §7.4 | New |
| FR-21b worker-restart orphan recovery | §7.4 | New |
| FR-24 expanded delete-vs-in-flight-job | §7.5 | Edit |
| FR-25 add 409 if writing | §7.5 | Edit |
| FR-25a Cancel-job UI surface | §7.5 | New |
| FR-26a re-import audio reconciliation | §7.5 | New |
| FR-26b audio_positions cleanup on book delete | §7.5 | New |
| FR-28 add `'error'` status + `errorKind` | §7.6 | Edit |
| FR-28a player error handling + Retry button | §7.6 | New |
| FR-32 active-vs-default engine chip + reason tooltip | §7.6 | Edit |
| FR-43 voice validation at PUT | §7.8 | Edit |
| FR-60 cost-estimator formula + constants | §7.11 | Edit |
| §9.1 409 response shape; concurrency-safety note | §9 | Edit |
| §9.6 lookup adds `sanitizer_version_*`, `stale_reason` fields | §9 | Edit |
| SSE event list adds `section_audio_already_stale` | §9.10 | Edit |
| §10.1 schema adds `sanitizer_version`, `job_id` columns | §10 | Edit |
| §10.2 migration ordering + batch_alter_table note | §10 | Edit |
| §11.1.1 generic API-error mapping composable | §11 | New |
| NFR-09 Firefox best-effort statement | §8 | Edit |
| NFR-12 metrics counters list | §8 | Edit |
| NFR-13 per-AudioFile size cap | §8 | New |
| Review Log row Sim-1 | end | Edit |

**Total: 29 spec edits.**

---

## 11. Review Log

| Loop | Findings | Changes |
|------|----------|---------|
| 1 | Phase 9 single-loop review: re-read spec post-patch; checked (a) every Gap Register entry has a disposition + Edit confirmation, (b) every Apply disposition appears in §10, (c) no significant gap deferred, (d) all 5 phases produced findings. All 5 review checks passed. No additional gaps surfaced. | None — exit gate met. |
