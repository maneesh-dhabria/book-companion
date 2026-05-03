---
date: 2026-05-03
spec: docs/specs/2026-05-03-summary-and-audio-ux-fixes-spec.md
tier: 2
status: Complete (1 review loop, 0 residual gaps)
---

# Summary & Audio UX Fixes — Simulation

## 1. Scope

**In scope:** Frontend (Vue components, Pinia stores, composables, routes), Backend
(one new route `/api/v1/audio/annotations/{id}/lookup` + `ContentType.ANNOTATION`
enum extension + 409 response field on `POST /book-summary`), CSS (global
`.btn-primary`/`.btn-secondary` promotion + 9-file scoped sweep), Settings UI
(Reset button on `SettingsTtsPanel`), Web Speech engine wiring (read TTSConfig at
`useTtsEngine.load`), `mediaSession` integration on both engines, preload cache
+ `audioJob` SSE-driven invalidation.

**Out of scope** (per spec Non-Goals — not flagged as gaps): localStorage Web
Speech persistence; Cancel button on book-summary spinner; reattach-on-reload
via active-jobs endpoint; Listen on TOC/search/playlists; deep-link autoplay;
Playbar collapse; settings export/import; CLI parity; bundle-size budget.

**Companion specs:** None — single bundled spec.

**Anticipated downstream consumers:** Future per-book Web Speech overrides
(noted in req Non-Goals); future cross-book annotation views (E14 covers).

---

## 2. Scenario Inventory

35 scenarios traced. Source: 18 from spec (J1–J8 + E1–E10/E12), 2 happy-path
variants, 10 adversarial across 8 of 10 standard categories (auth N/A —
single-user local; ordering covered as concurrency/timing), 5 model-driven.

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | Generate book summary → spinner + elapsed timer until completion | Spec J1 | happy |
| S2 | Audio surface buttons render with shared classes | Spec J2 | happy |
| S3 | Listen to section summary; MP3 vs Web Speech routing | Spec J3 | happy |
| S4 | Listen to book summary | Spec J4 | happy |
| S5 | Listen to section content (large chapter) | Spec J5 | happy |
| S6 | Listen to individual annotation | Spec J6 | happy |
| S7 | Switch content mid-playback (replace immediately) | Spec J7 | happy |
| S8 | Configure Web Speech voice + rate, test, save, reset | Spec J8 | happy |
| S9 | 409 reattach on double-click Generate | Spec E1 | retry |
| S10 | Page reload mid-job (no reattach) | Spec E2 | failure |
| S11 | SSE disconnect / error mid-job | Spec E3 | failure |
| S12 | Empty annotation Listen | Spec E4 | input |
| S13 | Web Speech unsupported AND no MP3 | Spec E5 | failure |
| S14 | Persisted voice no longer present on device | Spec E6 | input |
| S15 | iOS Safari gesture chain | Spec E7 | timing |
| S16 | Playbar Close mid-Web-Speech | Spec E9 | failure |
| S17 | Voice changed while Playbar active | Spec E10 | timing |
| S18 | processing_jobs UNIQUE collision | Spec E12 | concurrency |
| S19 | First-time user, no MP3 generated, clicks Listen on summary | Variant | happy |
| S20 | Mixed-state book: some sections have MP3, others don't | Variant | edge |
| S21 | audio/lookup returns 500 during preload | Adversarial | failure |
| S22 | User saves SettingsTtsPanel from two tabs concurrently | Adversarial | concurrency |
| S23 | Rapid click Listen before preload promise resolves | Adversarial | retry |
| S24 | Cache TTL boundary: pregen MP3 lands while cache has stale `pregenerated:false` | Adversarial | stale-data |
| S25 | Deep-link to `/books/1?tab=summary` — does audioJob store mount in time for cache subscription? | Adversarial | ordering |
| S26 | Section content 50KB+ chars — preload triggers slow sanitize() per page load | Adversarial | size |
| S27 | AnnotationsView with 100 annotations — IO scroll triggers 100 lookups | Adversarial | size |
| S28 | Preload network timeout, user clicks Listen → cache miss → await breaks gesture chain | Adversarial | network |
| S29 | SSE `section_audio_completed` arrives before audioJob store mounted | Adversarial | ordering |
| S30 | Voice name `""` (TTSConfig default) → engine receives empty voice | Adversarial | input |
| M1 | Cache key collides across books — wrong content served | Model-driven | design-bug |
| M2 | Multiple `useTtsEngine()` callers — does terminate() target the active engine reliably? | Model-driven | concurrency |
| M3 | TtsPlayButton unmount: do IntersectionObservers + in-flight preloads cleanly tear down? | Model-driven | lifecycle |
| M4 | 409 reattach: elapsed timer starts at 0:00 even if real job started 8 min ago | Model-driven | UX |
| M5 | Empty annotation: button renders, click opens Playbar that immediately ends | Model-driven | UX |

---

## 3. Coverage Matrix

Spec scenarios (S1–S20) map cleanly to existing FRs and were marked ✓ on first
pass except where noted. Adversarial and model-driven scenarios surfaced 14
gaps logged with S-prefix:

| Scenario | Status | Gap(s) |
|----------|--------|--------|
| S1–S4, S7–S11, S13–S20 | ✓ | None |
| S5 (large content preload) | gap | S5-G1 → applied as G1 |
| S6 (annotation mediaSession) | partial | S6-G2 → applied as E14 |
| S12 (empty annotation) | gap | S12-G4 → applied as G4 (FR-17 visibility) |
| S21 (preload 500) | gap | S21-G5 → applied as FR-25d |
| S22 (cross-tab settings) | gap | S22-G6 → applied as E13 |
| S23 (rapid click) | gap | S23-G7 → covered by NFR-02 |
| S24 (cache TTL stale) | gap | S24-G8 → applied as FR-25f |
| S25 (deep-link timing) | gap | merged with S24-G8 |
| S26 (large content) | gap | merged with S5-G1 |
| S27 (100 annotations scroll) | partial | S27-G9 → applied as E17 |
| S28 (network timeout iOS) | gap | S28-G10 → applied as NFR-02 |
| S29 (SSE before mount) | gap | merged with S24-G8 |
| S30 (voice empty) | partial | S30-G11 → applied as E16 |
| M1 (cache key collision) | partial | M1-G12 → applied as §8.3a doc |
| M2 (terminate concurrency) | ✓ | None (race-free under sequential calls) |
| M3 (observer teardown) | gap | M3-G13 → applied as FR-25g |
| M4 (409 elapsed misleading) | gap | M4-G14 → applied as FR-07b |
| M5 (empty annotation Listen) | gap | merged with S12-G4 |

---

## 4. Artifact Fitness Findings

### Bucket 1 — Data & Storage

✓ Clean. No new tables; only `ContentType` enum extension (runtime-only,
schema-empty migration). No source_hash/sanitizer_version drift on annotation
path because annotation lookups never persist to `audio_files`.

### Bucket 2 — Service Interfaces

- **B2-G16 (minor):** New annotation lookup route didn't enumerate 500 error
  response. Applied: spec §7.1 lists `500 {"detail":"sanitization failed"}`.

### Bucket 3 — Behavior (state machines)

- **B3-G18 (minor):** terminate-vs-close micro-race on module-level `lastEngine`.
  Applied: §12 E15 documents idempotency.

### Bucket 4 — Interface (UI)

- **B4-G19 (minor):** Listen button had no loading state between click and
  Playbar mount. Applied: FR-15 click-time disabled+spinner.
- **B4-G20 (significant):** Spinner had no `aria-live` region — WCAG concern.
  Applied: FR-03 `role="status" aria-live="polite" aria-busy="true"`.
- **B4-G21 (significant):** Keyboard Space-on-focused-button double-fired
  (button activates AND global handler toggles). Applied: FR-14 excludes
  button/link/role=button targets.

### Bucket 6 — Operational

- **B6-G22 (minor):** No NFR for preload latency. Applied: §9.3 NFR-01–03.

---

## 5. Cross-Reference

Forward table (UI → API):

| # | Interaction | Trigger | Endpoint | Notes |
|---|-------------|---------|----------|-------|
| W1 | Click "Generate book summary" | BookSummaryTab btn | POST /books/{id}/book-summary | ✓ (409 extended per FR-07b) |
| W2 | Mount TtsPlayButton (preload) | onMounted IO/hover | GET /audio/lookup or /audio/annotations/{id}/lookup | ✓ (error path via FR-25d) |
| W3 | Click Listen | TtsPlayButton.onClick | (cache + engine.play) | ✓ |
| W4 | Save TTS settings | SettingsTtsPanel btn | PUT /settings/tts | ✓ existing |
| W5 | Reset to defaults | btn @click | PUT /settings/tts (defaults) | ✓ FR-26 |
| W6 | Voice Test | VoiceSampleButton | speechSynthesis.speak | ✓ existing |
| W7 | Cache subscription | AppShell onMounted | (Pinia $onAction, no API) | ✓ FR-25f |
| W8 | Playbar Close | onClose | useTtsEngine.terminate + store.close | ✓ FR-31 |

Reverse scan: every endpoint has a consumer; every UI mutating action has an
endpoint. No orphans.

---

## 6. Pseudocode

### Flow A — TtsPlayButton preload + click (gesture-critical path)

```
GLOBAL preloadCache: Map<key, CacheEntry>

COMPONENT TtsPlayButton(contentType, contentId, hasSummary?, bookId?):
  visible = ref('hidden-while-resolving')   # FR-17 render-then-resolve
  observer: IntersectionObserver
  fallbackTimer: number

  ON_MOUNT:
    if hasSummary === false: visible = false; return
    if contentType === 'section_content':                   # G1: hover/focus path
      buttonEl.addEventListener('mouseenter focus touchstart', triggerPreload, {once:true})
    else:
      observer = new IntersectionObserver(onIntersect, {rootMargin:'200px'})
      observer.observe(buttonEl)
    fallbackTimer = setTimeout(() => if visible === 'hidden-while-resolving': visible = false, 300)

  ON_INTERSECT(entries):
    if entries[0].isIntersecting:
      debounce(500ms) → triggerPreload()
      observer.disconnect()                                  # one-shot

  TRIGGER_PRELOAD():
    key = `${contentType}:${contentId}`
    cached = preloadCache.get(key)
    if cached?.result: onResolved(cached.result); return
    if cached?.promise: cached.promise.then(onResolved); return
    if cached?.error AND cached.expiresAt > now: onFailed(cached.error); return
    # FR-25c synchronous placeholder
    placeholder = {promise: pendingPromise, createdAt: now, expiresAt: now+5min}
    preloadCache.set(key, placeholder)
    fetch.then(result => {
      # FR-25e invalidation race guard
      if lastInvalidatedAt[key] > placeholder.createdAt:
        preloadCache.delete(key); triggerPreload(); return
      preloadCache.set(key, {result, createdAt:now, expiresAt:now+5min})
      onResolved(result)
    }).catch(err => {
      preloadCache.set(key, {error:err, createdAt:now, expiresAt:now+30s})
      onFailed(err)
    })

  ON_RESOLVED(result):
    visible = (webSpeechSupported || result.pregenerated) && result.sanitized_text !== ""
    clearTimeout(fallbackTimer)

  ON_FAILED(err):
    visible = webSpeechSupported   # FR-25d: error treated as pregenerated:false

  ON_CLICK:
    if !visible: return
    btnDisabled = true; btnIcon = 'spinner'                   # FR-15 G19 click feedback
    cached = preloadCache.get(key)
    if cached?.result:
      store.open({contentType, contentId})
      useTtsEngine.load(...)                                  # synchronous up to engine.play
    elif cached?.promise:
      cached.promise.then(() => { store.open(...); useTtsEngine.load(...) })  # iOS may break here
    else:                                                     # error or missing
      freshLookup = audioApi.lookup(...).then(...)            # gesture chain breaks (NFR-02)
      preloadCache.set(key, {promise:freshLookup,...})

  ON_UNMOUNT:                                                 # FR-25g
    observer?.disconnect()
    clearTimeout(fallbackTimer)
```

**DB calls:** none (client-only).
**State transitions:** `visible: 'hidden-while-resolving' → false | true` (on resolve OR 300ms timeout).
**Error branches:** preload reject → error sentinel + visibility falls back; click on error → fresh lookup; click on missing cache → fresh lookup (iOS gesture risk per NFR-02).
**Concurrency notes:** Synchronous placeholder set (FR-25c) coalesces N parallel buttons for same content. Invalidation timestamp guard (FR-25e) prevents stale-write race when SSE evicts during in-flight preload.

### Flow B — Cache subscription + invalidation

```
MODULE preloadCache:
  cache: Map<string, CacheEntry>
  lastInvalidatedAt: Map<string, number>

  initCacheSubscription():                                    # FR-25f, called from AppShell onMounted
    audioJob = useAudioJobStore()                             # auto-instantiates Pinia store
    audioJob.$onAction(({name, args}) => {
      if name !== 'applyEvent': return
      ev = args[0]
      switch (ev.event):
        case 'section_audio_completed':
          invalidate(`section_summary:${ev.section_id}`)
          invalidate(`section_content:${ev.section_id}`)
        case 'book_audio_completed':
          invalidate(`book_summary:${ev.book_id}`)
        case 'annotations_playlist_audio_completed':
          invalidate(`annotations_playlist:${ev.book_id}`)
        # _failed and _already_stale variants: same eviction (cache may be stale)
    })

  invalidate(key):
    lastInvalidatedAt[key] = Date.now()
    cache.delete(key)
```

**DB calls:** N/A.
**State transitions:** cache entry `present → absent` on event; `lastInvalidatedAt[key]` monotonic.
**Error branches:** if `useAudioJobStore()` throws (Pinia not registered), AppShell mount fails — caught by Vue's error boundary; cache still works (just no SSE-driven eviction; TTL backstop applies).
**Concurrency notes:** Pinia `$onAction` is synchronous; eviction is atomic JS. The race with in-flight preload is handled in Flow A (FR-25e) by comparing `lastInvalidatedAt[key]` against preload's `createdAt`.

---

## 7. Gap Register

23 gaps. All dispositioned as **Apply patch**. (No accepted risks; no deferred
opens.)

| # | Severity | Source | Gap | Disposition | Patch ref |
|---|----------|--------|-----|-------------|-----------|
| G1 | significant | S5/S26 | section_content sanitize() runs on every section view via IO preload — slow for large chapters | Apply | FR-25a (hover/focus path for section_content) |
| G2 | minor | S6 | mediaSession `artist` resolution on cross-book annotation views | Apply | §12 E14 |
| G3 | minor | S7 | terminate-vs-load rapid switch race | Apply | §12 E15 |
| G4 | significant | S12/M5 | Empty-content Listen button shows then immediately ends | Apply | FR-17 visibility predicate extension |
| G5 | significant | S21 | Preload error handling (500/network) unspecified | Apply | FR-25d (error sentinel + click retry) |
| G6 | minor | S22 | Cross-tab settings save is last-write-wins | Apply | §12 E13 |
| G8 | significant | S24/S25/S29 | Cache subscription depends on audioJob store mounted | Apply | FR-25f (AppShell-owned init) |
| G9 | minor | S27 | No concurrency cap on preload requests | Apply | §12 E17 |
| G10 | significant | S28 | Cold-cache slow-network click breaks iOS gesture chain | Apply | NFR-02 + /verify manual iOS test |
| G11 | minor | S30 | Voice="" → browser default, undocumented | Apply | §12 E16 |
| G12 | minor | M1 | Cache key uniqueness assumption undocumented | Apply | §8.3a |
| G13 | significant | M3 | IntersectionObserver lifecycle teardown unspecified | Apply | FR-25g (onUnmounted disconnect) |
| G14 | significant | M4 | 409 reattach: elapsed=0:00 misleading | Apply | FR-07 + FR-07b (backend includes started_at) |
| G16 | minor | B2 | Annotation lookup route missing 500 error in spec | Apply | §7.1 |
| G18 | minor | B3 | terminate-vs-close brief race | Apply | §12 E15 |
| G19 | minor | B4 | No Listen button loading feedback | Apply | FR-15 (disabled+spinner during loading) |
| G20 | significant | B4 | Spinner missing aria-live region | Apply | FR-03 (role+aria-live+aria-busy) |
| G21 | significant | B4 | Space keydown on focused Listen button double-fires | Apply | FR-14 (exclude button/link targets) |
| G22 | minor | B6 | No preload latency NFR | Apply | NFR-01 (8s soft-budget) |
| G24 | significant | P1 | PRELOAD_CACHE coalescing race (N buttons, N preloads) | Apply | FR-25c (synchronous placeholder) |
| G25 | significant | P2 | Cache subscription init lifecycle unspecified | Apply | merged with G8 → FR-25f |
| G26 | significant | P3 | Cache eviction during in-flight preload sets stale entry | Apply | FR-25e (invalidation timestamp guard) |

12 significant + 11 minor = 23 total.

---

## 8. Accepted Risks

None. All 23 gaps applied as patches.

---

## 9. Open Questions

Inherited from spec (no new opens from simulation):

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| Q2 | Mp3Engine mediaSession wiring — extend or net-new? | Agent (in /plan §8.3 audit) | Before /plan finalizes |
| Q4 | Dark-mode convention — `.dark` class vs `@media`? | Agent (in /plan §8.3 audit) | Before /plan finalizes |
| Q5 | Exact paths for SectionSummaryTab and SectionContent components | Agent (in /plan §8.3 audit) | Before /plan finalizes |

Q1 (iOS gesture) and Q3 (empty annotation) closed by simulation.

---

## 10. Spec Patches Applied

All edits applied to `docs/specs/2026-05-03-summary-and-audio-ux-fixes-spec.md`:

1. **FR-25a–h** — Rewrote single-paragraph FR-25a as 8 sub-requirements covering preload trigger (with section_content carve-out per G1), cache module shape, synchronous coalescing (G24), error sentinel (G5), invalidation race guard (G26), AppShell-owned subscription (G8/G25), observer teardown (G13), click-time gesture preservation (G10).
2. **FR-17** — Visibility predicate extended to require `sanitized_text !== ""` (G4); resolves Q3.
3. **FR-15** — Click-time button disabled+spinner state added (G19).
4. **FR-14** — Global Space handler excludes button/link/role=button event targets (G21).
5. **FR-03** — Spinner gains `role="status" aria-live="polite" aria-busy="true"` (G20).
6. **FR-07 + new FR-07b** — Backend POST /book-summary 409 response extended with `active_job_started_at` ISO8601; UI uses it instead of `Date.now()` (G14).
7. **§7.1** — Annotation lookup route lists 500 error response (G16).
8. **§9.3 (new)** — NFR-01 (preload 8s soft-budget), NFR-02 (cold-cache iOS residual risk + /verify test), NFR-03 (cache invalidation latency).
9. **§8.3a (new)** — Cache-key uniqueness assumption documented (G12).
10. **§12 E13–E17 (new)** — Cross-tab settings (G6), cross-book annotation mediaSession (G2), terminate-vs-load race (G3/G18), voice="" path (G11), scroll-triggered preload herd (G9).
11. **§17 Review Log** — Added loop 3 (/simulate-spec) entry summarizing 23 gaps and the patches applied.

---

## 11. Review Log

| Loop | Findings | Changes |
|------|----------|---------|
| 1 (this simulation) | 35 scenarios, 23 gaps total: 12 significant + 11 minor across 5 categories (preload mechanics, cache lifecycle, UX feedback, keyboard race, doc/edge nits). All dispositioned as Apply. | All 23 patches applied to the spec; no new simulation findings. |

**Exit criteria met:**
- ✓ Scenario completeness — spec J/E + variants + 10-category adversarial + model-driven
- ✓ Bucket completeness — Buckets 1, 2, 3, 4 (UI variant), 6 critiqued; Bucket 5 covered by Phase 5 cross-reference
- ✓ Cross-reference complete — forward table + reverse scan
- ✓ Gap Register integrity — all 23 have dispositions, all "Apply" appear in §10
- ✓ High-severity coverage — all 12 significant gaps have applied patches; no significant deferred or accepted-as-risk
