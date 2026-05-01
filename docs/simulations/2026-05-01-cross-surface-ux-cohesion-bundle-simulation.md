# Cross-Surface UX Cohesion Bundle — Simulation

**Date:** 2026-05-01
**Spec:** `docs/specs/2026-05-01-cross-surface-ux-cohesion-bundle-spec.md`
**Tier:** 2
**Status:** Complete (16 gaps, all dispositions captured)

---

## 1. Scope

**In scope:**
- Backend services + API contracts: `SettingsService.get_migration_status()` rewrite, `PresetService` CRUD + template viewer, annotation `content_type` filter
- Frontend (Vue): Book Detail tab strip + Summary tab + OverflowMenu reshape, MarkdownRenderer scoped styles, ReadingArea footer prev/next, TocDropdown char-count fix, side-panel reader-theme propagation, Settings cohesion (LlmSettings restyle, DatabaseSettings stripe removal, ThemeCard relocation), Preset CRUD UI
- Cross-cutting: reader-theme scope propagation, annotation `content_type` wiring across tab switches

**Out of scope (explicit per spec § Non-Goals):**
- DB schema changes (none touched)
- Feature flags / rollout machinery
- New design system / Tailwind→CSS-vars migration beyond LlmSettings
- Preset import/export/sharing
- Cross-projecting `section_content` highlights onto summary text
- Responsive (iPad/mobile) tuning — desktop-first per requirements; deferred to a separate bundle

**Companion specs:** none.
**Anticipated downstream consumers:** none (single-user personal tool).

---

## 2. Scenario Inventory

30 scenarios across 4 sources (spec, variant, adversarial, model-driven). Skipped categories: `auth` (single-user tool, no permission boundaries beyond system-vs-user preset).

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | User browses to `/books/3?tab=summary` (book has summary) — renders Markdown | Spec/J1 | happy |
| S2 | `/books/3?tab=summary`, no summary_md, ≥1 section summarized → empty state | Spec E1 + FR-02 | edge |
| S3 | `/books/3?tab=summary`, 0 sections summarized → Generate disabled | Spec E4 + FR-02 | edge |
| S4 | Book summary generation in progress → progress + Cancel | Req E2 | edge |
| S5 | Overflow → Customize reader → popover anchored, themes load | Spec/J2 | happy |
| S6 | First section, Summary tab → footer shows only `Next: …` | Req E3 | edge |
| S7 | Last section, Summary tab → footer shows only `← Previous: …` | Req E4 | edge |
| S8 | TOC dropdown on a 200-section book → scrolls, char counts correct | Req E11 | boundary |
| S9 | User creates user preset "foo" via form → renders with Edit/Delete | Spec/J5 | happy |
| S10 | User attempts to delete a system preset → no Delete shown; API 403 | Req E7 | auth |
| S11 | User submits New preset with name collision → 409 + inline form error | Req E8 | edge |
| S12 | Preset detail shows raw Jinja base + fragments; system = read-only | FR-16 | happy |
| S13 | Reader on Dark theme → ContextSidebar bg ≠ rgb(255,255,255) | Spec/J6 + FR-09 | happy |
| S14 | Migration-status backend raises → null + error field; UI Unknown | Req E6 + Spec E1 | failure |
| S15 | User highlights on Summary tab → persists with `content_type='section_summary'` | Spec FR-12 + E5' | happy |
| S16 | Section has only `section_content` annotations → Summary tab renders 0 highlights | Req §Non-goals | edge |
| S17 | Two browser tabs both click Generate book summary within seconds | Adversarial | concurrency |
| S18 | Connection drops mid-job → reconnect → UI knows job state | Adversarial | failure |
| S19 | Regenerate clicked while previous Generate is still running | Adversarial | concurrency |
| S20 | Tab A creates "foo"; Tab B's list stale; Tab B tries to create "foo" → collision detection | Adversarial | retry |
| S21 | Summary tab open while another tab regenerates → auto-refresh? | Adversarial | timing |
| S22 | Hand-edited preset YAML on disk has malformed facet → list endpoint behavior | Adversarial | input |
| S23 | First section `?tab=summary`, Next routes to next section `?tab=summary` but next has no summary → empty state | Model-driven | edge |
| S24 | Copy `/books/3?tab=summary` URL into new tab — initial load respects query | Model-driven | input |
| S25 | iPad / narrow viewport renders new tab strip + footer without overflow | Variant | boundary |
| S26 | ThemeCard moves to `components/shared/` — direct import of old path breaks at build time | Model-driven | input |
| S27 | BookSection annotation with legacy/unknown `content_type` value | Adversarial | input |
| S28 | Markdown content with raw HTML block — scoped styles still apply | Adversarial | input |
| S29 | PresetService facet cache stale until restart when fragment file added at runtime | Model-driven | timing |
| S30 | Active-tab state for annotation-create — Pinia vs local component state | Model-driven | input |

---

## 3. Coverage Matrix

Happy paths S1–S16 trace cleanly to spec FR-XX (full mapping: see Acceptance Criteria table in requirements doc; spec §6 mirrors 1:1). Adversarial scenarios S17–S30 surfaced gaps captured in §7 below.

Selected illustrative trace rows (full set elided for brevity — gaps are the actionable output):

| Scenario | Step | Spec Artifact | Status |
|----------|------|---------------|--------|
| S1 | Render book.summary_md on tab activation | FR-02 populated state | **GAP G5** (data path) — patched as SD22 + § 7.4 |
| S4 | Click Cancel during in-progress | FR-02 in-progress state | **GAP G2** (no endpoint named, no state outcome) — patched as SD18 + § 7.6 |
| S14 | Backend returns null + error on alembic failure | § 7.1 + FR-13 | ✓ |
| S15 | Annotation create persists with content_type='section_summary' | FR-12 + SD12 | ✓ |
| S17 | Second Generate click while first job active | (no idempotency in original spec) | **GAP G1** — patched as SD17 + § 7.5 |
| S22 | GET /presets when one YAML file is malformed | (not specified) | **GAP G4** — patched as SD21 + § 7.2 |
| S23 | Footer Next from summary tab → next section has no summary | FR-07 + SD14 | resolved as design (G8 — accept; empty state IS a valid screen) |
| S25 | Tab strip layout at 768px | (not in spec) | **GAP G9** — resolved as out-of-scope (desktop-first), § 11 note added |
| S30 | Active-tab read in annotation-create handler | SD12 (says "reader state") | **GAP G12** — deferred to /plan judgment |

---

## 4. Artifact Fitness Findings

### Bucket 1 — Data & Storage
**Skipped** — no schema changes in this bundle.

### Bucket 2 — Service Interfaces
- Migration-status response shape complete (current/latest/is_behind/error). ✓
- Preset CRUD: response shapes/codes were unspecified → **G13** (patched: 201/200/204).
- Template endpoint: 404 unspecified → **G14** (patched).
- New: idempotency contract on POST /book-summary unspecified → **G1** (patched as 409 with active_job_id).
- New: book_summary access path unspecified → **G5** (patched: embedded in GET /books/{id}).
- Annotations: existing API supports both content_type values; frontend just needs to broaden filter. ✓

### Bucket 3 — Behavior (State / Workflows)
- Book-summary generation state machine partially specified (empty / in-progress / populated) → missing **failed** state and **cancelled** outcome → **G2 + G3** (patched as SD18 + SD19; new states + Retry).
- Preset CRUD: simple, no state machine.

### Bucket 4 — Interface (UI)
- BookSummaryTab: Failed state missing → **G3** (patched).
- BookSummaryTab: cross-tab freshness when regenerated → **G7** (patched: SSE subscription).
- Footer: single-section book unspecified → **G16** (patched: footer doesn't render).
- New-preset form: empty/slug validation unspecified → **G15** (patched).
- Narrow viewport behavior unspecified → **G9** (resolved: desktop-first, deferred).

### Bucket 5 — Wire-up
Handled in §5.

### Bucket 6 — Operational
- NFRs: none specified. Acceptable for a polish bundle.
- Observability: spec adds `logger.exception("migration_status_failed")`. Preset CRUD/list should follow existing structlog patterns (no new gap; convention).
- Rollout: per-PR per-workstream, no flags. ✓

---

## 5. Cross-Reference (Frontend ↔ Backend)

### Forward (UI → API)

| W# | Interaction | Trigger | Endpoint | Req Match | Res Has Need | Error Map | Notes |
|----|-------------|---------|----------|-----------|--------------|-----------|-------|
| W1 | Load Book Detail | BookOverviewView mount | GET /api/v1/books/{id} | ✓ | **needs `book_summary` field** | — | **G5** patched: embedded per § 7.4 |
| W2 | Generate book summary | BookSummaryTab Generate | POST /api/v1/books/{id}/book-summary | ✓ | returns job_id | 409 if active job exists | **G1** patched: § 7.5 |
| W3 | Cancel generate | BookSummaryTab Cancel | (existing job-cancel endpoint) | ✓ | — | — | **G2** patched: SD18 + § 7.6 (/plan task to pin exact path) |
| W4 | Read book summary | OverflowMenu / Summary tab | (frontend route) | ✓ | — | — | ✓ |
| W5 | List presets | PresetSettings mount | GET /api/v1/summarize/presets | ✓ | + `is_system`, `description`, `facets` (existing) + `warnings[]` (per SD21) | — | **G4** patched |
| W6 | Create preset | PresetCreateEditForm save | POST /api/v1/summarize/presets | ✓ | 201 + preset object | 409, 422 | **G13** patched |
| W7 | Update preset | PresetCreateEditForm save | PUT /api/v1/summarize/presets/{name} | ✓ | 200 + updated preset | 404, 422 | **G13** patched |
| W8 | Delete preset | PresetSettings Delete + confirm | DELETE /api/v1/summarize/presets/{name} | ✓ | 204 | 403, 404 | **G13** patched |
| W9 | View raw template | PresetSettings select preset | GET /api/v1/summarize/presets/{name}/template | ✓ | ✓ | 404 | **G14** patched |
| W10 | Migration status | DatabaseSettings mount | GET /api/v1/settings/migration-status | ✓ | ✓ | structured error in body | ✓ |
| W11 | Load annotations | BookDetailView | GET /api/v1/annotations | ✓ (broadened filter) | — | — | ✓ |
| W12 | Create annotation on Summary tab | highlight create handler | POST /api/v1/annotations | ✓ (passes content_type='section_summary') | — | — | ✓ |
| W13 | Customize reader from Book Detail | OverflowMenu emit | (frontend popover only) | ✓ | — | — | ✓ |
| W14 | SSE: book-summary completion | BookSummaryTab subscribe | (existing SSE channel) | ✓ | — | — | **G7** patched |

### Reverse scan
Every spec-defined endpoint has a consumer. Every interface mutation maps to an endpoint (post-patches). No orphans.

---

## 6. Pseudocode

### 6.1 Book summary generate / regenerate / cancel

```
Flow: book_summary_generate
Entry: POST /api/v1/books/{id}/book-summary

FUNCTION generate_book_summary(book_id, preset_name):
  # SD17 — idempotency
  active = SELECT id FROM processing_jobs
           WHERE book_id = :book_id
             AND job_type = 'book_summary'
             AND status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
           LIMIT 1
  IF active EXISTS:
    RETURN 409 {detail: "...", active_job_id: active.id}

  # Validate preconditions: ≥1 section summary
  count = SELECT COUNT(*) FROM summaries
          WHERE book_id=:book_id AND content_type='section'
  IF count == 0:
    RETURN 422 {detail: "Summarize at least one section first."}

  # Queue job (existing infrastructure)
  job = INSERT INTO processing_jobs (book_id, job_type='book_summary', status='QUEUED', preset_name=:preset_name)
  RETURN 202 {job_id: job.id}

FUNCTION on_job_complete(job_id, status, summary_md, error_message):
  # Driven by existing background worker
  IF status == 'COMPLETED':
    summary_id = INSERT INTO summaries (book_id, content_type='book', summary_md=:summary_md)
    UPDATE books SET default_summary_id = :summary_id WHERE id = :job.book_id
  ELSE IF status == 'FAILED':
    UPDATE processing_jobs SET error_message=:error_message WHERE id=:job_id
  # CANCELLED: leave book.default_summary unchanged (SD18)
  EMIT_SSE('book_summary.completed', {book_id, status, summary_id})
```

**DB calls:**
- SELECT processing_jobs (idempotency check)
- SELECT COUNT summaries (precondition)
- INSERT processing_jobs
- INSERT summaries (on success)
- UPDATE books.default_summary_id (on success)
- UPDATE processing_jobs.error_message (on fail)

**State transitions:**
- processing_jobs: (none) → QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED
- book.default_summary_id: null → <id> (only on COMPLETED at book level)

**Error branches:**
- Active job exists → 409 with active_job_id (idempotency)
- 0 section summaries → 422
- LLM provider failure during run → status=FAILED, error_message captured, surfaces in BookSummaryTab Failed state (SD19)
- Worker crash mid-run → existing orphan-detection reaps the job (CLAUDE.md gotcha context)

**Concurrency notes:**
- Idempotency check + queue insert SHOULD be inside one transaction with `SELECT … FOR UPDATE` on the book row (or a conditional INSERT) to avoid two simultaneous QUEUED jobs sneaking past the check. SQLite WAL: a `BEGIN IMMEDIATE` transaction grants a reserved lock — sufficient for this single-user case.
- /plan task: confirm the existing book-summary route's transaction boundaries match the above.

### 6.2 Preset facet validation with filesystem-derived cache

```
Flow: preset_facet_validation
Entry: POST/PUT /api/v1/summarize/presets

CLASS PresetService:
  FUNCTION __init__():
    self._facet_cache = self._build_facet_cache()  # called once at service init

  FUNCTION _build_facet_cache():
    cache = {}
    FOR dimension IN ['style', 'audience', 'compression', 'content_focus']:
      dir = FRAGMENTS_DIR / dimension
      cache[dimension] = {f.stem FOR f IN dir.glob('*.txt')}
    RETURN cache

  FUNCTION validate_facets(facets: dict):
    errors = []
    FOR dim, value IN facets.items():
      IF dim NOT IN self._facet_cache:
        errors.append({dim: "unknown dimension"})
      ELIF value NOT IN self._facet_cache[dim]:
        errors.append({dim: f"unknown value '{value}' for dimension '{dim}'"})
    IF errors: RAISE ValidationError(errors)

  FUNCTION list_presets():
    out = []
    warnings = []
    FOR file IN PRESETS_DIR.glob('*.yaml'):
      TRY:
        preset = parse_yaml(file)
        self.validate_facets(preset.facets)  # only warn, don't include
        out.append(preset)
      EXCEPT (yaml.YAMLError, ValidationError) AS e:
        log.warning("preset_skipped", file=str(file), error=str(e))
        warnings.append({file: str(file.name), error: str(e)})
    RETURN out, warnings
```

**DB calls:** none (presets are filesystem).

**State transitions:** none.

**Error branches:**
- File parse error / validation error → skip + warn (SD21)
- POST/PUT with invalid facet → 422 + offending dimension/value
- POST with name collision → 409 (system OR user namespace)

**Concurrency notes:**
- File writes for create/update are not concurrency-safe across multi-process deployments, but this tool is single-process. `os.replace()` for atomic rename is sufficient on macOS/Linux.
- Cache rebuild on init only: adding a new fragment requires process restart (SD15 documented).

---

## 7. Gap Register

All 16 gaps with dispositions.

| ID | Gap | Severity | Disposition | Patch |
|----|-----|----------|-------------|-------|
| G1 | Concurrent Generate book-summary clicks (no idempotency) | significant | Apply patch | SD17 + § 7.5 (409 + active_job_id) |
| G2 | Cancel button has no endpoint named, no state outcome | significant | Apply patch | SD18 + § 7.6; FR-02 cancel returns to Empty, summary_md stays null |
| G3 | UI state when last generation failed | significant | Apply patch | SD19; FR-02 gains Failed state + Retry CTA from `processing_jobs.error_message` |
| G4 | GET /presets when YAML file malformed | significant | Apply patch | SD21 + § 7.2; skip-with-warning per file |
| G5 | BookSummaryTab data access path unspecified | significant | Apply patch | SD22 + § 7.4; embed `book_summary` in GET /books/{id} |
| G6 | Network drop mid-generation, UI recovery | minor | Apply patch | Reuse existing SSE reconnect; covered by SD20 (FR-02 SSE subscribe) |
| G7 | Auto-refresh Summary tab on cross-tab regen | minor | Apply patch | SD20 |
| G8 | Footer Next when next section has no summary | minor | Accept as risk | Empty state IS a valid screen; predictable behavior preferred over magic |
| G9 | Narrow viewport (iPad/mobile) layout | minor | Apply patch | Spec § 11 note: desktop-first; deferred to separate bundle |
| G10 | ThemeCard import-path migration (consumer enumeration) | minor | Defer to /plan | /plan grep gate already noted in spec; no spec change needed |
| G11 | Filesystem-derived facet cache stale until restart | minor | Apply patch | SD15 / § 7.2 documents restart requirement |
| G12 | "Active tab" state location for annotation-create | minor | Defer to /plan | /plan picks Pinia vs prop-drilling vs lift-to-view based on actual code shape |
| G13 | Preset CRUD response shapes/codes unspecified | minor | Apply patch | § 7.2 table: 201 / 200 / 204 + return-shape per row |
| G14 | GET /template 404 for missing preset | minor | Apply patch | § 7.2: 404 added |
| G15 | New-preset form validation for empty name/label, slug pattern | minor | Apply patch | FR-15 + § 7.2 frontend validation paragraph |
| G16 | Single-section book footer (no prev, no next) | minor | Apply patch | § 9.4: footer doesn't render at all |

---

## 8. Accepted Risks

| ID | Risk | Rationale |
|----|------|-----------|
| G8 | Footer "Next" from Summary tab can land the user on the next section's empty Summary state | The empty state already explains "no summary yet for this section" with a Generate-section-summary CTA. Adapting the footer based on the next section's summary presence adds magic that's hard to predict. Predictable beats clever for a personal tool. |

---

## 9. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Exact path of the existing job-cancel endpoint (`DELETE /api/v1/processing/{job_id}` vs `POST .../cancel`) | /plan | start of Workstream 3 (Book Summary tab) |
| 2 | Active-tab state location for annotation-create — Pinia vs `BookDetailView` local state vs lift-to-route-meta | /plan | start of Workstream 4 (Section Reader polish) |
| 3 | Confirm the existing book-summary route's transaction boundaries match the SD17 idempotency contract; if not, add `BEGIN IMMEDIATE` around the check + insert | /plan | start of Workstream 3 |

---

## 10. Spec Patches Applied

All applied via `Edit` on `docs/specs/2026-05-01-cross-surface-ux-cohesion-bundle-spec.md`:

| # | Section / Anchor | Change |
|---|------------------|--------|
| 1 | FR-02 | Added explicit Failed state + Retry CTA; pinned Cancel-returns-to-Empty semantics; added SSE subscription line |
| 2 | § 4 Decision Log | Added SD17 (409 idempotency), SD18 (cancel reuse), SD19 (failed state), SD20 (SSE), SD21 (skip malformed YAML), SD22 (embed book_summary) |
| 3 | § 7.2 Preset CRUD | Added response codes/shapes table, `warnings[]` field on list, frontend form validation paragraph, restart-required note for facet cache |
| 4 | § 7 (new subsections) | § 7.4 — embed `book_summary` in GET /books/{id}; § 7.5 — 409 idempotency on POST /book-summary; § 7.6 — cancel-endpoint /plan task |
| 5 | § 9.4 Footer | Single-section book hides footer entirely |
| 6 | § 10 Edge Cases | Added E11 (concurrent generate), E12 (cancel), E13 (failed state), E14 (cross-tab refresh), E15 (malformed YAML) |
| 7 | § 11 Configuration | Added desktop-first viewport scope note |
| 8 | § 16 Review Log | Added Loop 3 (simulation) row capturing the 16 findings + dispositions |

---

## 11. Review Log

| Loop | Findings | Changes |
|------|----------|---------|
| 1 | (a) Scenario Trace surfaced 9 adversarial gaps; Artifact Fitness surfaced 7. Cross-reference reverse scan: no orphans. Pseudocode flow 1 (book-summary generation) revealed the idempotency gap and the missing failed state. Flow 2 (preset facet validation) revealed the cache-staleness documentation gap. (b) All 16 gaps presented to user via batched `AskUserQuestion` calls (4 + 4 + 4 + remaining via 2 multi-select questions). All 16 received a disposition. (c) 13 patches applied; 1 accepted as risk; 2 deferred to /plan as open questions. | All applied — see § 10. |
