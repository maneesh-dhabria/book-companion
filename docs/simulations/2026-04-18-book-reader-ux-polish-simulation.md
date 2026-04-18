# Book Reader UX Polish — Simulation

**Date:** 2026-04-18
**Spec:** `docs/specs/2026-04-18-book-reader-ux-polish-spec.md`
**Tier:** 2 — Enhancement
**Status:** Complete; 17 gaps surfaced, 13 patched inline, 4 accepted as documented risks.

---

## 1. Scope

**In scope (single spec, single PR):**
- Backend: shared `section_classifier` module (EPUB + PDF); two Alembic data migrations (image backfill, section reclassification + summary prune); section response extensions (`summary_md`, `is_summarizable`); book response extension (`summary_progress`); summarize endpoint `scope`+`section_id` extension; SSE event payload extensions + new `section_started` / `processing_started` events.
- Frontend: `reader.ts` landing + `updateSection`; `TOCDropdown` Front Matter accordion; `SummaryEmptyState` component (4 states); `SummarizationProgress` component; `summarizationJob` store; `ReadingArea` post-DOMPurify link rewriter; `link-policy.ts` + Vitest; `processing.ts` TS mirror.
- Ops: migration logging via structlog, NFRs on migration + per-request cost, security (rel=noopener), accessibility (native `<details>`/`<summary>`).

**Out of scope (per spec non-goals):** footnote popovers / in-reader anchor navigation; per-book configurable summarizable types; summarizer internals; per-section commit mechanics (owned by `post-install-runtime-quality-spec`); Re-summarize All UI; Cover visual handling.

**Companion specs:** none — final consumer is this spec.
**Anticipated consumers:** none beyond this release.

---

## 2. Scenario Inventory

27 scenarios enumerated across four passes.

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | First open of Porter, no saved reading-state → lands on Ch 1 | Spec J1 | happy |
| S2 | Click Copyright inside Front Matter accordion → "Summary not applicable" | Spec J1 | happy |
| S3 | Open summarized chapter, click Summary tab → markdown renders | Spec G3 | happy |
| S4 | Open unsummarized chapter, click Summary tab → "Not yet summarized" + CTA | Spec FR-33 | happy |
| S5 | Click *Summarize this section* CTA → Generating → rendered | Spec §5.1 | happy |
| S6 | Upgrade library: migrations run, images render, Front Matter grouped | Spec J3 | happy |
| S7 | Click *Summarize pending* on Porter (counter 4/12 → 12/12 live) | Spec J4 | happy |
| S8 | External link + footnote anchor + heading self-anchor in content | Spec J5 | happy |
| S9 | First open with SAVED reading-state (position overrides landing logic) | Variant | happy |
| S10 | Open book with ONLY front-matter (reference-only library) | Spec E2 | edge |
| S11 | Brand-new book imported AFTER fixes — migration no-op for that book | Spec E11 | edge |
| S12 | Power-user library (100 books / 2000 sections) — migration runtime | NFR-01 | boundary |
| S13 | LLM provider crashes mid-section | Adversarial | failure |
| S14 | Two `scope="pending"` POSTs concurrently (user double-clicks) | Spec E6 | concurrency |
| S15 | SSE connection drops mid-job | Spec E4 | failure |
| S16 | SSE fails to open post-POST (30s grace + polling) | Spec E4a | failure |
| S17 | User navigates away during active job; comes back | Spec E5 | timing |
| S18 | Migration process killed mid-run | Adversarial | failure |
| S19 | POST `/summarize` with `scope="section"` + `section_id` from another book | Spec FR-24 | auth/boundary |
| S20 | `section_completed` arrives for `section_id` no longer in `reader.sections` | Model-driven | ordering |
| S21 | Clock skew / 60s batch window edge | Model-driven | timing |
| S22 | FRONT_MATTER_TYPES drift between backend and frontend | Model-driven | input |
| S23 | `__IMG_PLACEHOLDER__` inside a code fence in user content | Model-driven | input |
| S24 | Book section titled "Contents of Chapter 1" matches TOC pattern | Model-driven | input |
| S25 | Part-header content-aware threshold with markdown syntax | Model-driven | boundary |
| S26 | Per-section CTA on non-summarizable section (glossary) | Spec E3 | behavior |
| S27 | `scope="pending"` click while single-section job running | Model-driven | concurrency |

---

## 3. Coverage Matrix (gap-producing rows only)

| # | Scenario | Step | Spec Artifact | Status |
|---|----------|------|---------------|--------|
| S13 | LLM crashes mid-section | Frontend receives `section_failed` | No `onSectionFailed` handler; no Failed state in `SummaryEmptyState` | **GAP G3** |
| S14 | Two concurrent pending POSTs | Race on in-flight section | Skip-check fires before LLM; duplicate work possible in narrow window | **GAP G4** |
| S15 | SSE drops mid-job | `activeJobSectionId` persists | E4 only clears `jobId` | **GAP G5** |
| S18 | Migration killed mid-run | Partial commit semantics | Commit granularity unspecified | **GAP G6** |
| S20 | Stale section_completed | `updateSection` behavior | FR-39 silent on missing-section case | **GAP G7** |
| S22 | Backend/frontend sets drift | No sync mechanism | FR-06 + FR-30 independent constants | **GAP G8** |
| S24 | "Contents of Chapter 1" → front-matter | TOC regex too broad | `\bcontents\b` pattern | **GAP G9** |
| S25 | part_header threshold | `strip_markdown` undefined | FR-03 references undefined helper | **GAP G10** |

Scenarios S1–S8, S11, S17, S19, S26 trace cleanly. S9, S10, S12, S16, S21, S23, S27 surfaced minor gaps tracked below.

---

## 4. Artifact Fitness Findings

### Bucket 1 — Data & Storage
- ✓ `section_type` indexed; `default_summary_id` nullable FK.
- **G12 (minor)** — Migration B doesn't bump `updated_at` on reclassified sections.

### Bucket 2 — Service Interfaces
- ✓ All request/response shapes complete; error codes defined.
- **G13 (minor)** — POST `/summarize` has no idempotency key; duplicate submits create duplicate `ProcessingJob` rows.
- **G14 (minor)** — Event ordering (`processing_started` before all `section_*`) is implicit; no invariant stated.

### Bucket 3 — Behavior
- ✓ ProcessingJob states existing.
- **G15 (significant; merged with G3)** — `SummaryEmptyState` lacks a Failed state; rolled into G3.

### Bucket 4 — Interface (UI)
- ✓ Component hierarchy / state placement / deep-link support.
- **G16 (minor)** — Saved reading position could land on a reclassified front-matter section post-migration.

### Bucket 6 — Operational
- **G2 (minor)** — NFR-01 / NFR-01a are aspirational, not benchmark-tested.
- **G17 (minor)** — Migration uses `print()` not `structlog` (repo convention).

---

## 5. Interface ↔ Core Cross-Reference

| # | Interaction | Trigger | Endpoint/Function | Req/Res/Errors | Notes |
|---|-------------|---------|-------------------|----------------|-------|
| W1 | Load book detail | BookDetailView mount | GET /books/{id} | ✓ / ✓ incl `summary_progress` / existing 404 | clean |
| W2 | Load section | route change | GET /books/{id}/sections/{sid}?include_content=true | ✓ / ✓ incl `summary_md`+`is_summarizable` / existing | clean |
| W3 | Click Summarize pending | SummarizationProgress | POST /summarize `{scope:'pending'}` | ✓ / job_id / 422, 400 | clean |
| W4 | Click Summarize this section | SummaryEmptyState | POST /summarize `{scope:'section', section_id}` | ✓ / job_id / 422 | clean |
| W5 | Subscribe to job progress | startJob | connectSSE | ✓ / section_started+completed+processing_started+completed / onError | clean post-FR-28/28a |
| W6 | React to section_completed | SSE handler | GET section | ✓ / updated section / **missing 404 handling** | **GAP G7** |
| W7 | React to section_failed | — | — | — | **merged into G3** |
| W8 | React to section_skipped / section_retrying | — | — | — | **merged into G3** |

**Reverse scan:** backend emits `section_skipped` / `section_retrying` / `section_failed` (existing + FR-28 adds `section_id`); frontend had no handler slots. Rolled into G3.

---

## 6. Pseudocode

### Flow A — Migration B `reclassify_section_types.upgrade()`

```
Entry: alembic upgrade head

FUNCTION upgrade():
  conn = op.get_bind()
  log = structlog.get_logger()
  stats = {reclassified:0, pruned:0, preserved:0, books:set()}
  books = conn.execute(SELECT DISTINCT book_id FROM book_sections ORDER BY book_id)
  for book_id in books:
    rows = conn.execute(SELECT id, title, content_md, section_type, default_summary_id
                        FROM book_sections WHERE book_id=:bid ORDER BY order_index)
    for row in rows:
      new_type = detect_section_type(row.title, row.content_md)
      if new_type == row.section_type:
        continue
      conn.execute(UPDATE book_sections
                   SET section_type=:new_type, updated_at=CURRENT_TIMESTAMP
                   WHERE id=:id)
      stats.reclassified += 1
      stats.books.add(book_id)
      if new_type in FRONT_MATTER_TYPES and row.section_type not in FRONT_MATTER_TYPES:
        count = conn.execute(SELECT count(*) FROM summaries
                             WHERE content_type='section' AND content_id=:id).scalar()
        if count == 1:
          conn.execute(DELETE FROM summaries WHERE content_type='section' AND content_id=:id)
          conn.execute(UPDATE book_sections SET default_summary_id=NULL WHERE id=:id)
          stats.pruned += 1
        elif count > 1:
          batch_end = conn.execute(SELECT max(s.created_at) FROM summaries s
                                   JOIN book_sections bs ON bs.id=s.content_id
                                   WHERE s.content_type='section' AND bs.book_id=:bid).scalar()
          cutoff = batch_end - timedelta(seconds=60)
          newest_non_batch = conn.execute(SELECT id FROM summaries
                                          WHERE content_type='section' AND content_id=:id
                                            AND created_at < :cutoff
                                          ORDER BY created_at DESC LIMIT 1).scalar()
          conn.execute(UPDATE book_sections SET default_summary_id=:new_default
                       WHERE id=:id)
          stats.preserved += 1
    log.info("migration_reclassify_book", book_id=book_id, ...per_book_counters)
    # commit per book (FR-18a)
  log.info("migration_reclassify_complete", **stats)
```

- **DB calls:** `SELECT DISTINCT book_id`; `SELECT rows per book`; `UPDATE book_sections.section_type + updated_at`; `SELECT count summaries`; `DELETE summaries`; `SELECT max(created_at)` + `SELECT newest_non_batch`; `UPDATE book_sections.default_summary_id`.
- **State transitions:** `section.section_type: <old> → <front_matter_or_summarizable>`; `section.default_summary_id: <auto-id> → NULL` (prune) or `→ <user-curated-id>` (re-point).
- **Error branches:** Pure-regex classifier shouldn't raise; any DB error aborts the revision, Alembic leaves it not-applied, retry runs on next startup (idempotent per FR-17).
- **Concurrency notes:** Runs synchronously before API binds port. Single writer, single SQLite connection. Per-book commits bound lock duration.

### Flow B — `summarizationJob` store state machine on SSE events

```
state: {bookId, jobId, activeJobSectionId, scope, phase: 'idle'|'starting'|'running'|'done',
        failedSections: Map<section_id, error>, pollingHandle: Timeout|null}

FUNCTION startJob(bookId, params):
  reset()
  self.bookId = bookId
  self.phase = 'starting'
  self.scope = params.scope
  if params.scope === 'section' && failedSections.has(params.section_id):
    failedSections.delete(params.section_id)  # retry semantics
  resp = POST /books/{bookId}/summarize params
  self.jobId = resp.job_id
  connectSSE(self.jobId, {
    onProcessingStarted: (d) => self.phase='running'; self.totalSections=d.total_sections
    onSectionStarted:    (d) => self.activeJobSectionId=d.section_id
    onSectionCompleted:  (d) => { reader.updateSection via refetch(d.section_id);
                                  self.activeJobSectionId=null; bumpProgress() }
    onSectionFailed:     (d) => { failedSections.set(d.section_id, d.error);
                                  self.activeJobSectionId=null }
    onSectionSkipped:    (d) => bumpProgress()
    onSectionRetrying:   (d) => self.activeJobSectionId=d.section_id
    onProcessingCompleted:(d) => { self.phase='done'; self.reset() }
    onProcessingFailed:  (d) => { self.phase='done'; toast(d.error); self.reset() }
    onError:             (e) => { self.activeJobSectionId=null;
                                  scheduleBookRefetchPolling() }  # E4 / E4a
  })

FUNCTION reset():
  close EventSource; clear pollingHandle; all fields → idle state.

FUNCTION scheduleBookRefetchPolling():
  every 5s: refetch GET /books/{bookId}; update summary_progress;
  stop when phase='done' OR user navigates away.
```

- **DB calls:** N/A (frontend). Drives section and book GETs on event handlers.
- **State transitions:** `phase: idle → starting → running → done`; `activeJobSectionId: null ↔ <id>` paired with section_started/completed; `failedSections` entries added on failure, removed on retry.
- **Error branches:** `onError` → clear active section + polling fallback; `onSectionFailed` → record error for retry UI; `onProcessingFailed` → toast + reset.
- **Concurrency notes:** EventSource events are serialized by the browser. `refetch(section_id)` is async; if router guard's `reset()` ran mid-refetch, `reader.updateSection` silently no-ops for unknown bookId.

---

## 7. Gap Register (final — all dispositioned)

| # | Gap | Exposed By | Severity | Disposition |
|---|-----|------------|----------|-------------|
| G1 | FR-31 landing precedence implicit | S9 | minor | **Patched** — explicit 4-level precedence in FR-31 |
| G2 | NFR-01 / NFR-01a claims not benchmarked | S12 | minor | **Accepted risk** — aspirational; observable in use |
| G3 | No `onSectionFailed`/`Skipped`/`Retrying` handlers; missing Failed state | S13+B3+W7+W8 | significant | **Patched** — FR-33 gains state (d); FR-39a adds three handler slots; FR-38 gains `failedSections` map |
| G4 | Two concurrent pending POSTs can duplicate LLM work | S14 | minor | **Accepted risk** — documented in §12 Rollout |
| G5 | SSE drop leaves activeJobSectionId set | S15 | minor | **Patched** — E4 now clears `activeJobSectionId` + polls |
| G6 | Migration commit granularity unspecified | S18 | minor | **Patched** — FR-18a specifies per-book commits |
| G7 | `updateSection` unknown section_id unspecified | S20+W6 | minor | **Patched** — FR-39 defines silent no-op + console.warn; 404 on refetch also no-ops |
| G8 | FRONT_MATTER_TYPES drift | S22 | significant | **Patched** — FR-06a adds code-comment discipline + backend contract test reading both files |
| G9 | TOC regex `\bcontents\b` too permissive | S24 | significant | **Patched** — FR-02 regex anchored to whole-title match |
| G10 | `strip_markdown()` undefined | S25 | significant | **Patched** — FR-03 rewritten to use raw `len(content_md or "")` with rationale |
| G11 | 60s auto-batch window not justified | S21 | minor | **Patched** — FR-14 gains justification paragraph |
| G12 | Migration B doesn't bump `updated_at` | B1 | minor | **Patched** — FR-13 updates `updated_at` alongside `section_type` |
| G13 | No idempotency key on POST /summarize | B2 | minor | **Accepted risk** — documented in §12 Rollout |
| G14 | Event ordering implicit | B2 | minor | **Patched** — FR-28b states the invariant |
| G15 | SummaryEmptyState missing Failed state | B3 | significant | **Patched** (merged with G3) |
| G16 | Saved position on reclassified front-matter section | B4 | minor | **Accepted risk** — one click for user to navigate away; documented |
| G17 | Migration uses `print()` not structlog | B6 | minor | **Patched** — FR-15 uses `structlog.get_logger()` |

---

## 8. Accepted Risks

1. **Concurrent `scope="pending"` races (G4)** — two simultaneous POSTs can invoke the LLM for the same in-flight section before the first's summary commits. One wasted LLM call, two Summary rows (latest wins). Frontend disabled-while-running button prevents common double-click; cross-tab is rare. Per-book advisory lock rejected as overkill.
2. **Duplicate `ProcessingJob` rows (G13)** — network retries on POST /summarize create multiple job rows. Metadata noise only; no correctness impact.
3. **Saved position on reclassified section (G16)** — user's resume lands on a now-front-matter section. One click to move on.
4. **NFR-01 / NFR-01a aspirational (G2)** — no benchmark tests. Migration + book GET perf self-observable.

---

## 9. Open Questions

None. All gaps resolved or explicitly accepted as risks.

---

## 10. Spec Patches Applied

All edits applied to `docs/specs/2026-04-18-book-reader-ux-polish-spec.md` during Phase 7:

| Gap | Spec Section | Change |
|-----|--------------|--------|
| G3 / G15 / W7 / W8 | FR-33 | Added state (d): Failed + Retry button |
| G3 / W7 / W8 | FR-39a | Added 3 handler slots: onSectionFailed, onSectionSkipped, onSectionRetrying |
| G3 | FR-38 | Added `failedSections: Map<number, string>` store field + handler wiring |
| G8 | FR-06a (new) | Code-comment discipline + backend contract test |
| G9 | FR-02 | TOC regex anchored to whole-title |
| G10 | FR-03 | Use raw `len(content_md or "")`; document rationale |
| G6 | FR-18a (new) | Per-book commit semantics |
| G11 | FR-14 | 60-second window justification paragraph |
| G12 | FR-13 | UPDATE updated_at alongside section_type |
| G17 | FR-15 | structlog instead of print() |
| G1 | FR-31 | Explicit 4-level landing precedence |
| G14 | FR-28b (new) | Event ordering invariant |
| G5 | E4 edge case | onError clears activeJobSectionId + starts polling |
| G7 / W6 | FR-39 | Missing-section no-op + console.warn; refetch 404 no-op |
| G4, G13, G16, G2 | §12 Rollout | Accepted Risks block added |

---

## 11. Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | — | Single-pass review completed inline with Phase 9 before commit. |
