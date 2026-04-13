# Post-Install Runtime Quality — Requirements

**Date:** 2026-04-12
**Status:** Draft
**Tier:** 2 — Enhancement

## Problem

After the zero-dependency packaging work shipped, the first real end-user session against an installed wheel surfaced four runtime quality issues — one serious, three minor — that together make the post-install experience feel fragile. The serious one: concurrent writes to the SQLite database fail immediately with `database is locked` 500 errors, visible any time the user scrolls through a book while a summarization job is running. The minor three: noisy 404s in the browser console from a preflight request the frontend always makes, a summarizer that holds one long transaction across 17+ LLM calls (making the concurrency bug more likely), and broken image URLs served as HTML by the SPA fallback instead of returning 404s.

### Who & Why Now

A personal user running `bookcompanion serve` after installing from PyPI. The concurrency bug was invisible until now because the prior test environments used short-lived jobs and didn't overlap reads with writes. It surfaced immediately during the first real reading + summarizing session on a real book. Fixing this now, while the packaging work is still fresh in memory and the codebase has no external users, avoids each of these becoming a support ticket or a silent "quirk I live with."

## Goals & Non-Goals

### Goals
- **Concurrent reads and writes never fail with `database is locked`** under normal single-user load. Acceptance: an automated test that fires 50 `PUT /api/v1/reading-state` requests during an active `POST /books/{id}/summarize` job produces 0 × 500 responses.
- **Summarization progress is durable** — if the process is killed mid-book, completed section summaries are preserved rather than rolled back. Acceptance: a test that kills the summarize coroutine at section N leaves sections 1..N-1 committed and section N absent.
- **Re-running summarize skips already-summarized sections** — acceptance: a book with sections 1–11 summarized, when re-summarized with the same preset, returns `{completed: <remaining>, skipped: 11}` and makes no LLM calls for the skipped range.
- **The browser console is clean on a fresh library** — no spurious 404s from requests the user cannot influence. Acceptance: opening the app with no books produces zero 4xx or 5xx entries in the browser console.
- **Image requests return a correct status code** — if an image is missing, return 404, not an HTML document with a 200 status. Acceptance: `curl -sI /books/nonexistent.jpg` returns 404.

### Non-Goals
- NOT supporting multi-user concurrent writes because this is a single-user personal tool — a 5-second `busy_timeout` is sufficient, not a full write-queue architecture.
- NOT switching away from SQLite because WAL + proper timeout covers personal-library scale and keeps the zero-dependency promise.
- NOT rewriting the summarizer's orchestration model (map-reduce, cumulative context, eval retry) because the transaction-scope fix is orthogonal to those decisions.
- NOT adding a global error reporter or telemetry because this is pre-release personal-tool scope.
- NOT introducing a migration because none of these changes alter the schema.

## Solution Direction

Four discrete fixes, ordered by severity:

1. **SQLite busy-timeout pragma.** Add `PRAGMA busy_timeout=5000` (5 seconds) to the existing connect-event listener in `backend/app/db/session.py`, alongside the current WAL and foreign-keys pragmas. With busy_timeout set, concurrent writers wait-and-retry up to 5 seconds instead of failing instantly with `SQLITE_BUSY`. This is the single change that turns the 500s into a slight delay (or no delay at all in practice — summarizer write bursts are short).

2. **Commit per section in the summarizer.** Change `SummarizerService.summarize_book()` to `await self.db.commit()` after each successfully summarized section (and after each failed section's eval-trace write) instead of once at the end. Reduces the held-lock window from ~17 minutes to ~100 ms per section. Also makes partial progress durable across crashes. Principled fix for the contention — busy_timeout masks it, this removes it.

3. **Collapse `/active` preset endpoint into the list endpoint.** Today the frontend makes two calls: `GET /api/v1/reading-presets` (list) and `GET /api/v1/reading-presets/active` (which 404s when nothing's set). Replace with a single `GET /api/v1/reading-presets` response that carries both the full list AND which one is the default (e.g., a top-level `default_id` field or an `is_default` flag per item). Remove the `/active` endpoint. One round-trip, no special-case 404, no frontend suppression logic.

4. **Don't serve HTML under image URLs.** Two parts:
   - Fix whichever frontend view is requesting `/books/images/{filename}` (legacy path) and point it at the current `/books/{book_id}/sections/images/{filename}` shape, OR add a backend route that redirects legacy paths.
   - Tighten the SPA fallback in `CachingStaticFiles` to return real 404s for requests whose path looks like a binary asset (`.jpg`, `.png`, `.webp`, `.svg`, etc.) so missing images fail loudly instead of silently returning `index.html`.

## User Journeys

### Primary Journey — read while summarizing

1. User uploads a book → clicks **Summarize**.
2. Backend starts generating summaries section-by-section (each ~60 s).
3. User opens the book in the reader panel and scrolls through sections. The UI fires `PUT /api/v1/reading-state` on each section change.
4. **Today:** every PUT during an active write transaction returns 500. Continue-reading position silently stops advancing; user sees no error but loses their place if they close the tab.
5. **After fix:** every PUT either commits immediately (summarizer is between sections) or waits <5 s for the summarizer's current section write to finish, then commits. User experience: indistinguishable from normal.

### Primary Journey — crash recovery

1. User starts summarization on a 20-section book.
2. At section 12, the laptop lid closes or the process is killed.
3. **Today:** the entire transaction rolls back. On restart, sections 1–11 are unsummarized. The user re-runs summarization from scratch (~$cost × 20 LLM calls re-done).
4. **After fix:** sections 1–11 are persisted. On restart, summarization resumes from section 12.

### Primary Journey — re-running summarize after a partial run

1. User summarized the book earlier; sections 1–11 have default summaries, sections 12–20 do not (crashed or was aborted).
2. User clicks **Summarize** again with the same preset.
3. **After fix:** backend detects sections that already have a summary for the selected preset and **skips** them. Job result reports `completed: 9, skipped: 11`. LLM cost and wall-clock time are proportional to remaining work, not total work.
4. If the user wants to overwrite existing summaries (e.g., prompt changed), a separate "Re-summarize all" action or `--force` flag is the path — out of scope for this iteration.

### Progressive UI during summarization

- With per-section commits (D2), the book detail view can — with no additional server work — reflect completed sections as they land, rather than waiting for the whole book to finish.
- **In scope here:** the backend behavior change is sufficient; any polling the UI already does will now see partial progress.
- **Out of scope here:** pushing SSE events per section (noted as Open Question 2 since it falls out for free if we want it).

### Error / Edge Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| Two concurrent writes exceed 5 s busy-timeout | Pathological load (should not happen single-user) | Return 503 with a clear "server is busy" message, not a SQLAlchemy traceback. Log the occurrence for later diagnosis. |
| Summarizer fails mid-section | LLM call exception after partial DB writes | The failed section's partial state is rolled back; earlier sections remain committed. Job result reports `failed: 1` with the section title. |
| Frontend requests a legitimately missing image | e.g., ebook referenced a cover that wasn't extracted | Server returns `404 Not Found` with `Content-Type: application/json` or no body; the `<img>` shows broken-image icon. **Not** a 200 with `index.html` body. |
| User has no active reading preset yet | First session, nothing ever selected | `GET /api/v1/reading-presets/active` → `200 { "active": null }`. UI shows default reading mode without a console error. |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | `busy_timeout=5000 ms` | (a) 1 s (too tight — LLM writes can span multiple seconds), (b) 5 s (chosen), (c) 30 s (user-visible hang if something's really wrong) | 5 s is longer than any reasonable single write, short enough that if it does trip, something is genuinely stuck and failing loudly is better than hanging the UI. |
| D2 | Commit per section, not per book | (a) One commit at end (current; holds lock forever), (b) Commit per section (chosen), (c) Autocommit mode (loses transactional safety within a section's multi-table writes) | (b) balances durability (progress preserved on crash) with atomicity (each section's summary + embedding + eval trace land together). |
| D3 | Remove `/reading-presets/active`; list endpoint carries default flag | (a) Return 200+null from `/active`, (b) Suppress frontend request, (c) Collapse both endpoints into one list response with default marker (chosen) | One source of truth, one network round-trip, no special-case status codes. The "active preset" isn't a separate resource — it's metadata on the collection. Collapsing removes a class of bugs rather than patching a symptom. |
| D4 | SPA fallback excludes asset-like paths | (a) Blanket fallback to index.html (current; hides bugs), (b) Exclude known asset extensions (chosen), (c) Only fall back for paths without a `.` | (b) keeps the SPA-deeplink behavior working (e.g., `/library/some-id`) while making missing images, PDFs, and other binaries fail visibly. Extension-based is a simple, well-understood heuristic. Excluded set: `.jpg .jpeg .png .gif .webp .svg .ico .pdf .mp4 .woff .woff2`. |
| D5 | Image URL consistency via frontend fix, not backend redirect | (a) Add backend redirect for legacy path (debt forever), (b) Fix the frontend request (chosen), (c) Both | One correct path is better than two routes pointing at the same data. Backend redirect would be a permanent workaround. |
| D6 | Group all four fixes into one requirements doc | (a) Four separate docs, (b) Group (chosen), (c) Fix only the critical one | They share a context ("post-install polish after the first real user session"), are individually small, and pipeline overhead (spec → plan → execute × 4) would outweigh the work. |

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1 | (a) D3 contradicted OQ#1 (chose "200 + null" but also left the option open). (b) User pointed out the cleaner pattern is to collapse `/active` into the list endpoint rather than patch its status code. (c) No acceptance criteria for "zero 500s" goal. (d) Missing journey for re-running summarize after partial completion. (e) D4's excluded extension set wasn't enumerated. (f) Didn't address UI behavior change when commits are per-section. | (a,b) Rewrote item 3 and D3 to remove `/active` endpoint entirely; list endpoint carries `default_id` or equivalent. (c) Added measurable acceptance criterion to each goal. (d) Added "Re-running summarize" and "Progressive UI" journeys. (e) Enumerated extensions in D4. (f) Added progressive-UI note; SSE events still tracked as an open question. |

## Open Questions

| # | Question | Owner | Needed By |
|---|---|---|---|
| 1 | Should the per-section commit also fire an SSE event so the UI can progressively render completed summaries while the book is still processing? Falls out for free but adds a small API surface. | Maneesh | Before spec |
| 2 | For item 4, which frontend view emits the legacy `/books/images/X.jpg` URL? A quick grep during spec will pin this down — not a blocker for requirements. | Maneesh | During spec |

---

*Next step: `/spec` to turn this into a technical specification.*
