# Reader + Book Detail UX Fixes — Spec Simulation Trace

**Date:** 2026-04-30
**Spec:** [`docs/specs/2026-04-30-reader-and-book-detail-ux-fixes-spec.md`](../specs/2026-04-30-reader-and-book-detail-ux-fixes-spec.md)
**Tier:** 2 — Enhancement

## 1. Scope

**In scope:** Backend (API, services, prompt templates, Alembic data migrations) · Frontend (Vue components, Pinia stores, vue-router, theme CSS, webfont bundling) · Operational NFRs (a11y, perf, bundle size, migration safety).

**Out of scope (per spec Non-Goals):** Reader chrome redesign · queue dashboard at `/jobs` · parallel job execution · dropping the `processing_jobs` partial UNIQUE index · mobile-first layout (E15 hedged).

**Companion specs:** None — single doc covers FE + BE + ops.

**Anticipated downstream consumers:** None declared. Structure editor (from prior `2026-04-30-upload-summarize-flow-ux-fixes` bundle) is a sibling, not a downstream consumer of this spec's artifacts.

## 2. Scenario Inventory

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | Read fully-summarized book end-to-end (action row → reader → tabs → next/prev) | Spec §5 J1 | happy |
| S2 | Retry single failed section while no full-book job exists | Spec §5 J2 | happy |
| S3 | Watch a job from /jobs/{id} deep link (active job) | Spec §5 J3 | happy |
| S4 | Switch reader theme to Night, then to High-Contrast | Spec §5 J4 | happy |
| S5 | Section retry when full-book job is genuinely RUNNING (live PID) → 409 | Spec §9 E1 | concurrency |
| S6 | Section retry when blocking job is stale (dead PID) → on-demand sweep | Spec §9 E2 | concurrency |
| S7 | Image rewrite finds orphan `image:99` (id not in section's image map) | Spec §9 E3 | input |
| S8 | /jobs/{id} for a finished (COMPLETED) job — completion card | Spec §9 E4 | edge |
| S9 | /jobs/{id} for a non-existent / deleted job — 404 view | Spec §9 E5 | edge |
| S10 | URL `?tab=summary` on a section with no summary — silent rewrite | Spec §9 E6 | input |
| S11 | Prev/next from summary section to no-summary section | Spec §9 E7 | edge |
| S12 | Compression ratio > 100% (summary longer than original) | Spec §9 E8 | boundary |
| S13 | Section with empty `content_md` → compression shows "—" | Spec §9 E9 | boundary |
| S14 | Browser blocks `clipboard.write` (non-secure context, denied) | Spec §9 E11 | failure |
| S15 | Read Summary CTA on book with no default summary — disabled tooltip | Spec §9 E12 | empty |
| S16 | Export response < 250ms — loader floor enforced (no flash) | Spec §9 E13 | boundary |
| S17 | Page refresh during active SSE on /jobs/{id} | Spec §9 E14 | retry |
| S18 | LLM emits malformed `image:abc` — left untouched by regex | Spec §9 E16 | input |
| S19 | First-time user lands on /books/{id} with no summary (CTA disabled, action row variant) | Variant | happy |
| S20 | Two browser tabs POST /summarize on same book simultaneously, blocking job is stale | Adversarial | concurrency |
| S21 | SSE event arrives between GET /processing/{id} response paint and SSE subscribe (REST-then-SSE race per L69) | Adversarial | ordering |
| S22 | Image-rewrite migration runs against many summaries; one row's UPDATE fails — does the migration commit partial progress, can it resume? | Adversarial | partial-failure |
| S23 | `@fontsource/lora` package fails to load — what does Paper preset render? | Adversarial | failure |
| S24 | User cancels job at exact moment a section completes — cancel-vs-promote race per L70 | Adversarial | concurrency |
| S25 | User has `localStorage.appliedPresetKey = 'system:99'` (deleted preset id) → existing fallback chain still works post-migration | Adversarial | input |
| S26 | Backend deploy mid-job: existing RUNNING job is on the OLD prompt (emits `image:N`) but new code expects new format | Adversarial | timing |
| S27 | FR-32 `len(content_md)` at serialize time triggers full-payload load when only length is needed | Model-driven | design-specific |
| S28 | User opens /books/{id} while a section retry is RUNNING — does the new TOC table show live progress per row, or static at load time? | Model-driven | design-specific |

**Skipped categories with reason:** auth (single-user app, no auth surface) · pagination (TOC is single render of all sections, personal-scale typically < 100 sections per book) · 10x scaling (out of scope per requirements).

## 3. Coverage Matrix

| Scenario | Step | Spec Artifact | Status |
|----------|------|---------------|--------|
| S1 | Click Read → reader opens at first/last unread | FR-20 (action row), existing `/books/{id}/sections/{sectionId}` route | ✓ |
| S1 | Toggle Original/Summary tab | FR-14 to FR-19 | ✓ |
| S1 | Prev/next preserves tab choice | FR-16 | ✓ |
| S1 | Reload preserves tab | FR-15, FR-17 | ✓ |
| S2 | POST /summarize with `scope='section'` | §7.2, FR-01-04 + worker handles `scope='section'` (verified at `summarizer_service.py:118-122`) | ✓ |
| S2 | Retry accepted, single section job created | FR-01-04, partial UNIQUE index respected | ✓ |
| S3 | Mount `/jobs/{id}` view | FR-10, FR-11, FR-11a, FR-12 | ✓ |
| S3 | Paint from GET, subscribe to SSE | FR-11a (buffer-first/drain pattern), §6 pseudocode | ✓ |
| S3 | Live updates per event | FR-11b (event→UI mapping) | ✓ |
| S4 | Click theme tile → apply preset | FR-34, FR-35, FR-36 | ✓ |
| S4 | Theme variables fully wired | FR-35, NFR for full-coverage | ✓ |
| S5 | 409 with `active_job` payload | §7.2 modified shape, FR-03 | ✓ |
| S6 | Stale-sweep transactional + retry create | FR-01, FR-02, FR-04, sequence diagram | ✓ |
| S7 | Orphan `image:99` → strip with `[alt](#)` + log | FR-09 | ✓ |
| S8 | /jobs/{id} terminal mode → completion card | FR-12 mode (b) — fields enumerated post-patch | ✓ |
| S9 | /jobs/{id} 404 view | FR-12 mode (c) | ✓ |
| S10 | Silent rewrite of `?tab=summary` to `?tab=original` | FR-17 | ✓ |
| S11 | Tab choice carries forward, falls back if no summary | FR-16 | ✓ |
| S12 | Compression > 100% rendered as-is | E8, FR-31 | ✓ |
| S13 | "—" for zero content_char_count | E9, FR-31 | ✓ |
| S14 | Clipboard fallback chain | FR-26, §11.2a regex | ✓ |
| S15 | Read Summary disabled with tooltip | FR-23 | ✓ |
| S16 | 250ms loader floor, no flash | FR-25 (allSettled), E13 | ✓ |
| S17 | Refresh re-fetches GET + re-subscribes | E14, FR-11a (reconnect path) | ✓ |
| S18 | Malformed `image:abc` left untouched | E16, §11.2 strict regex | ✓ |
| S19 | First-time book with no summary — Read Summary disabled, Export ▾ disabled | FR-22a, FR-23 | ✓ |
| S20 | Two-tab concurrent POST → BEGIN IMMEDIATE serializes | FR-02 (transaction shape), sequence diagram | ✓ |
| S21 | SSE seeding race | FR-11a (buffer-then-drain pattern, §6 pseudocode) | ✓ (post-patch) |
| S22 | Migration partial failure → full rollback, retryable on next init | NFR-06 (transaction-wrap explicit) | ✓ (post-patch) |
| S23 | Webfont fails to load → fallback chain renders | FR-39a (font-display: swap + system fallback chain) | ✓ (post-patch) |
| S24 | Cancel-vs-promote race | Existing atomic DELETE WHERE status='PENDING' (per recon `processing.py:228-306`); spec defers to existing behavior | ✓ |
| S25 | localStorage stale preset id → fallback to first available | Existing `loadPresets` recovery (per recon `readerSettings.ts:327-345`) | ✓ |
| S26 | Mid-deploy in-flight job on old prompt | Rewriter (FR-05/06) handles legacy `image:N` regardless of prompt source | ✓ |
| S27 | char_count via SQL LENGTH() not Python len() | FR-32 (post-patch) | ✓ (post-patch) |
| S28 | TOC live updates during running job | FR-33a (subscribe in non-compact mode) | ✓ (post-patch) |

All scenarios covered post-patches. No remaining `GAP` rows.

## 4. Artifact Fitness Findings

### 4.1 Data & Storage

- **ProcessingJob:** schema unchanged; partial UNIQUE index respected; `request_params` JSON carries scope. Clean.
- **Summary:** rewrite migration idempotent; transaction-wrapped. NFR-06 covers safety. Clean.
- **ReadingPreset:** typography UPDATE migration with guarded WHERE — re-run is no-op. Clean.
- **BookSection:** no schema change; FR-32 derives `content_char_count` via SQL `LENGTH()` (post-patch B7) avoiding wasteful payload load.
- **Theme CSS:** all 6 themes get full variable coverage (FR-35); no missing values can no-op a click.

### 4.2 Service Interfaces

- **`GET /api/v1/processing/{id}` (NEW):** complete shape with status/progress/timestamps, 200 + 404. Clean.
- **`POST /api/v1/books/{id}/summarize` (modified 409):** sequence diagram pins concurrency; `BEGIN IMMEDIATE` explicit. Clean.
- **`GET /api/v1/books/{id}` (modified):** `content_char_count` field added to `SectionBrief`; SQL-projection mandate post-B7.
- **SSE `/api/v1/processing/{id}/stream`:** event→UI mapping enumerated (FR-11b post-patch); per L58, no orphan events for this view.
- **DELETE `/api/v1/processing/{id}`:** existing endpoint; `/jobs/{id}` Cancel binding pinned post-W1.

### 4.3 Behavior

- **Stale-sweep state machine:** PENDING/RUNNING → FAILED via on-demand sweep, transactionally. Sequence diagram. Clean.
- **Tab state machine:** trivial (toggle summary/original); URL is single source of truth post-FR-15.
- **`/jobs/{id}` view modes:** skeleton → active → terminal → 404, plus reconnect path. Post-patch B10 (skeleton) closes the only behavior gap.

### 4.4 Interface (UI in scope)

- **Component hierarchy:** §8.1 lists deltas. Clean.
- **State placement:** §8.2 covers per-state ownership.
- **Loading states:** Export FR-25 (allSettled, 250ms floor on both paths post-B5); /jobs/{id} skeleton (FR-12a post-B10); section retry uses existing SummarizationProgress.
- **Empty states:** FR-23 (Read Summary disabled), FR-22a (Export disabled when no summaries, post-B6), FR-30 ("—" rows), FR-12 mode (c) (404 view).
- **Accessibility:** NFR-01 (FontListbox = ARIA Listbox), NFR-02 (Export menu + overflow = ARIA Menu Button), NFR-07 (SectionListTable keyboard nav, post-B11).
- **Live updates on book detail during running job:** FR-33a (post-B3) subscribes the table to SSE in non-compact mode; reader-TOC compact mode does not (visual noise).

### 4.5 Wire-up

Handled in §5 Cross-Reference.

### 4.6 Operational

- **NFRs:** §6.9 covers a11y (×3), perf (×2), bundle size, migration safety.
- **Observability:** structured warning log on orphan-image strip (FR-09); logger event for on-demand stale-sweep is implicit (`error_message="Marked stale by on-demand sweep"` is observable in DB); could be enhanced but not a gap.
- **Rollout:** non-breaking; both data migrations idempotent and transaction-wrapped (NFR-06 post-B8). No feature flags needed.
- **Webfonts:** `font-display: swap` + system-font fallback chain mandated (FR-39a post-B2) → no FOIT, graceful degradation if @fontsource/* package is unreachable.

## 5. Cross-Reference (UI ↔ API)

### 5.1 Forward table

| # | Interaction | Trigger | Endpoint/Function | Req | Res complete | Errors mapped | Notes |
|---|-------------|---------|-------------------|-----|--------------|--------------|-------|
| W1 | Click Read | router-link | (SPA route) | n/a | n/a | n/a | ✓ |
| W2 | Click Read Summary | router-link to `/books/{id}/summary` | (SPA route) | n/a | n/a | n/a | ✓ disabled when no summary |
| W3 | Export ▾ → Download Markdown | onExportClick | GET `/api/v1/export/book/{id}?format=markdown` | ✓ | ✓ | ✓ | FR-25 allSettled |
| W4 | Export ▾ → Copy to Clipboard | onCopyClick | same as W3 | ✓ | ✓ | ✓ | FR-26 fallback regex pinned |
| W5 | Click section row in TOC | router-link to `/books/{id}/sections/{sid}` | (SPA route) | n/a | n/a | n/a | ✓ FR-29 tab-preservation rule |
| W6 | Toggle Original/Summary tab | toggleContent | (no API; URL state) | n/a | n/a | n/a | ✓ |
| W7 | Prev/next in reader | navigateSection | (no API; URL state) | n/a | n/a | n/a | ✓ |
| W8 | Click preset tile | applyPreset | (no API; localStorage) | n/a | n/a | n/a | ✓ |
| W9 | Pick font in FontListbox | updateSetting | (no API; localStorage) | n/a | n/a | n/a | ✓ |
| W10 | Mount /jobs/{id} | route mount | GET `/api/v1/processing/{id}` | ✓ | ✓ (post-B1) | ✓ | FR-12 enumerates terminal-card fields |
| W11 | /jobs/{id} live updates | SSE | `/api/v1/processing/{id}/stream` | n/a | ✓ (post-B4) | n/a | FR-11b enumerates event→UI mapping |
| W12 | /jobs/{id} Cancel | onClick | DELETE `/api/v1/processing/{id}` | ✓ (post-W1) | ✓ | ✓ | FR-12 binds endpoint explicitly |
| W13 | Section retry | onSummarize | POST `/api/v1/books/{id}/summarize` | ✓ | ✓ | ✓ | §7.2 modified 409 shape |
| W14 | TOC live row update | SSE (post-B3) | `/api/v1/processing/{id}/stream` (shared) | n/a | ✓ | n/a | FR-33a non-compact only |

### 5.2 Reverse scan

- POST `/api/v1/books/{id}/summarize` → consumed by W13 + upload wizard (prior bundle). ✓
- GET `/api/v1/processing/{id}` → consumed by W10. ✓ (NEW endpoint)
- SSE `/api/v1/processing/{id}/stream` → consumed by W11 (new view) + W14 (book-detail TOC) + existing `summarizationJob` store + existing `PersistentProcessingIndicator`. ✓
- DELETE `/api/v1/processing/{id}` → consumed by W12 + existing PersistentProcessingIndicator Cancel. ✓
- GET `/api/v1/books/{id}` → consumed by `BookOverviewView`. Adds `content_char_count`. ✓

No orphan endpoints. No interface action without a defined endpoint.

## 6. Pseudocode

### 6.1 JobProgressView mount — REST seed + SSE subscribe with no event loss

```
Flow: JobProgressView.vue mount
Entry: Vue Router mounts /jobs/:id

FUNCTION mountJobProgress(jobId):
  # 1. Subscribe FIRST so we don't miss events that arrive while GET is in flight
  buffer = []
  sseStream = subscribeSSE(`/api/v1/processing/${jobId}/stream`, evt => buffer.push(evt))

  # 2. Fetch initial state. Response includes `last_event_at` (ISO-8601 UTC)
  initial = await GET(`/api/v1/processing/${jobId}`)
  IF initial.status_code == 404:
    sseStream.close()
    RENDER notFoundView
    RETURN
  RENDER jobView(initial)

  # 3. If terminal at fetch time, no live updates needed
  IF initial.status IN ('COMPLETED', 'FAILED'):
    sseStream.close()
    RETURN

  # 4. Drain buffer: skip events the GET response already reflects
  cutoff = initial.last_event_at  # any event with last_event_at <= cutoff was already in `initial`
  FOR evt IN buffer:
    IF evt.last_event_at > cutoff:
      applyEvent(evt)
  buffer = null  # release for GC; future events go directly to applyEvent

  # 5. Switch SSE handler from "buffer" mode to "live apply" mode
  sseStream.onMessage = evt => applyEvent(evt)
```

**DB calls:** None on FE; backend GET resolves a single `processing_jobs` PK lookup (NFR-04).

**State transitions:** `mounting → seeded → live`; on terminal status `seeded → done`. On reconnect: `live → reseeding → live`.

**Error branches:** GET 404 → close stream, show 404 view. GET 5xx → show error card with retry button. SSE connection drop → automatic reconnect (existing 30s grace + polling fallback per recon `summarizationJob.ts:91-97`); reconnect re-runs the seed-then-drain protocol with the latest applied event's timestamp as cutoff. Buffer overflow on long GET latency → drop oldest events (acceptable since cutoff comparison handles correctness).

**Concurrency notes:** The `last_event_at` timestamp is the load-bearing invariant. Backend MUST stamp `last_event_at` on every published SSE event AND echo the same timestamp on the GET response so the cutoff comparison is meaningful — already implemented per recon `sse.py:44`. No additional locking; single-client per-job stream.

## 7. Gap Register

| # | Gap | Exposed By | Severity | Disposition |
|---|-----|------------|----------|-------------|
| S1 | REST→SSE seeding race on /jobs/{id} (events between GET response and SSE subscribe lost) | S21 + L69 | significant | Apply patch — added FR-11a (buffer-then-drain) + §6 pseudocode |
| B1 | FR-12 "completion card with summary stats" undefined | S8 | significant | Apply patch — enumerated fields in FR-12 mode (b) |
| B2 | Webfont loading lacks `font-display` strategy + fallback chain | S23 | significant | Apply patch — added FR-39a (font-display: swap + per-style fallback chain) |
| B3 | TOC live-update behavior during a running job not specified | S28 | significant | Apply patch — added FR-33a (SSE subscribe in non-compact mode) |
| B4 | FR-11/12 don't enumerate which SSE events drive which UI updates (per L58) | Bucket 2 | significant | Apply patch — added FR-11b (event→UI mapping) |
| B5 | FR-25 export loader behavior on rejection (Promise.all rejects fast) | S16 | minor | Apply patch — switched to Promise.allSettled |
| B6 | Export semantics on book with no summary content | S19 | minor | Apply patch — added FR-22a (Export ▾ disabled when summarized=0) |
| B7 | FR-32 `len(content_md)` loads full payload just to compute length | S27 | minor | Apply patch — mandate SQL `LENGTH()` projection |
| B8 | Migration transaction-wrap not stated explicitly | S22 | minor | Apply patch — extended NFR-06 with rollback semantics |
| B9 | FR-24 removal lacks L67-style grep inventory | Bucket 4 | minor | Apply patch — added grep inventory clause to FR-24 |
| B10 | /jobs/{id} initial-fetch loading state not specified | Bucket 4 | minor | Apply patch — added FR-12a (skeleton view during GET) |
| B11 | SectionListTable keyboard navigation a11y NFR missing | Bucket 4 | minor | Apply patch — added NFR-07 |
| W1 | /jobs/{id} Cancel button's API binding unspecified | Phase 5 | significant | Apply patch — FR-12 active mode binds DELETE `/api/v1/processing/{id}` |

All 13 gaps applied as patches. Zero accepted-as-risk, zero deferred to open questions in this run.

## 8. Accepted Risks

None this run. Every gap had a clear remediation that fit the spec's scope.

## 9. Open Questions

The 4 OQs from the spec carry forward unchanged (all are `before /plan` or `before /execute`):

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| OQ1 | Concrete color palettes for `paper` and `contrast` themes (FR-35). | Maneesh | before /execute |
| OQ2 | Mobile/small-viewport behavior for `SectionListTable` compact mode. | Maneesh | before /plan |
| OQ3 | Telemetry counter for orphan-image-strip (FR-09)? | Maneesh | during /execute |
| OQ4 | Cancel UI affordance consistency between `/jobs/{id}` and persistent indicator. | Maneesh | before /plan |

No new open questions added by simulation.

## 10. Spec Patches Applied

Each row corresponds to one `Edit` call against `docs/specs/2026-04-30-reader-and-book-detail-ux-fixes-spec.md`.

| # | Section | Change |
|---|---------|--------|
| 1 | §6.3 (FRs) | Added FR-11a (buffer-then-drain SSE seed); FR-11b (event→UI mapping); replaced FR-12 with enumerated terminal-card fields + Cancel API binding |
| 2 | §6.7 (FRs) | Added FR-33a (SectionListTable SSE subscription in non-compact mode) |
| 3 | §6.6 (FRs) | Added FR-22a (Export ▾ disabled when summarized=0) |
| 4 | §6.3 (FRs) | Added FR-12a (skeleton view during initial GET) |
| 5 | §6.9 (NFRs) | Added NFR-07 (SectionListTable keyboard navigation) |
| 6 | §6.8 (FRs) | Added FR-39a (font-display: swap + system-font fallback chain) |
| 7 | §6.6 (FR-25) | Replaced Promise.all with Promise.allSettled (loader floor on error path too) |
| 8 | §6.7 (FR-32) | SQL `LENGTH()` projection mandate; replaces ORM-loaded `len()` |
| 9 | §6.9 (NFR-06) | Extended with explicit transaction-wrap + rollback semantics |
| 10 | §6.6 (FR-24) | Added removal grep inventory clause |

## 11. Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | Five-check sweep: scenarios cover all 8 FR areas; all 6 buckets traversed; forward + reverse cross-reference clean; all 13 gaps have dispositions and patches; all 5 significant-severity gaps applied. Cross-checked against /simulate-spec learnings L60/L63/L64/L67/L69/L70 — each covered or N/A. | No new findings. Single review pass closes. |
