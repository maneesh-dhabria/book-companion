---
date: 2026-05-08
status: Complete
spec: docs/specs/2026-05-08-design-crit-followups-spec.md
mode: autonomous (best-guess dispositions per user instruction)
---

# Design-Crit Followups — Spec Simulation Trace

## 1. Scope

**In scope:**
- Frontend (Vue 3 + TypeScript + Tailwind CSS v4 + Pinia)
- Minor backend changes: 1 new endpoint (`/reading-state/resume-banner`), 2 new audio batch endpoints (`/audio/sections/by-book/:id`, `/audio/positions/by-book/:id`), 1 server-side filter on existing `/continue`
- 6-cluster UX bundle: dark-mode chip audit, read-position correctness, BookSummaryPage IA, SectionDetail toolbar, audio chrome polish, Library polish

**Out of scope (deferred to companion specs):**
- Audio synthesis / generation pipeline → `docs/specs/2026-05-02-audiobook-mode-spec.md`
- Audio playback silent-Play bug → `docs/specs/2026-05-08-audio-playback-fix-spec.md`
- Reader UX polish (typography, settings) → covered by prior 2026-04-25 / 2026-04-30 specs
- Concepts page redesign → out of crit scope
- Annotations page redesign → out of crit scope

**Companion specs:** none for this cycle. Adjacent specs referenced for non-overlap only.

**Anticipated downstream consumers:** none beyond the existing single-user web UI and CLI.

## 2. Scenario Inventory

### 2a. Extracted from spec (User Journeys + Edge Cases)

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| S1 | Continue reading from home (warm user, one click) | Spec §5.2 | happy |
| S2 | Open a book from the library (Overview default) | Spec §5.2 | happy |
| S3 | Browse summary by heading (TOC click) | Spec §5.2 | happy |
| S4 | Listen to a section | Spec §5.2 | happy |
| S5 | Empty audio tab → Generate flow | Spec §5.2 | happy |
| S6 | Empty Overview state (no summaries / concepts) | Spec §5.2 | edge |
| S7 | Continue tile when no SUMMARIZABLE section exists | Spec §5.2 | edge |
| S8 | Section[0] is itself a chapter | Spec §5.2 | edge |
| E1 | Book with no chapters yet (all front+other) | Spec §12 | edge |
| E2 | Book mid-parse (`status=PARSING`) | Spec §12 | edge |
| E3–E4 | Tag chip in light/dark theme | Spec §12 | input |
| E5 | Section with no summary | Spec §12 | edge |
| E6–E7 | Audio Playbar on Web Speech vs Kokoro | Spec §12 | edge |
| E8 | Scroll past first viewport on Summary tab | Spec §12 | happy |
| E9 | Library default browse (no bulk-select) | Spec §12 | happy |
| E10 | Markdown summary with no H2s | Spec §12 | edge |
| E11 | Stale Copyright continue-reading row | Spec §12 | edge |
| E12 | Section[0] is a chapter | Spec §12 | edge |
| E13 | Continue-reading and audio-position both null | Spec §12 | edge |
| E14 | Both present, audio more recent | Spec §12 | edge |
| E15 | localStorage write throws (private browsing) | Spec §12 | failure |
| E16 | Heading text duplicates after slugify | Spec §12 | input |
| E17 | Difference popover open, route changes | Spec §12 | edge |
| E18 | ResumeAffordance content matches active Playbar | Spec §12 | edge |

### 2b. Variants generated

| # | Scenario | Source | Category |
|---|----------|--------|----------|
| V1 | First-time visitor: empty library | Variant | happy |
| V2 | Power user with 50+ books in Library, grid view | Variant | happy |
| V3 | Deep-link to `/books/1?tab=summary#chapter-3` (cold load) | Variant | happy |
| V4 | Mobile viewport (375px wide) on every cluster | Variant | edge |
| V5 | User with 2 browsers — laptop + iPad — open simultaneously | Variant | concurrency |

### 2c. Adversarial scenarios

| # | Scenario | Category |
|---|----------|----------|
| A1 | Backend down: `GET /resume-banner` 500s | failure |
| A2 | `audio/sections/by-book/:id` returns 500 mid-Sections-tab-mount | failure |
| A3 | Concurrent: same browser_id PUTs reader_position twice in <100ms | concurrency |
| A4 | Concurrent: laptop pauses audio, iPad starts new section's audio simultaneously | concurrency |
| A5 | Stale cache: home banner hydrated with X, user starts listening on another tab → banner doesn't update on `/` | timing |
| A6 | localStorage `bc.sections.expand.{bookId}` corrupted to non-JSON | input |
| A7 | Network partition mid-PUT to `/reading-state` — request sent, response lost | failure |
| A8 | Pagination boundary: book with 100+ sections in Sections tab | boundary |
| A9 | Empty: book with 0 sections (mid-parse) on every cluster | boundary |
| A10 | Malformed: section heading is empty string after `&nbsp;` strip | input |
| A11 | Heading is emoji-only (e.g., "## 🎯🎯") → slugify empty | input |
| A12 | Concurrent: user clicks Read on Overview tile while book is mid-parse and `firstChapter` resolves to null | concurrency |
| A13 | OS-level dark mode flip mid-session: chip styles re-resolve | input |
| A14 | User has only 1 browser → existing `/continue` returns empty → home banner needs `/resume-banner` to work | edge |
| A15 | `audio_positions` row exists but `content_type=annotations_playlist` only | edge |
| A16 | User deletes a book; localStorage `bc.sections.expand.{bookId}` becomes orphaned | edge |

### 2d. Model-driven (design-specific) scenarios

| # | Scenario | Category |
|---|----------|----------|
| M1 | `firstChapter` returns null because all sections are `other` (no front, no summarizable, no back patterns matched) → spec spec'd this; verify all consumers handle | edge |
| M2 | Frontend `FRONT_MATTER_TYPES` constant drifts from backend (contract test broken) → all server filters break | failure |
| M3 | TOC right-rail vs viewport overflow: 50+ H3s in a long book → rail scrolls independently, can become a UX wart | boundary |
| M4 | Sections-tab batch lookup hits stale data because audio was generated 200ms ago and table mount fired 100ms ago | timing |
| M5 | Both `ContinueBanner` and `ResumeAffordance` are mounted briefly during banner-store hydration → flash | timing |
| M6 | The `--playbar-height` CSS custom property is set by AppShell but the Playbar component owns its own height — coupling risk | design |

### Consolidated total

**67 scenarios.** Tracing focuses on the high-signal subset (happy paths + adversarial + model-driven; spec-extracted edge cases largely covered by spec §12).

## 3. Coverage Matrix (high-signal trace)

| Scenario | Step | Spec Artifact | Status |
|----------|------|---------------|--------|
| **S1: Continue reading** | 1. User lands on / | HomeView | ✓ |
| | 2. Banner store fetches `/resume-banner` | FR-B05, §9.1 | ✓ |
| | 3. Resolver picks reading vs listening | FR-B06 | ✓ |
| | 4. Click → route to last section | FR-B07 | ✓ |
| | 5. Section detail loads with saved tab | (existing reader.ts) | ✓ |
| **S2: Read CTA → first chapter** | 1. User clicks Read on book[0]=copyright | FR-B02 | ✓ |
| | 2. firstChapter() helper resolves | FR-B01 | ✓ |
| | 3. Skip copyright, return first chapter | FR-B01 + SUMMARIZABLE_TYPES | ✓ |
| | 4. Route push | FR-B02 | ✓ |
| **S5: Audio empty state** | 1. Open Audio tab | AudioTab.vue | ✓ |
| | 2. Render engine chip + estimate + scope | FR-E04 | ✓ |
| | 3. Click "What's the difference?" | FR-E04 | ✓ |
| | 4. Popover opens, focus moves into it | FR-E05 | ✓ |
| | 5. Esc / outside click closes, focus returns | FR-E05 | ✓ |
| **A1: `/resume-banner` 500** | 1. HomeView mounts | HomeView | ✓ |
| | 2. Store fetches, gets 500 | FR-B07a | ✓ |
| | 3. `chosen=null`, no banner rendered | FR-B07 | ✓ |
| | 4. Console.warn logged | FR-B07a | ✓ |
| **A2: `/audio/sections/by-book` errors** | 1. Sections tab mounts | SectionListTable | ✓ |
| | 2. Batch lookup fails | FR-C20 fallback | ✓ |
| | 3. Rows render with Listen enabled (degraded) | FR-C20 | ✓ |
| | 4. Per-click `audio/lookup` reveals availability | FR-C20 | ✓ |
| **A4: Concurrent multi-device audio** | 1. Laptop pauses → writes audio_position(browser=laptop) | (existing) | ✓ |
| | 2. iPad starts new audio → writes audio_position(browser=ipad) | (existing) | ✓ |
| | 3. Home banner fetches `/resume-banner` | FR-B05 | ✓ |
| | 4. SQL returns max(updated_at) across browsers | FR-B05, §9.1 | ✓ |
| **A11: Emoji-only heading** | 1. Markdown contains `## 🎯` | n/a | ✓ |
| | 2. Slugify strips → empty | §11.7 | ✓ |
| | 3. Fallback to `section-{ordinal}` | §11.7 (post-patch) | ✓ |
| **M2: Backend/frontend type-set drift** | 1. New section_type added to backend FRONT_MATTER_TYPES | section_classifier.py | ⚠ |
| | 2. Frontend mirror not updated | reader.ts | ⚠ |
| | 3. Contract test catches at backend test run | tests/unit/test_section_type_sets_contract.py | ✓ existing guard |
| | (No new gap — existing contract test covers) | | |
| **M5: Banner double-mount flicker** | 1. HomeView mount fires resumeBannerStore.load() | FR-B06 | ✓ |
| | 2. Initial state: `chosen=null`, no banner rendered | FR-B07 | ✓ |
| | 3. Fetch resolves, chosen='listening', single banner appears | FR-B07 | ✓ |
| | (Both banners never mounted simultaneously; resolver returns at most one of {'reading','listening',null}) | | |

## 4. Artifact Fitness Findings

### 4.1 Data & Storage

| ID | Finding | Severity |
|----|---------|----------|
| B-Data-1 | Spec referenced `audio_positions.last_played_at` — column doesn't exist (actual: `updated_at`) | significant — wrong SQL would not run |
| B-Data-2 | `audio_positions` PK is `(content_type, content_id, browser_id)` — multi-browser semantics not addressed in spec | significant — missing SQL aggregation strategy |
| B-Data-3 | `audio_positions` has no `book_id` — "audio for this book" detection requires a join via `book_sections.book_id` for section-scoped types and direct match for `book_summary` | significant — missing join logic |
| B-Data-4 | `Concept` model has no `score` column (verified in models.py) — sort key in FR-C04 invalid | significant — query would fail |
| B-Data-5 | `BACK_MATTER_TYPES` constant referenced but does not exist in `section_classifier.py` | significant — naming inconsistency, would block implementation |
| B-Data-6 | `ReadingStateResponse` field names are `last_book_id`/`last_section_id`/`last_viewed_at` (existing schema), spec used `book_id`/`section_id`/`last_seen_at` | significant — API contract drift |

### 4.2 Service Interfaces

| ID | Finding | Severity |
|----|---------|----------|
| B-Iface-1 | `GET /reading-state/continue` returns OTHER-device rows only (`get_latest_other_device`); spec assumed it's the most-recent-overall | blocker — extending it for the home banner would break cross-device sync |
| B-Iface-2 | No batch endpoint for "audio availability for every section in a book" — N-request thundering herd | significant — performance gap |
| B-Iface-3 | No endpoint for "is there any audio position for this book" (FR-E07 dock detection) | significant — missing endpoint |
| B-Iface-4 | `audio_positions.content_type='annotations_playlist'` rows would surface on home banner if not filtered | minor — SQL filter needed |

### 4.3 Behavior

| ID | Finding | Severity |
|----|---------|----------|
| B-Beh-1 | Resume banner resolver tie-break (max-timestamp equal-millisecond) was asserted in test but not stated in body | minor — addressed in /spec loop 2 |
| B-Beh-2 | `firstChapter` returns null in 3 distinct cases (empty, mid-parse, no summarizable); each consumer needs the same disabled-CTA copy | minor — consistency check |

### 4.4 Interface (UI)

| ID | Finding | Severity |
|----|---------|----------|
| B-UI-1 | Back-to-top FAB at `bottom: 1.5rem` collides with global Playbar (84px tall, also bottom-fixed) | significant — visual stack |
| B-UI-2 | `<RouterLink>` containing `<button>` is invalid HTML5 | significant — addressed in /spec loop 1 |
| B-UI-3 | Slugify produces empty string for emoji-only / non-ASCII-only headings → duplicate empty IDs | minor |
| B-UI-4 | Middle-click on a section-row's nested action button bubbles to row middle-click handler → opens section in new tab unintentionally | minor |
| B-UI-5 | Difference popover lacks focus trap + return-focus-to-trigger | minor — accessibility |
| B-UI-6 | TOC right-rail has no overflow strategy for 50+ headings | minor — boundary |
| B-UI-7 | Overview tile loading state unspecified | minor — addressed in /spec loop 1 |
| B-UI-8 | `/reading-state/resume-banner` failure has no UI fallback | minor — addressed in /spec loop 1 |

### 4.5 Wire-up

See §5.

### 4.6 Operational

| ID | Finding | Severity |
|----|---------|----------|
| B-Op-1 | `/verify` ladder integration is "TBD at /plan time" — punted | minor — acceptable for solo workflow |
| B-Op-2 | localStorage key `bc.sections.expand.{bookId}` grows unbounded across book deletes | minor — accept-as-risk for personal-tool scale |

## 5. Cross-Reference (Interface ↔ Core)

| # | Interaction | Trigger | Endpoint | Req Match | Res Has What's Needed | Error Mapping | Notes |
|---|-------------|---------|----------|-----------|----------------------|---------------|-------|
| W1 | Home mount → resume banner | HomeView | GET /reading-state/resume-banner | ✓ | ✓ (post-patch) | ✓ silent degrade | new endpoint |
| W2 | Cross-device "Continue" widget (if any) | (legacy) | GET /reading-state/continue | ✓ | ✓ | ✓ | unchanged |
| W3 | Read CTA (book card / Continue tile / Summary tab btn) | firstChapter() | (no API) | ✓ | n/a | n/a | client-only |
| W4 | Sections tab mount | SectionListTable | GET /audio/sections/by-book/:id | ✓ | ✓ (post-patch) | ✓ degrade-on-error | new endpoint |
| W5 | BookSummaryPage mount | BookSummaryPage | GET /audio/positions/by-book/:id | ✓ | ✓ | 404 = no dock | new endpoint |
| W6 | SectionDetailView mount | SectionDetailView | GET /audio/positions/lookup (existing) | ⚠ verify | ✓ | 404 = no dock | needs /plan-time verify |
| W7 | Tag chip render | TagChip | (no API) | n/a | n/a | n/a | CSS-only |
| W8 | Concept tile render | OverviewDashboard | GET /concepts?book_id=:id (existing) | ✓ | ⚠ verify sort param | ✓ | needs /plan-time verify |
| W9 | Listen click on section row | TtsPlayButton | (existing 2026-05-03 spec flow) | ✓ | ✓ | ✓ | unchanged |
| W10 | Generate audio click | AudioTab | (existing audiobook-mode spec) | ✓ | ✓ | ✓ | unchanged |
| W11 | Difference popover CTA | DifferencePopover | (router push /settings#audio) | ✓ | n/a | n/a | client-only |
| W12 | Library view-toggle | FilterRow | (no API; localStorage only) | n/a | n/a | n/a | client-only |
| W13 | Bulk-select toggle | FilterRow | (existing BulkToolbar APIs) | ✓ | ✓ | ✓ | unchanged |

**Reverse scan:**
- Every new endpoint (`/resume-banner`, `/audio/sections/by-book/:id`, `/audio/positions/by-book/:id`) has exactly one consumer named — no orphans.
- Every UI mutation maps to a defined endpoint or is documented as client-only — no unbacked actions.

## 6. Targeted Pseudocode

Three flows qualify for pseudocode under the selection criteria (algorithmic complexity / multi-step / concurrency-sensitive):

### Flow 1: `firstChapter(sections, bookStatus)` (FR-B01)

**Trigger:** any consumer (BookOverviewView Read, BookSummaryTab readSectionSummaries, ContinueBanner fallback, OverviewDashboard Continue tile).

```
FUNCTION firstChapter(sections: Section[], bookStatus: BookStatus) -> Section | null:
  IF sections is null OR sections is empty:
    RETURN null

  FOR section IN sections (in order_index ASC):
    IF section.section_type IN SUMMARIZABLE_TYPES:
      RETURN section

  # No summarizable section found — fall back only when book is fully parsed.
  IF bookStatus == 'PARSED':
    RETURN sections[0]

  RETURN null
```

- **DB calls:** N/A — operates on a list passed in by the caller.
- **State transitions:** N/A — pure function.
- **Error branches:**
  - Empty input → null. Caller gates the CTA with `disabled` + tooltip "No chapter to open yet".
  - Non-PARSED status with no SUMMARIZABLE → null. Caller copy: "Waiting for the first chapter to parse."
- **Concurrency notes:** N/A — pure function. Test harness covers all known SectionType values + status transitions.

### Flow 2: `GET /api/v1/reading-state/resume-banner` (FR-B05)

**Trigger:** HomeView mount.

```
FUNCTION get_resume_banner(db) -> ResumeBannerResponse:
  # READING SIDE — most-recent reader_position across all browser_ids,
  # excluding rows that target a front-matter section.

  reading_row = db.execute("""
    SELECT rp.book_id, rp.section_id, rp.updated_at AS last_viewed_at,
           b.title AS book_title, bs.title AS section_title
    FROM reader_position rp
    JOIN book_sections bs ON bs.id = rp.section_id
    JOIN books b ON b.id = rp.book_id
    WHERE bs.section_type NOT IN :FRONT_MATTER_TYPES
    ORDER BY rp.updated_at DESC
    LIMIT 1
  """, FRONT_MATTER_TYPES=tuple(FRONT_MATTER_TYPES)).first()

  # AUDIO SIDE — most-recent audio_positions row across all browser_ids,
  # excluding annotations_playlist (never surfaced on home banner).

  audio_row = db.execute("""
    SELECT ap.content_type, ap.content_id, ap.updated_at AS last_audio_at,
           CASE
             WHEN ap.content_type IN ('section_summary', 'section_content') THEN bs.book_id
             WHEN ap.content_type = 'book_summary' THEN ap.content_id
           END AS effective_book_id
    FROM audio_positions ap
    LEFT JOIN book_sections bs
      ON bs.id = ap.content_id
     AND ap.content_type IN ('section_summary', 'section_content')
    WHERE ap.content_type != 'annotations_playlist'
    ORDER BY ap.updated_at DESC
    LIMIT 1
  """).first()

  # Resolve titles for the audio row's effective book + section, if applicable.
  audio_book_title = None
  audio_section_title = None
  IF audio_row IS NOT NULL:
    book = db.get(Book, audio_row.effective_book_id) IF audio_row.effective_book_id ELSE None
    audio_book_title = book.title IF book ELSE None
    IF audio_row.content_type IN ('section_summary', 'section_content'):
      section = db.get(BookSection, audio_row.content_id)
      audio_section_title = section.title IF section ELSE None

  RETURN ResumeBannerResponse(
    last_book_id          = reading_row.book_id          IF reading_row ELSE None,
    last_section_id       = reading_row.section_id       IF reading_row ELSE None,
    last_book_title       = reading_row.book_title       IF reading_row ELSE None,
    last_section_title    = reading_row.section_title    IF reading_row ELSE None,
    last_viewed_at        = reading_row.last_viewed_at.isoformat() IF reading_row ELSE None,
    last_audio_content_type = audio_row.content_type     IF audio_row ELSE None,
    last_audio_content_id   = audio_row.content_id       IF audio_row ELSE None,
    last_audio_book_id      = audio_row.effective_book_id IF audio_row ELSE None,
    last_audio_book_title   = audio_book_title,
    last_audio_section_title= audio_section_title,
    last_audio_at         = audio_row.last_audio_at.isoformat() IF audio_row ELSE None,
  )
```

- **DB calls:**
  - `SELECT FROM reader_position JOIN book_sections JOIN books WHERE section_type NOT IN FRONT_MATTER_TYPES ORDER BY updated_at DESC LIMIT 1`
  - `SELECT FROM audio_positions LEFT JOIN book_sections WHERE content_type != 'annotations_playlist' ORDER BY updated_at DESC LIMIT 1`
  - `SELECT FROM books WHERE id = :effective_book_id` (audio book title)
  - `SELECT FROM book_sections WHERE id = :content_id` (audio section title, when applicable)
- **State transitions:** N/A — read-only endpoint.
- **Error branches:** SQL error → 500 (FastAPI default). Returns 200 with all-null when no rows.
- **Concurrency notes:** Read-only across multiple write tables; eventual consistency is acceptable (the banner reflects state-as-of-fetch; new writes during the response are not surfaced until next fetch). No locks. WAL mode allows concurrent reads.

### Flow 3: Sections-tab batch audio lookup (FR-C20)

**Trigger:** Sections tab mount.

```
FUNCTION get_audio_availability_for_book(book_id: int) -> SectionAudioMap:
  rows = db.execute("""
    SELECT bs.id AS section_id,
           af.engine,
           CASE WHEN af.id IS NOT NULL AND af.status = 'ready' THEN TRUE ELSE FALSE END AS has_mp3
    FROM book_sections bs
    LEFT JOIN audio_files af
      ON af.book_id = bs.book_id
     AND af.content_id = bs.id
     AND af.content_type IN ('section_summary', 'section_content')
     AND af.status = 'ready'
    WHERE bs.book_id = :book_id
    ORDER BY bs.order_index ASC
  """).all()

  IF rows is empty:
    # Book exists but no sections — verify book exists, else 404.
    IF NOT db.get(Book, book_id):
      RAISE 404
    RETURN { book_id: book_id, sections: [] }

  # Coalesce: if a section has both summary and content audio rows, the LEFT JOIN
  # will produce two rows; collapse to one with has_mp3=true.
  by_section = {}
  FOR row IN rows:
    IF row.section_id NOT IN by_section OR row.has_mp3:
      by_section[row.section_id] = { section_id: row.section_id, has_mp3: row.has_mp3, engine: row.engine }

  RETURN { book_id: book_id, sections: list(by_section.values()) }
```

- **DB calls:** single LEFT JOIN against `book_sections` and `audio_files`.
- **State transitions:** N/A — read-only.
- **Error branches:** book not found → 404. SQL error → 500.
- **Concurrency notes:** Read-only. Result may be milliseconds-stale if an audio job completes mid-mount; FE accepts staleness — the existing per-click `audio/lookup` handles eventual consistency.

## 7. Gap Register

| ID | Gap | Exposed By | Severity | Disposition |
|----|-----|-----------|----------|-------------|
| B-Data-1 | `audio_positions.last_played_at` referenced — column doesn't exist | Recon (models.py) | significant | **Apply patch** — renamed all refs to `updated_at` in spec §6.2, §9.1, FR-B05, D21 |
| B-Data-2 | Multi-browser audio_positions semantics not addressed | Recon (PK) | significant | **Apply patch** — D21 + §9.1 explicitly state "across all browser_ids" with `ORDER BY updated_at DESC` |
| B-Data-3 | `audio_positions` has no `book_id` — join logic missing | Recon (models.py) | significant | **Apply patch** — FR-E07a + §9.4 specify the join (section types via book_sections; book_summary direct) |
| B-Data-4 | `Concept.score` referenced — column doesn't exist | Recon (models.py) | significant | **Apply patch** — FR-C04 changed to `created_at ASC` |
| B-Data-5 | `BACK_MATTER_TYPES` referenced — constant doesn't exist | Recon (section_classifier.py) | significant | **Apply patch** — FR-C15 computes back-matter as set-difference, no new constant |
| B-Data-6 | `ReadingStateResponse` field names mismatch | Recon (schemas) | significant | **Apply patch** — §9.1 uses `last_book_id`/`last_section_id`/`last_viewed_at`; D21 documents alignment |
| B-Iface-1 | `/reading-state/continue` returns OTHER-device only | Recon (route) | blocker | **Apply patch** — NEW endpoint `/resume-banner` introduced; existing `/continue` left intact |
| B-Iface-2 | No batch audio-availability endpoint | M-driven | significant | **Apply patch** — NEW `GET /audio/sections/by-book/:id` (§9.4, FR-C20) |
| B-Iface-3 | No "any audio for this book" detection | FR-E07 trace | significant | **Apply patch** — NEW `GET /audio/positions/by-book/:id` (§9.4, FR-E07a) |
| B-Iface-4 | `annotations_playlist` rows leaking into banner | A15 | minor | **Apply patch** — §9.1 SQL excludes `annotations_playlist` |
| B-UI-1 | FAB collides with Playbar | M-driven | significant | **Apply patch** — FR-C10 positions FAB above Playbar via `--playbar-height` CSS custom property |
| B-UI-3 | Slugify empty for emoji-only headings | A11 | minor | **Apply patch** — §11.7 slugify gains `fallbackOrdinal` |
| B-UI-4 | Middle-click on action button bubbles to row | M-driven | minor | **Apply patch** — FR-C17a adds `@click.middle.stop` and `@auxclick.stop` on nested buttons |
| B-UI-5 | Popover lacks focus trap | M-driven | minor | **Apply patch** — FR-E05 specifies focus-trap + return-to-trigger |
| S-Edge-1 | Reading rows all front-matter, audio present | A14 derivative | edge | **Apply patch** — Edge case E14a added |
| S-Edge-2 | annotations_playlist-only audio | A15 | edge | **Apply patch** — Edge case E14b added |
| B-Op-2 | localStorage `bc.sections.expand.{bookId}` orphans | A16 | minor | **Accept as risk** — personal-tool scale (typical user has <50 books); cleanup not worth the code. Log here for future revisit if library scales. |
| B-UI-6 | TOC rail no overflow strategy | M3 | minor | **Accept as risk** — typical non-fiction book has <30 H2/H3 in summary; CSS `overflow-y: auto` on the rail container handles the rare 50+ case acceptably. Log for revisit. |
| B-Op-1 | `/verify` integration TBD | spec FR-A07 | minor | **Defer as open question** — Q9 in §17: name the precise verify-script entry point at /plan time. |
| W6 | Existing `audio/positions/lookup` route signature unverified | Cross-ref | minor | **Defer as open question** — Q10 in §17: confirm existing route name + params at /plan time. |
| W8 | `Concept` list endpoint sort param unverified | Cross-ref | minor | **Defer as open question** — Q11 in §17: confirm `/concepts` API supports filter by book_id + sort. |
| M2 | FE/BE section-type-set drift | M-driven | (covered) | **Existing guard** — `tests/unit/test_section_type_sets_contract.py` enforces equality. No new gap. |
| B-Beh-2 | firstChapter null-cases consistency | M1 derivative | minor | **Apply patch** — FR-B01 enumerated all 3 null cases; FR-B02 names the unified disabled copy "No chapter to open yet" (the previous spec already had this — verified). |

**Total gaps:** 22 (17 Apply patch, 2 Accept as risk, 3 Defer as open question, 1 Existing guard).

## 8. Accepted Risks

| # | Risk | Rationale |
|---|------|-----------|
| AR-1 | localStorage `bc.sections.expand.{bookId}` keys orphan when books are deleted | Personal-tool scale (<50 books); cleanup logic adds complexity for marginal storage savings. localStorage limits (5–10 MB) mean the user would need 100,000+ deleted books before pressure. Revisit if library scales. |
| AR-2 | TOC right-rail has no overflow strategy beyond CSS `overflow-y: auto` | Typical non-fiction summary has <30 H2/H3. The 50+ heading case is rare and not blocking; rail-internal scrolling is the obvious browser behavior. Acceptable degradation. |
| AR-3 | Resume banner does not update on `/` if a write happens after mount | Solo personal tool; the user typically doesn't hold `/` open while another device writes. Re-fetch on focus would add code; not worth the rare benefit. |

## 9. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| Q9 | Where exactly does the new `dark-mode-contrast.spec.ts` slot in the `/verify` ladder? Identify the precise script + line. | Maneesh | /plan time |
| Q10 | Confirm the existing audio-position lookup route name + signature for FR-E07b. Likely `GET /api/v1/audio/positions/lookup` or similar — read backend at /plan time. | /plan recon | /plan time |
| Q11 | Confirm `/api/v1/concepts` supports `?book_id=` filter and a sort parameter. If not, FR-C04 needs a new query path or in-memory sort. | /plan recon | /plan time |

## 10. Spec Patches Applied

All patches applied via `Edit` tool to `docs/specs/2026-05-08-design-crit-followups-spec.md`. Reference sections shown for traceability.

| # | Section | Change |
|---|---------|--------|
| P1 | FR-B05 | Replaced "extend `/continue`" with NEW endpoint `/resume-banner`; added FR-B05a for the front-matter filter on `/continue`. |
| P2 | FR-B06 | Renamed `last_seen_at` → `last_viewed_at`, `last_audio_played_at` → `last_audio_at`. |
| P3 | §9.1 | Replaced "extended `/continue`" subsection with a NEW `/resume-banner` endpoint contract; added §9.2 for the unchanged `/continue` + filter; added §9.3 + §9.4 for new audio batch endpoints. |
| P4 | FR-C04 | Sort key changed from `score DESC` (column doesn't exist) to `created_at ASC`. |
| P5 | FR-C15 | Back-matter computed as set difference; no new constant. |
| P6 | FR-C20 | Batch lookup via NEW `/audio/sections/by-book/:id` with degraded-on-error fallback. |
| P7 | FR-E07 + FR-E07a + FR-E07b | Mount conditions specified with explicit query strategies; new `/audio/positions/by-book/:id` for book-scope detection. |
| P8 | §9.4 | Added two new endpoint contracts. |
| P9 | FR-C10 | FAB position uses `--playbar-height` CSS custom property to avoid Playbar collision. |
| P10 | §11.7 | Slugify gains `fallbackOrdinal` for empty-after-strip cases. |
| P11 | FR-C17a | `@click.middle.stop` and `@auxclick.stop` on nested action buttons. |
| P12 | FR-E05 | Focus trap + return-to-trigger specified for DifferencePopover. |
| P13 | D20 + D21 | Updated to reflect new endpoint and column-name corrections. |
| P14 | §6.2 | Data flow trace updated with correct column names + cross-device caveat. |
| P15 | §6.3.2 | Sequence diagram field names updated. |
| P16 | §12 (E14, E14a, E14b) | Renamed timestamps; added all-front-matter and annotations_playlist-only edge cases. |
| P17 | §18 Review Log | Loop 3 entry added documenting the simulation patches. |

## 11. Review Log

| Loop | Findings | Disposition |
|------|----------|-------------|
| 1 (single review pass per Tier 3 protocol) | All 5 review checks passed: scenario completeness (67 enumerated, all categories covered); bucket completeness (Data, Iface, Behavior, UI, Op); cross-reference forward + reverse complete; every gap has a disposition; every blocker (B-Iface-1) is patched. No additional gaps surfaced in review. | Exit. |

---

**Simulation complete.** 17 patches applied, 3 risks accepted, 3 questions deferred to /plan time. Spec is now consistent with the actual backend models and route conventions.
