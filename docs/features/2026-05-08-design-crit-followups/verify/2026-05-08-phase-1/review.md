# Phase 1 Verification — Design-Crit Followups

**Date:** 2026-05-08
**Scope:** `--scope phase --feature 2026-05-08-design-crit-followups --phase 1`
**Phase 1 tasks:** T1, T2, T3, T4, T5, T6, T6a (7 tasks)
**Branch:** `design-crit-followups` (worktree)
**Result:** **PASS**

---

## 1. Static Verification

| Check | Outcome | Evidence |
|------|---------|----------|
| Backend lint (changed files) | Verified | `ruff check` — 4 errors, all 3 pre-existing TC001/TC002 on main; the one new I001 (import-sort on `test_audio_by_book.py`) was auto-fixed |
| Backend format | Verified | `ruff format` — applied to `reading_state_repo.py`; clean |
| Frontend type check | Verified | `vue-tsc --build --force` clean |
| Backend full suite | Verified | 1019 passed, 35 skipped, 4 deselected (`pytest -m "not integration_llm"`); baseline 1001 → +18 net new |
| Frontend full unit suite | Verified | 92 test files / 501 tests passed |

## 2. Code Quality Review

CLAUDE.md compliance check (self-review of the 7 commits):

- ✓ Repos remain thin query builders (no business logic added)
- ✓ Async-first; no sync DB access
- ✓ `selectinload` used on `ReadingState.section`/`book` for eager loading
- ✓ `Integer` PK respected (no schema changes anyway)
- ✓ Routes follow constructor-DI pattern via `get_db` / `get_reading_state_repo`
- ✓ No new `print`/`logging`; pure data plumbing
- ✓ Plan deviations recorded inline in task logs

Pre-existing TC001/TC002 lint warnings on `audio.py` and `audio_position_repo.py` are not introduced by Phase 1 changes — they exist on main.

## 3. Deploy & Integration Verification (Phase 4)

### Verification Surface (entry-gate todos)

| FR-ID / Item | Surface | Evidence type required | Outcome |
|--------------|---------|-----------------------|---------|
| FR-B01 (`firstChapter`) | Pure FE helper | Unit test | Verified |
| FR-C14 (`formatReadTime`) | Pure FE helper | Unit test | Verified |
| FR-B05a (`/continue` FM filter) | API | curl response + repo unit | Verified |
| FR-B05 (`/resume-banner`) | API (new) | curl response + repo unit | Verified |
| FR-C20 (`/audio/sections/by-book`) | API (new) | curl response + integ test | Verified |
| FR-E07a (`/audio/positions/by-book`) | API (new) | curl response + integ test | Verified |
| P13 (`/reading-state/by-book`) | API (new) | curl response + repo unit | Verified |

No UI surfaces in Phase 1 — sub-step 3d (Frontend Verification) and 3f (UX Polish & Wireframe Consistency) are NOT applicable to this phase. Phase 1 ships backend endpoints and pure-function FE helpers; FE consumption begins in Phase 3 (T12+) and is the responsibility of subsequent phase verifies.

### 3a. Migrations

NA — no schema changes (spec §10 confirms zero migrations).

### 3b. Deploy

`uv run bookcompanion serve --port 8765` started cleanly; `/api/v1/health` → `200`.

### 3c. API smoke tests (live curl against dev DB)

```
GET /api/v1/reading-state/resume-banner          → 200, schema matches §9.1
  body: { last_book_id: 1, last_section_id: 3,
          last_book_title: "Understanding Michael Porter",
          last_section_title: "Introduction",
          last_viewed_at: "2026-04-18T12:10:13",
          last_audio_*: null, last_audio_total_sentences: null }
  ✓ 12 keys present; reading fields populated from existing dev row;
    audio fields null because no audio_position seeded.

GET /api/v1/reading-state/by-book/1              → 200, all-null (UA "Unknown" has no row for book 1)
  ✓ Per spec: returns all-null fields, NOT 404.

GET /api/v1/audio/sections/by-book/1             → 200
  body: { book_id: 1, sections: [17 entries, all has_mp3:false, engine:null] }
  ✓ Schema matches AudioByBookResponse / AudioByBookEntry.

GET /api/v1/audio/positions/by-book/1            → 404 { detail: "no audio position for book" }
  ✓ Per spec: 404 when no audio position exists for the book.
```

### 3d. Frontend Verification

NA — Phase 1 ships no UI changes. The two FE helpers are pure exported functions consumed in later phases.

### 3e. Interactive Spot Checks

NA at phase scope — no UI.

### 3f. UX Polish & Wireframe Consistency

NA — zero UI surface in Phase 1.

## 4. Spec Compliance

### 4a. Requirements Compliance (Phase 1 scope)

| ID | Requirement | Outcome | Evidence |
|----|-------------|---------|----------|
| Goal G2 (Resume coherence — backend half) | Server-side filter prevents copyright rows surfacing on /continue or /resume-banner | Verified | `tests/unit/repositories/test_reading_state_repo.py::test_continue_skips_front_matter`, `::test_resume_banner_reading_skips_front_matter` |
| Cluster B partial — backend foundations | Both endpoints exist and return spec-shaped payloads | Verified | curl excerpts (3c) |
| Cluster C partial — Sections-tab batch audio backend | `/audio/sections/by-book/{id}` endpoint exists; correct shape | Verified | `test_audio_by_book.py::test_sections_by_book_marks_only_seeded_sections` |
| Cluster E partial — ResumeAffordance gate backend | `/audio/positions/by-book/{id}` 200/404 split | Verified | `test_audio_by_book.py::test_positions_by_book_*` |

### 4b. Spec FR Compliance (Phase 1 only)

| ID | FR | Outcome | Evidence |
|----|----|---------|----------|
| FR-B01 | `firstChapter(sections, bookStatus)` helper | Verified | `frontend/src/stores/__tests__/firstChapter.spec.ts` — 8 tests |
| FR-B05 | `GET /reading-state/resume-banner` returns most-recent across browsers per §9.1 | Verified | repo + integration tests; live curl |
| FR-B05a | `/continue` skips front-matter | Verified | repo unit tests |
| FR-C14 | `formatReadTime` / `formatReadTimeSum` per §11.4 | Verified | `frontend/src/utils/__tests__/readTime.spec.ts` — 14 tests |
| FR-C20 | Batch `GET /audio/sections/by-book/{book_id}` | Verified | integration tests + live curl |
| FR-E07a | `GET /audio/positions/by-book/{book_id}` | Verified | integration tests + live curl |
| D20 | FM filter implemented server-side, no migration | Verified | repo SQL uses `outerjoin` + `notin_(FRONT_MATTER_TYPES)` |
| D21 | New endpoint, not extension of /continue | Verified | route defined separately at `/resume-banner`; semantics differ |
| P13 | `/reading-state/by-book/{book_id}` for OverviewDashboard | Verified | repo + live curl |
| P17 | `last_audio_total_sentences` field on response | Verified | `test_resume_banner_includes_total_sentences_from_audio_files` confirms population from `audio_files.sentence_count` |

Edge cases:
| ID | Case | Outcome | Evidence |
|----|------|---------|----------|
| E1 | `annotations_playlist` excluded from resume-banner | Verified | `test_resume_banner_excludes_annotations_playlist` |
| E2 | `book_summary` content_type resolved via `Book.id == content_id` | Verified | `test_resume_banner_book_summary_resolves_book_directly` |
| E3 | `section_id IS NULL` reading rows still surface in /continue | Verified | `test_continue_includes_rows_with_null_section_id` |
| E4 | Empty DB returns 200 with all-null fields | Verified | `test_resume_banner_empty_db_returns_all_null` + live curl |

### 4c. Plan Compliance (Phase 1 tasks)

| Task | Outcome | Evidence |
|------|---------|----------|
| T1: firstChapter helper | Verified-complete | commit `fbb69f1`; tests `firstChapter.spec.ts` (8 pass) |
| T2: readTime utility | Verified-complete | commit `268fab2`; tests `readTime.spec.ts` (14 pass) |
| T3: /continue FM filter | Verified-complete | commit `08d8782`; `test_continue_skips_front_matter` etc. |
| T4: /reading-state/resume-banner | Verified-complete | commit `d8f5a4e`; repo + integration + live curl |
| T5: /audio/sections/by-book | Verified-complete | commit `167d4bf`; `test_sections_by_book_*` |
| T6: /audio/positions/by-book | Verified-complete | commit `167d4bf`; `test_positions_by_book_*` |
| T6a: /reading-state/by-book | Verified-complete | commit `919d761`; `test_by_book_returns_per_device_per_book_match` + live curl |

### 4d. Wireframe & UX Polish Compliance

NA — zero UI surface in Phase 1. Wireframe diff and UX checklist deferred to phase verifies that ship UI (Phase 2+).

### 4e. Gap Report

None. All Phase 1 entry-gate todos closed as Verified.

## 5. Hardened Tests

Phase 1 added 32 new tests across 4 files. No new gaps were discovered during verification (all bugs surfaced at TDD time were fixed before commit).

| File | Tests added |
|------|-------------|
| `frontend/src/stores/__tests__/firstChapter.spec.ts` | 8 |
| `frontend/src/utils/__tests__/readTime.spec.ts` | 14 |
| `backend/tests/unit/repositories/test_reading_state_repo.py` | 7 |
| `backend/tests/unit/repositories/test_audio_position_resume_banner.py` | 5 |
| `backend/tests/integration/test_api/test_resume_banner_api.py` | 1 |
| `backend/tests/integration/test_api/test_audio_by_book.py` | 5 |
| **Total** | **40** |

## 6. Final Compliance Pass

- ✓ No `TODO`/`FIXME`/`HACK` introduced in changed files (grep clean).
- ✓ No debug `print` / temporary code.
- ✓ No hardcoded values (`CHARS_PER_MINUTE` is a documented constant per spec §11.4).
- ✓ Documentation updated: 7 per-task execute logs in `docs/features/2026-05-08-design-crit-followups/execute/`. CLAUDE.md not affected (no new architectural patterns).

## 7. Result

**ok: true**
**evidence_dir: docs/features/2026-05-08-design-crit-followups/verify/2026-05-08-phase-1/**
**failures: []**

Phase 1 is sealed. /execute may proceed to Phase 2 (T7 — Chip token CSS) in a fresh session via `/pmos-toolkit:execute --resume`.
