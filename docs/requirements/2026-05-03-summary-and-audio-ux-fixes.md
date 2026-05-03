---
date: 2026-05-03
status: Draft
tier: 2 — Enhancement
related:
  - docs/plans/2026-05-02-audiobook-mode-plan.md
  - docs/requirements/2026-05-02-audiobook-mode-requirements.md
---

# Summary & Audio UX Fixes — Requirements

## Problem

After shipping audiobook-mode (v1.6), three UX gaps surfaced on the book detail surface (`/books/{id}`) and the section detail surface (`/books/{id}/sections/{sectionId}`). Each gap silently degrades the perceived reliability of features that already work on the backend:

1. **No feedback when a book summary is queued.** On the Summary tab, clicking **Generate book summary** fires the POST and the backend creates the job, but the UI stays on the empty state. The user has no way to know work started without checking the server logs.
2. **Audio tab buttons are visually inconsistent.** The Audio tab's **Generate audio** button uses raw Tailwind utility classes (e.g. `bg-indigo-600`) instead of the app-wide `btn-primary` / `btn-secondary` semantic classes used everywhere else (Summary tab, modals, reader). It looks and behaves like a stranger inside the same shell.
3. **Browser-speech playback is not exposed in the UI.** The audiobook-mode plan shipped a `TtsPlayButton` component that wraps Web Speech for instant, no-pre-generation playback, but it is only referenced from its own test file. From the user's perspective, the only way to listen to a summary is to first run the (slow, ffmpeg-and-Kokoro-gated) audio generation pipeline — defeating the "click and listen" promise of the Web Speech engine.

### Who & Why Now

A single user (the product owner) on the local dev install. Audiobook-mode just shipped, so users are exploring the new audio surface for the first time and immediately hitting these rough edges. Each one undermines confidence in the new feature.

## Goals & Non-Goals

### Goals

- **G1.** After clicking **Generate book summary**, the Summary tab shows live progress (sections completed of total, ideally with a percentage) within ~1 second, driven by the same SSE stream the backend already emits.
- **G2.** Every button on the Audio tab uses the same semantic `btn-primary` / `btn-secondary` classes used by Summary tab, modals, and reader controls — visual parity across surfaces.
- **G3.** From any summary view (book summary, section summary) and from the section content view, the user can press a single play button and hear the content read aloud via the browser's Web Speech engine — no pre-generation step, no ffmpeg, no Kokoro install required.

### Non-Goals

- **NOT** redesigning the Summary tab layout — only adding the missing progress affordance. *Reason:* scope creep; the existing layout is fine.
- **NOT** rebuilding the design-token / theming system to inherit reader-preset typography on the Audio tab. *Reason:* the user clarified "inherit reader preset" actually means "use the same button classes as the rest of the app" — typography inheritance is out of scope.
- **NOT** changing how Kokoro audio generation works on the Audio tab. *Reason:* generation pipeline is correct; only the trigger button styling is wrong.
- **NOT** adding sentence-level highlight or playbar UI to the new TTS entry points. *Reason:* highlight + Playbar already exist for the reader; this fix only wires the existing `TtsPlayButton` into more locations. Whether the global Playbar should appear is a follow-up.
- **NOT** persisting Web Speech playback position. *Reason:* Web Speech is the "ephemeral, instant" engine by design; persistence is for Kokoro audio.
- **NOT** extending the `bookcompanion listen` CLI command to speak summaries. *Reason:* this fix targets web-surface UX gaps the user hit during exploration; CLI parity is a separate scope and the existing CLI already covers Kokoro pre-generation needs.

## Solution Direction

Three small, independent fixes inside existing components — no new services, no new backend routes.

```
1. Summary tab progress
   BookSummaryTab.vue
     ├─ on POST 201/202 → flip local state to 'inProgress' immediately
     └─ render existing SSE stream (section_completed events) as
        "X of Y sections (NN%)" + cancel button

2. Audio tab button parity
   AudioTab.vue, GenerateAudioModal.vue, AudioFileRow.vue, etc.
     └─ replace bg-indigo-600 / hover:bg-indigo-500 / px-3 py-1.5
        with btn-primary / btn-secondary

3. Web Speech entry points
   SectionSummaryPane / SectionContentPane / BookSummaryTab
     └─ mount existing TtsPlayButton with appropriate text source
        (summary_md or content_md, sanitized via existing
         markdown_to_speech pipeline)
```

## User Journeys

### J1 — Generate book summary with feedback (fixes #1)

1. User opens `/books/1?tab=summary` for a book where every section is summarized but no book summary exists.
2. Empty-state shows "N of N sections summarized." + **Generate book summary** button.
3. User clicks the button.
4. Within ~1 second, the empty state is replaced with: "Generating book summary… 0 of N sections" + progress bar + **Cancel** button.
5. As backend SSE events fire (`section_completed`, etc.), the counter and bar update in real time.
6. On `book_summary_completed`, the view swaps to the populated summary.
7. On error, view swaps to the existing failed state with a Retry button.

### J2 — Click the Audio tab and recognize buttons (fixes #2)

1. User opens `/books/1?tab=audio` on a book with no audio.
2. Sees **Generate audio** button styled identically to **Generate book summary** on the Summary tab — same height, padding, color, hover, focus ring.
3. User clicks it; the modal opens with primary/secondary action buttons that also match the rest of the app's modals.

### J3 — Listen to a section summary instantly (fixes #3)

1. User opens `/books/1/sections/6?tab=summary`.
2. Above (or beside) the rendered summary markdown, a **▶ Listen** button is visible.
3. User clicks it. Browser Web Speech begins reading the summary aloud immediately, no network wait. The button visibly switches to a ⏸ Pause affordance and an engine label (e.g. "Browser speech") becomes visible so the user can see what's playing.
4. A second click pauses (button returns to ▶); a third resumes; navigating away stops playback.
5. If the browser has no Web Speech support, the button is hidden (or disabled with a tooltip — design decision deferred to spec).

### J4 — Listen to a book summary instantly

1. Same as J3, but on `/books/1?tab=summary` once a book summary exists.
2. **▶ Listen** appears beside the existing **Read Section Summaries** / **Regenerate** actions.

### J5 — Listen to section content instantly

1. User opens `/books/1/sections/6?tab=content` (the raw chapter text).
2. **▶ Listen** appears in the same position as on the summary tab.
3. Behavior identical to J3.

### J6 — Re-attach to an in-flight book-summary job

1. User clicks **Generate book summary**, then navigates away (or hard-reloads the page) before it completes.
2. User returns to `/books/1?tab=summary`.
3. On mount, the Summary tab detects the active book-summary job for this book and immediately renders the progress view (counter + bar + Cancel) with whatever state the SSE stream is at.
4. No re-click of Generate is needed — the user picks up exactly where they left off.

### Error / Edge Cases

- Web Speech unavailable in browser → entry point hidden (no broken button).
- User clicks **Generate book summary** twice rapidly → second click is a no-op (already in inProgress state) OR backend returns 409 with `active_job_id` and the UI attaches to that existing job.
- Job fails mid-stream → progress view swaps to the existing failed state.
- User navigates away during Web Speech playback → playback stops (no orphaned background speech).
- User toggles Kokoro audio playback (Playbar) and Web Speech ▶ Listen at the same time → only one engine plays at a time; starting one stops the other.

## Design Decisions

| #  | Decision                                                                 | Options Considered                                                                                                                                                                       | Rationale                                                                                                                                                                                                                  |
|----|--------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D1 | Show inline progress bar with `X of Y (NN%)` after Generate-summary click | (a) Toast only; (b) Flip to existing inProgress text-only state; (c) Inline progress bar with %                                                                                          | User chose (c). Reuses existing SSE events; gives the strongest "yes, work is happening" signal; matches the section-level `SummarizationProgress` pattern already in the codebase.                                        |
| D2 | "Inherit reader preset" = use `btn-primary` / `btn-secondary` classes     | (a) Match reader font/theme tokens; (b) Use semantic btn classes; (c) Both                                                                                                               | User clarified intent: visual parity with the rest of the app, not typography inheritance. (b) is the smallest blast-radius fix and produces the consistency the user wanted.                                              |
| D3 | Web Speech ▶ Listen on section summary, book summary, AND section content | (a) Section summary only; (b) Section + book summary; (c) Section summary + book summary + section content                                                                               | User chose (c). The Web Speech engine is already implemented; gating it behind pre-generation everywhere defeats its purpose. Section content unlocks "audiobook mode without setup" for users who skip Kokoro.            |
| D4 | Single bundled requirements doc                                          | (a) One bundle; (b) Three independent docs                                                                                                                                                | User chose (a). All three are small, share the same surface (book detail), and benefit from one spec/plan/verify cycle.                                                                                                    |
| D5 | Reuse existing `TtsPlayButton` rather than create new components          | (a) Reuse `TtsPlayButton`; (b) Build a new compact variant per surface                                                                                                                   | The component exists, has tests, and is engine-aware. Reuse wins on consistency and speed.                                                                                                                                 |
| D6 | Single-active-engine: starting Web Speech stops Kokoro and vice-versa     | (a) Allow concurrent playback; (b) Only one engine at a time                                                                                                                              | Two voices reading the same chapter at once is never desired. **Conditional on Q6:** if `ttsPlayer` already enforces this, no work needed; if not, add it as part of this fix.                                              |

## Open Questions

| #  | Question                                                                                                                                                  | Owner   | Needed By  |
|----|-----------------------------------------------------------------------------------------------------------------------------------------------------------|---------|------------|
| Q1 | Exact placement of ▶ Listen on each surface — header action row vs. floating-above-content vs. below-title? Should it sit beside Regenerate / Read buttons? | Maneesh | Before /spec |
| Q2 | When Web Speech is unsupported, should the button be hidden, or shown disabled with a "Browser doesn't support speech" tooltip?                            | Maneesh | Before /spec |
| Q3 | Should the inline progress bar (D1) match the existing `coverage-bar` styling on the Audio tab, or the `SummarizationProgress` styling already used for section batches? | Maneesh | Before /spec |
| Q4 | Are there other places in the app still using raw Tailwind button utilities that should be normalized in the same pass (consistency sweep)?                | Maneesh | Before /spec |
| Q5 | **Backend research task:** does the current book-summary job emit per-section SSE events (e.g. `section_completed`) usable to drive an X-of-Y progress bar, or only start/finish events? If the latter, scope expands to backend OR the bar degrades to indeterminate. Must be answered in /spec Phase 1. | Agent (in /spec) | Before /spec finalizes |
| Q6 | **Engine-exclusivity research:** does the existing `ttsPlayer` store already enforce single-active-engine (Web Speech vs. Kokoro Playbar)? If not, this becomes a real Design Decision and additional behavior in /spec.                                                            | Agent (in /spec) | Before /spec finalizes |

## Acceptance Criteria

- [ ] Clicking **Generate book summary** swaps the Summary tab to a progress view within 1 second; the view shows section X of Y completed and a percentage; the bar updates as SSE events arrive.
- [ ] On job completion, the Summary tab shows the populated summary without a manual refresh.
- [ ] On job failure, the Summary tab shows the existing failed state with Retry.
- [ ] Every button on the Audio tab and inside the Generate Audio modal uses `btn-primary` or `btn-secondary` (no raw `bg-indigo-*` / `bg-slate-*` button utilities remain).
- [ ] A ▶ Listen button is visible and functional on: section-summary view, book-summary view (when populated), and section-content view.
- [ ] Pressing ▶ Listen starts Web Speech playback with no network round-trip; perceived as instant.
- [ ] During Web Speech playback, the entry point visibly toggles to a pause affordance (▶ → ⏸) and the engine label/chip is visible so the user knows audio is active.
- [ ] Starting Web Speech while Kokoro Playbar is active stops the Kokoro track first (and vice-versa).
- [ ] Navigating away from a view with active Web Speech playback stops playback.
- [ ] In a browser without Web Speech support, the entry point gracefully hides or disables (per Q2 resolution).
- [ ] Reloading the Summary tab while a book-summary job is in flight re-attaches the progress view automatically, with no user action required.

## Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | F1 missing reattach journey; F2 unverified SSE granularity for book-summary jobs; F3 unverified single-engine enforcement; F4 CLI scope unstated. | Added J6 (reattach) + AC; added non-goal for CLI; added Q5 (SSE research) and Q6 (engine-exclusivity research) as research tasks for /spec Phase 1. |
| 2 | F5 arbitrary 200 ms latency AC; F6 button-state-during-playback contract missing; F7 a11y; F8 cosmetic icon. | F5: rephrased AC to "no network round-trip; perceived as instant." F6: added playback-state language to J3 + AC. F7: skipped (personal tool). F8: cosmetic, no change. |
