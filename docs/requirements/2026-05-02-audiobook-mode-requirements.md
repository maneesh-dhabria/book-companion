# Audiobook Mode — Requirements

**Date:** 2026-05-02
**Status:** Draft
**Tier:** 3 — Feature

## Problem

Reading a non-fiction book — or even its AI summaries — requires sitting and looking at a screen. The owner of a Book Companion library has dozens of summarized books they'd like to **revisit while doing something else**: dishes, walking, commuting, cooking. Today there is no path: every word in the system is text-only, and copy-pasting summaries into a third-party TTS app loses structure, position, and integration with the rest of the library.

### Who experiences this?

The single user of a self-hosted Book Companion instance — a power reader who has already invested in summarizing 20–100 non-fiction books and wants those summaries (and their own highlights) accessible in **listening contexts** where reading is impossible. Primary device contexts: a desktop or laptop running a browser tab while doing chores; secondarily, a phone where the user has played a generated MP3 in a podcast app.

### Why now?

The library has reached the point where summary content is the most valuable artifact in the system, and the bottleneck has shifted from *generating* summaries to *re-encountering* them. Audio is the single largest unaddressed re-encounter channel. TTS quality in 2026 (Kokoro-82M, Apple system voices) is finally close enough to commercial narration that listening to a summary feels useful, not painful — a gate that didn't exist two years ago.

## Goals & Non-Goals

### Goals

- A user can **press play on any section summary, the book-level summary, or the per-book annotations playlist** in the web reader and hear it spoken in a usable voice, with controls for speed, pause/resume, and skip-by-sentence.
- Generated audio for any book can be **downloaded as MP3 files** for use in any podcast app, music player, or file system.
- The user can **pre-generate audio for an entire book** in one explicit action, and watch progress in the existing job/SSE UI.
- Audio playback **resumes from the last position** when the user returns to a section, even after a tab close or browser restart.
- The **CLI exposes the same generation capability** so audio can be queued without opening the UI.
- Engine choice is **pluggable**: the system supports both browser-native (Web Speech API, zero install) and a local engine (Kokoro-82M, ~100MB model, full file-output capability), and the user picks per-action which to use.
- The user can **delete generated audio for any book at any time** to free disk space, without affecting summaries, annotations, or the book's data integrity.
- **Adding a third TTS engine in the future is a small, isolated change** — the `TTSProvider` abstraction stays minimal and engine-agnostic so a new engine (cloud, alternative local, OS-specific) is a factory-line addition, not a redesign.
- The user finishes a v1 spike able to answer with confidence: *"Is browser-native voice quality good enough that I'd ever pick it over the local engine?"*

### Non-Goals (explicit scope cuts)

- **Cloud TTS APIs (OpenAI, ElevenLabs, Google) are NOT supported.** The user does not want a recurring spend, and Book Companion's identity is local-first.
- **TTS of the full original section content (`content_md`) is NOT in v1** because Book Companion's value proposition is *summaries*, not narration of the original. A user wanting a full audiobook of a public-domain book has better options (Librivox, commercial audiobooks).
- **A public-internet RSS podcast feed is NOT in v1.** Pocket Casts / Overcast require server-side fetch from a publicly-reachable URL, which means Tailscale Funnel or a tunnel — a meaningful operational layer. Defer until we know audio listening is sticky enough to justify the deployment work. v1 ships MP3 download only.
- **Word-level karaoke highlighting is NOT in v1.** Web Speech `boundary` events are unreliable cross-browser; local engines don't emit word timings without a separate alignment step. v1 ships **sentence-level** highlight-as-it-plays only.
- **Voice cloning, multi-speaker, or character-voice features are NOT in scope** because they do not serve the summary-listening job.
- **Background music / soundscape / ambient layering is NOT in scope** because it adds UX complexity for a feature that's already a focused consumption mode.
- **Multi-user audio personalization is NOT in scope** because Book Companion is single-user by design.
- **Engine plugin discovery / hot-swap UI is NOT in v1** because it solves a problem the user doesn't have (the user installs Book Companion themselves; adding a new engine is a code change, not a UI flow).

## User Experience Analysis

### Motivation

- **Job to be done:** *"Re-encounter what I learned from the books I've already summarized, in moments where I can't look at a screen."* Closely related: *"Decide whether a book I summarized weeks ago is still relevant to a problem I'm thinking about today, without having to sit down and read."*
- **Importance/Urgency:** Medium. The user has the summaries already; the audio path is additive, not blocking. However, the marginal value of each new summarization drops if the user can't easily re-encounter past summaries — the audiobook feature unlocks compounding value from existing library investment.
- **Alternatives:** (a) copy/paste into Speechify (loses position, not integrated with library, recurring subscription); (b) use Edge "Read Aloud" on the web UI (no resume position, no MP3 export, no annotations integration); (c) skip listening entirely and accept that summaries are read-only artifacts. The current alternatives are all friction-laden enough that the user doesn't actually use them — meaning the current effective listen rate of the library is **zero**.

### Friction Points

| Friction Point | Cause | Mitigation |
|---|---|---|
| "I'll wait until I'm doing dishes" → never opens the page | Listening requires opening a browser tab and finding the book first | Lock-screen / Media Session controls so phone playback works without tab focus; "play next section" auto-advance |
| "It pronounces footnote markers as numbers / reads code blocks literally" | Markdown structural noise (links, image refs, code fences, footnote markers, math) is not text-to-speech-safe | Mandatory markdown-to-speech sanitizer pass before audio generation; characterized as a hard requirement, not nice-to-have (see Anti-Patterns table below) |
| "First time I clicked play I waited 30 seconds for nothing" | Local engine cold-start (model load) is multiple seconds | Show explicit "Loading voice…" state on first invocation; warm the engine on `bookcompanion serve` startup if local engine selected; for in-browser Web Speech, instant |
| "I don't know which voice/engine to pick" | Two engines with different quality vs install tradeoffs is a real choice | Spike phase before commitment; ship sensible default; document the tradeoff in settings UI |
| "I lost my place when I closed the tab" | TTS state is non-persistent in browser | Persist `{book_id, content_type, content_id, sentence_index, device_id}` server-side at every sentence boundary; restore on resume per D9 |
| "It started reading another book in another tab without warning" | Audio playback ignores router transitions / multi-tab | Single playing source per book; navigating away pauses (configurable); only one audio source active per browser at a time |
| "I generated audio for the whole book and have no idea what's in those MP3s" | Bare filenames lose context | MP3 files include ID3 tags (book title, section title, track number, cover image from book metadata) so they're playable in any music app |
| "Why does this section sound different from the last one?" | Per D14, sections with pre-generated MP3s use the local engine; sections without use Web Speech as instant fallback — same book can mix engines | Player header always shows the **active engine + voice name**; section list shows a small icon next to sections with pre-generated audio; book detail shows audio-coverage state at a glance ("Audio: 12 of 47 sections pre-generated") |

### Satisfaction Signals

- The user opens a book they summarized two months ago, taps play, walks away from the screen, and finds the summary genuinely informative spoken aloud — voice quality doesn't break the experience.
- Pre-generating a whole book's audio is a single click and completes in the background while the user does other work, with the same SSE progress UI they already know from summarization.
- The user can hand a generated MP3 to a friend (via AirDrop / iMessage) without having to explain how to use Book Companion.
- The user can listen to the "annotations playlist" of a recently re-read book and feel like they're getting a personalized condensed review, not a generic dump.

## Solution Direction

Two-engine pluggable TTS, mirroring the existing Claude/Codex CLI provider auto-detection pattern. v1 ships:

1. **Web Speech API engine** (browser-native, zero install) — for instant browser-tab listening. No file output. No phone podcast-app path.
2. **Kokoro-82M local engine** (~100MB ONNX model downloaded on first use, like fastembed) — for file output (MP3), pre-generation, downloads, and future RSS. Higher quality, ~3–11x realtime on M-series CPU.

A short **spike phase** (≤2 days, before /spec) compares the two on the user's actual content with the user's actual ears. The spike outputs a short writeup ("Web Speech sounds like ___, Kokoro sounds like ___; here's a 30-second clip of each on the same passage") that informs the default-engine setting in v1. **Both engines ship regardless of spike outcome** — the spike only sets the default and informs documentation copy.

```
                           ┌─────────────────────────┐
   Reader page ────play──▶│  TTSPlayer (Vue)        │──Web Speech──▶ system audio
                           │  - speed / pause / skip │
   Book detail ─generate──▶│  - sentence highlight   │──MP3 stream──▶ HTML5 <audio>
                           │  - resume position      │
   CLI: bookcompanion      │  - Media Session API    │
        listen ──────────▶ │  - sleep timer          │
                           └─────────┬───────────────┘
                                     │
                                     ▼
                       ┌─────────────────────────┐       ┌──────────────┐
                       │  TTSProvider ABC        │──────▶│ Kokoro local │── MP3 files
                       │  (subprocess pattern)   │       │ (subprocess) │   on disk
                       └─────────┬───────────────┘       └──────────────┘
                                 │
                                 ▼
                       ┌─────────────────────────┐
                       │ Markdown→Speech         │  strips: code blocks, image refs,
                       │ sanitizer (shared)      │           footnote markers, URLs,
                       └─────────────────────────┘           math, abbreviation expansion
```

Generated MP3s are stored in the existing data directory (alongside `library.db`), exposed via authenticated routes (`GET /api/v1/books/{id}/audio/{kind}/{ref}.mp3`), tagged with ID3 metadata, and listable as a flat per-book index page. RSS feed generation is deliberately deferred to v1.1 once we know listening is sticky.

## User Journeys

### Primary Journey 1 — Listen to a section summary right now

1. User opens a book in the reader, lands on the Summary tab of a section.
2. A **play button** appears in the section header next to the existing content toggle. User clicks it.
3. If browser-native engine selected (default for instant playback): audio starts within 200ms. A **playback bar** appears at the bottom of the reader (sticky, non-modal) with: pause, sentence-back, sentence-forward, speed (0.75x / 1x / 1.25x / 1.5x / 2x), close.
4. The current sentence is **highlighted** in the rendered summary as it plays. The reader auto-scrolls to keep the current sentence centered.
5. User walks away from the screen. Audio continues. Lock-screen / Media Session shows book title + section title + cover.
6. When the section ends, audio **auto-advances** to the next section's summary (if a setting allows; default on). Highlight moves with it.
7. User returns later, navigates to the same section. The play button shows a **"Resume from sentence 12 of 47 (last listened on this device 2 hours ago)"** affordance instead of restarting. Position is persisted server-side, so resuming on a different device is *best-effort* (the position exists, but the device-context line makes clear it may not match where this user actually stopped on this device).

### Primary Journey 2 — Pre-generate audio for a whole book

1. On the book detail page, a **"Generate audio"** button sits alongside the existing "Generate summaries" button, in the same area.
2. User clicks. A modal asks: *Which content?* (default summary per section ☑, book summary ☑, annotations playlist ☐) and *Which voice?* (defaults to user's saved preference, with a sample-play button for each option).
3. User confirms. A processing job is queued in the existing job system. SSE updates stream into the same UI used for summarization (`section_audio_started`, `section_audio_completed`, `book_audio_completed` events).
4. Job completes. The book detail page now shows: a **"Listen"** button (opens the player on the book summary), an **"Audio files"** link (opens a flat list page with download links + sizes), and a **"Regenerate audio"** option (with engine/voice picker).
5. User downloads the MP3s and transfers them to their phone (AirDrop, USB, cloud sync, Tailscale, etc.), where any podcast app or media player that accepts local MP3 files can play them. The ID3 tags ensure they appear with proper book/section titles and cover art.

### Primary Journey 3 — Listen to annotations from a book

1. On the book detail page, "Annotations" tab (existing) gains a **"Play as audio"** button if any highlights or notes exist on this book.
2. User clicks. The TTSPlayer opens in **Annotations playlist mode**: it walks each highlight in section reading-order, reading the highlighted passage, then any attached note (preceded by an audible cue: a half-second pause + a slightly different voice tone via SSML or speed shift).
3. Standard player controls work: pause, skip-to-next-annotation, speed.
4. The visual area shows the current annotation's source section + highlight context (existing annotation card UI), advancing with playback.
5. User can tap any annotation card to jump playback to it.

### Alternate Journey — CLI generation

1. User runs `bookcompanion listen --generate <book_id>` on a remote terminal.
2. Same job is queued as the UI button. CLI streams the same SSE events as Rich-rendered progress bars.
3. On completion, CLI prints the per-section MP3 file paths and the total disk usage.
4. User can also run `bookcompanion listen <book_id>` (no `--generate`) to play the book summary out the local audio device using the local engine, with keybindings for pause/skip — useful for headless playback on a media server.

### Error Journeys

| Scenario | What user sees | Recovery |
|---|---|---|
| Local engine model not yet downloaded | First click on play: modal "Download voice model? (~100MB, one-time)" with confirm/cancel | On confirm, downloads with progress bar (reuses fastembed model-download UX); on cancel, falls back to Web Speech if available, otherwise disables play with explanatory tooltip |
| Web Speech voice not available in this browser | Inline warning in player: "Browser TTS unavailable. Use local engine?" with one-click switch | One-click switch to local engine; remembers preference |
| Audio generation job fails mid-book | Job marked FAILED with per-section breakdown (X of Y sections completed); partial MP3s remain usable | "Retry failed sections" button; user can play the completed sections in the meantime |
| User triggers playback while another section is already playing in the same browser | Smooth handoff: previous source pauses, new source starts; no double-audio | (no recovery needed — designed behavior) |
| Markdown sanitizer fails on a malformed section | The audio for that section is generated from the un-sanitized text with a warning logged; an inline "Audio quality may be poor for this section" banner shows in the player | User can regenerate per-section after editing the section |
| Disk fills up during pre-generation | Job fails with "Disk full" error; partial MP3s preserved | User clears space or deletes audio for other books; "Delete audio" button on each book detail page |

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| Book has no summaries yet | User clicks "Generate audio" | Modal explains "Generate summaries first." Disabled with link to summary generation. |
| Section has no summary, only original content | User opens the section's reader | Play button is **disabled** with tooltip: "Audio is only generated for summaries in v1. Generate this section's summary first." |
| Annotations playlist requested but book has zero highlights | User clicks "Play as audio" on Annotations tab | Button is hidden; if force-clicked via deep link, shows "No highlights yet — add some by selecting text in the reader." |
| Audio file exists but markdown source has changed since generation | User opens player after editing a section | Banner: "Source has been edited since audio was generated. Regenerate?" with one-click action. Stale audio still playable. |
| User on a browser where neither Web Speech voices NOR local engine model are available | (Linux Firefox with no system voices, no Kokoro download) | Player shows "No voice available" with link to settings page where local engine can be downloaded |
| Large book with 80+ sections being pre-generated | Generation will take 20+ minutes | Job UI shows estimated time remaining; user can close tab — job continues in background; SSE reconnects on return |
| Summary regenerates while audio is playing on the previous version | User is listening; in another tab they trigger summary regeneration; v2 is now the default summary, v1 audio is now stale | Player **finishes the current section on v1 audio without interruption** (no jarring stop). On section completion (or on user pressing pause), a banner appears: *"Summary updated since this audio was generated. Regenerate audio for the new summary?"* with one-click action. v1 audio remains playable until explicitly replaced. |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | **Pluggable two-engine architecture (Web Speech + Kokoro local)** is v1 default. | (a) Web Speech only; (b) Kokoro only; (c) Both pluggable; (d) Cloud TTS | (c) chosen. Web Speech and local engines serve different journeys (instant browser stream vs file output) — neither alone covers both. Cloud is cost-bound off the table. |
| D2 | **Spike phase before /spec** compares Web Speech and Kokoro voice quality on the user's actual content. | (a) Spike before commit; (b) Skip spike, ship both; (c) Skip spike, ship one | (a) chosen. The user explicitly asked for a POC. Spike output sets the default-engine setting and the engine-picker copy in settings UI; both engines ship regardless. |
| D3 | **Sentence-level highlighting only in v1**, not word-level. | (a) Word-level via Web Speech `boundary` events; (b) Word-level via local-engine + WhisperX alignment; (c) Sentence-level only; (d) No highlighting | (c) chosen. Word-level via boundary events is unreliable cross-browser; via alignment adds a heavy dependency. Sentence-level is dramatically simpler (split on sentence boundaries, advance on `<audio>` `ended` event for local engine, on `boundary type='sentence'` for Web Speech) and serves the "where am I in the text" job adequately. |
| D4 | **MP3 files only in v1**, not RSS podcast feed. | (a) MP3 download only; (b) RSS feed via Tailscale Funnel; (c) RSS feed via LAN-only (broken with Pocket Casts) | (a) chosen. Validates listening behavior before paying the operational cost of RSS+tunnel. Path stays open in v1.1. |
| D5 | **Manual generation trigger** per book (button), not automatic post-summarize. | (a) Manual button; (b) Auto-after-summarize; (c) Stream-on-demand only; (d) Hybrid | (a) chosen. User decides which books deserve TTS CPU/disk cost; mirrors how summarization itself is triggered. Stream-on-demand is interesting but blocks the MP3-download surface. |
| D6 | **Annotations as a separate playlist mode**, not inline during section playback. | (a) Inline at highlight position; (b) Separate playlist; (c) Both with toggle; (d) Defer | (b) chosen. Inline interrupts narrative flow of the section summary; separate playlist serves spaced-repetition / review use case more cleanly. Both is over-engineering for v1. |
| D7 | **TTS preferences live in `~/.config/bookcompanion/settings.yaml`** (engine, voice, default speed), not localStorage. | (a) localStorage like reader chrome; (b) settings.yaml like LLM config | (b) chosen. Per the project pattern: localStorage is for transient UI chrome; persisted user choices that the CLI also needs to read live in the YAML. CLI must read voice + engine config to generate matching audio. |
| D8 | **Lock-screen / Media Session API integration in v1**, not deferred. | (a) Defer to v1.1; (b) Ship in v1 | (b) chosen. The "walk away from the screen" job is core to the feature. Media Session API is a 50-line integration with high payoff (lock-screen play/pause/scrub on iOS/macOS/Android). Skipping it would force users to wake the screen for every interaction. |
| D9 | **Audio resume position persisted server-side**, not in localStorage. **Cross-device resume is best-effort in v1** — server stores the position, but UI surfaces last-listened device context (e.g., "last listened on this device 2 hours ago") rather than implying seamless device handoff. | (a) localStorage (per-device); (b) Server-side, single global position; (c) Server-side per-device with explicit context | (c) chosen. Server storage future-proofs phone listening; per-device context avoids the "I was here on my phone, why is laptop now showing that position?" confusion of a single global position. Schema: `audio_position` table with `(content_type, content_id, device_id, sentence_index, updated_at)`. True cross-device handoff (Audible-style) is deferred. |
| D10 | **Markdown-to-speech sanitizer is a shared, mandatory step** for both engines, not engine-specific. | (a) Per-engine sanitization; (b) Shared sanitizer module | (b) chosen. The sanitization needs (strip code blocks, footnote markers, URLs, image refs, expand abbreviations) are 100% identical regardless of engine; the cure for "voice reads literal markdown" is sanitization at the edge, not engine-specific tweaking. New module: `app/services/tts/markdown_to_speech.py`. |
| D11 | **MP3 files include rich ID3 tags** (book title, section title, track number, embedded cover image). | (a) Bare filenames; (b) Rich ID3 tags | (b) chosen. Generated files are first-class artifacts that need to make sense outside Book Companion (in a podcast app, in the Files app, after AirDrop). ID3 is a 5-line addition with `mutagen`. |
| D12 | **Audio files stored on disk, not in SQLite. Lifecycle is replace-on-regenerate, delete-on-book-delete, and explicit-user-delete.** | (a) Disk files referenced by AudioFile rows; (b) BLOB columns in DB | (a) chosen. MP3s are large (~2–5MB per section); BLOB storage bloats the SQLite file and slows backups. Disk path stored in DB. Lifecycle: regenerating audio for a section atomically **replaces** the prior MP3 (no orphan accumulation); deleting a book deletes all its audio; user can explicitly **"Delete audio for this book"** as a one-click action on the book detail page. Mirrors how the existing fastembed model and backup files work — outside `library.db`. |
| D13 | **Mid-listen summary regeneration does not interrupt audio.** Player finishes current section on stale audio; banner offers regeneration on next pause / section boundary. | (a) Stop immediately and modal; (b) Finish current section then offer; (c) Silently switch (impossible — audio is pre-rendered) | (b) chosen. Interrupting an active listening session is the worst UX failure mode for an audiobook player; the user's intent at moment-of-listen is to listen, not to be modal-prompted. The stale-audio window is bounded (one section at most). |
| D14 | **Click-to-play in the reader uses Web Speech instantly if no pre-generated MP3 exists for that section, regardless of the user's default-engine setting.** Local-engine narration of a section requires the user to explicitly Generate Audio for the book first. | (a) Silent Web Speech fallback when no MP3; (b) Stream-on-demand from local engine (5–10s latency); (c) Disable click-to-play unless pre-generated | (a) chosen. Makes the two-engine split feel natural rather than confusing: instant browser playback = Web Speech, persistent file/MP3 = Kokoro. Removes the "why does click-play sound different from the MP3 I downloaded?" confusion by making the engine-per-surface predictable. The player UI labels which engine is active. |

## Success Metrics

| Metric | Baseline | Target | Measurement |
|---|---|---|---|
| Books with audio generated within 30 days of v1 ship | 0 | ≥ 5 | Count of books with at least one `AudioFile` row |
| Listening sessions per week (4 weeks post-ship) | 0 | ≥ 3/week sustained | Server-side log of any audio playback start event |
| Spike outcome documented | (n/a) | Written comparison + chosen default | One file at `docs/spikes/2026-05-XX-tts-engine-spike.md` (new convention; this is the first entry under `docs/spikes/`) before /spec |
| Spike materially shapes v1 | (n/a) | Default-engine setting + Settings UI engine-picker copy + ≥1 paragraph of user-facing engine guidance all derived from the spike's findings | /verify checks that the Settings UI text references the spike, not generic boilerplate |
| Voice-quality acceptability (subjective, user self-report at week 4) | (n/a) | "I'd actually use this" — yes / no | User notes the answer; if no, /verify treats it as a v1 failure regardless of code quality |
| Podcast-app usage (offline phone listening) | 0 | ≥ 1 book actually listened to on phone offline | Self-report; if zero at week 4, deprioritize the RSS roadmap |
| Markdown-sanitizer regression rate | (n/a) | < 1 reported "voice reads garbage" issue per 10 books | Manual / informal — these are obvious enough that the user notices |

## Anti-Patterns to Defend Against

These are spoken-output failure modes that consistently break TTS UX. The spec must address each as a sanitizer requirement.

| Anti-pattern | Cure (in sanitizer) |
|---|---|
| Footnote markers spoken as digits ("…as Smith argued 23 the…") | Strip `[N]` and superscript `^N` patterns before TTS |
| Code blocks read literally | Replace fenced code blocks with `"code block, N lines, skipped."` (or fully omit, configurable) |
| Markdown image refs spoken as URLs | Replace `![alt](url)` with `"figure: " + alt` (or omit if no alt) |
| Raw URLs spoken character-by-character | Skip bare URLs; replace with domain name only or omit |
| Abbreviations mangled ("e.g." as "ee gee") | Expansion table for common abbreviations (e.g., i.e., etc., vs., St.) |
| Math / LaTeX gibberish | Detect `$…$` / `\[…\]` and replace with `"equation, omitted"` |
| Voice changes mid-sentence | Always chunk on sentence boundaries, one utterance per sentence |
| Audio keeps playing after navigating away | Player is single-instance per browser; navigate-away pauses (configurable: pause vs continue) |

## Research Sources

| Source | Type | Key Takeaway |
|---|---|---|
| `frontend/src/views/BookDetailView.vue:1-200`, `ReaderHeader.vue:24-60`, `ReadingArea.vue:30-37` | Existing code | Reader UI structure, where play button and player slot in |
| `backend/app/services/summarizer/llm_provider.py:20-67`, `summarizer/__init__.py:8-27` | Existing code | Pluggable provider ABC + auto-detect pattern — direct template for `TTSProvider` |
| `backend/app/services/job_queue_worker.py:42-108`, `app/api/sse.py:15-55`, `routes/processing.py:33-194` | Existing code | Job queue + SSE pattern — direct template for audio-generation jobs |
| `backend/app/services/settings_service.py:55-106`, `frontend/src/stores/readerSettings.ts:30-70` | Existing code | Two-tier settings split: TTS config goes in `settings.yaml` (read by CLI too), not localStorage |
| `backend/app/services/export_service.py:44-71` | Existing code | `_sanitize_image_urls()` is the closest existing analog to the new markdown-to-speech sanitizer |
| `backend/app/api/routes/images.py:11-27`, `routes/backup.py:51-64` | Existing code | Binary blob serving pattern for MP3 files |
| `backend/app/db/models.py:81-84, 436-466`, `AnnotationRepository:40-60` | Existing code | Polymorphic Annotation model — annotations playlist enumeration is feasible without schema changes |
| Speechify reader — https://speechify.com/text-reader/ | Competitor | Word-sync highlight + 0.5–4.5x speed are table stakes; voice picker hidden in settings |
| Voice Dream Reader — https://www.voicedream.com/reader/reader-feature-list/ | Competitor | Skip-by-sentence/paragraph beats skip-by-15s; rebindable controls |
| Apple Books on Mac — https://support.apple.com/guide/books/listen-to-audiobooks-ibks9a460640/mac | Competitor | Sleep timer is a top-level discoverable control; chapter list is flat |
| MDN Media Session API — https://developer.mozilla.org/en-US/docs/Web/API/Media_Session_API | Reference | Lock-screen / Now Playing integration is ~50 LOC, supports `chapterInfo` |
| MDN speechSynthesis boundary event — https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisUtterance/boundary_event | Reference | Word-level `boundary` events unreliable on Linux/Android — avoid for cross-browser sync |
| Kokoro-82M — https://huggingface.co/hexgrad/Kokoro-82M | TTS engine | Apache 2.0, ~3–11x realtime CPU, ranked #1 TTS Arena. ONNX build available. Recommended local engine. |
| Piper TTS — https://github.com/rhasspy/piper | TTS engine alternative | MIT, ~10–20x realtime, slightly more robotic than Kokoro. Lighter fallback if Kokoro install proves painful. |
| Coqui TTS (idiap fork) — https://github.com/idiap/coqui-ai-TTS | TTS engine alternative | Heavier, voice cloning capable. Out of scope for v1 (overkill for summary narration). |
| Substack private podcast feed — https://support.substack.com/hc/en-us/articles/4519588148244 | RSS pattern | Single-user RSS feed model — direct precedent for v1.1 RSS work |
| Pocket Casts private feeds — https://support.pocketcasts.com/knowledge-base/private-or-members-only-feeds/ | RSS constraint | Server-side fetch — public reachability required, kills LAN-only RSS |
| Tailscale Funnel — https://tailscale.com/blog/self-host-a-local-ai-stack | Deployment pattern | Cleanest path to expose a localhost service publicly with HTTPS, for v1.1 RSS |
| DAISY TTS edge cases — https://github.com/daisy/kb/issues/55 | Anti-pattern source | Footnote/code/abbreviation failure modes — informs the sanitizer requirements list |
| BDA writing for TTS — https://bdanewtechnologies.wordpress.com/what-technology/text-to-speech/accessible-formats/writing-for-tts/ | Anti-pattern source | Same |
| Edge "Read Aloud" — https://www.microsoft.com/en-us/edge/features/read-aloud | Competitor | Voice picker UI precedent (offline + online voice tiers grouped in dropdown) |

## Review Log

| Loop | Findings | Changes Made |
|---|---|---|
| 1 | (a) Resume position cross-device wording vague; (b) No coverage of mid-listen summary regen; (c) Pluggable goal didn't state extensibility intent for future engines; (d) Implicit conflict between manual generation (D5) and instant browser play (Journey 1) — needed explicit fallback rule | (a) Updated Journey 1 step 7 + tightened D9 with `audio_position` table sketch and per-device context; (b) Added Empty States row + new D13 (finish-current-section-then-offer); (c) Added Goal line + matching Non-Goal for engine-plugin-discovery; (d) Added new D14 (Web Speech instant fallback when no pre-gen MP3, regardless of default engine) |
| 2 | (a) No success metric tied spike outcome to v1 changes; (b) D14's mention of engine-labeling was buried — the cross-section voice-change risk is the #1 anti-pattern from research and deserved a Friction row; (c) No requirements coverage for audio file lifecycle (delete / regen-replace); (d) Journey 2 step 5 over-specified Apple-ecosystem behavior | (a) Added Success Metric row "Spike materially shapes v1" with /verify check; (b) Added Friction row "Why does this section sound different" with engine-label + per-section icon mitigation; (c) Added Goal "User can delete generated audio…" + tightened D12 to specify replace-on-regen and explicit-user-delete; (d) Softened Journey 2 step 5 to be transfer-mechanism-agnostic |

## Open Questions

| # | Question | Owner | Needed By |
|---|---|---|---|
| 1 | What is the exact Kokoro install path on macOS ARM64 in 2026 — is the `kokoro` PyPI package wheels-ready or does it need the ONNX runtime via a separate `onnxruntime` install? Spike must answer concretely with a verified install command. | Maneesh / spike | Before /spec |
| 2 | What's the spike's success criterion? Proposal: *"After 5 minutes of listening to a Kokoro-narrated section summary on a real book, would I keep using it?"* — yes/no, recorded. | Maneesh | Before spike begins |
| 3 | Should the "auto-advance to next section" behavior in Journey 1 default ON or OFF? Default ON matches audiobook UX expectations; default OFF is more deliberate. | Maneesh | Before /spec |
| 4 | Where exactly does the playback bar live in the existing reader layout? Sticky bottom (audio-app convention) vs floating panel (less invasive) vs header-integrated. Wireframes will resolve. | /wireframes | Before /spec |
| 5 | If both engines are installed, what's the default-engine rule for "click play in browser"? Web Speech (instant) vs local (consistent with pre-generated MP3s). Spike informs. | Spike outcome | Before /spec |
| 6 | Do we need any audio-job concurrency separate from the existing global single-RUNNING queue? Long audio jobs would block summarization for 20+ minutes; consider a separate worker or per-job-type queue. | /spec | During /spec |
| 7 | Annotations playlist: include the surrounding sentence as context, or just the highlighted span? Just-the-span is faster but loses meaning; with-context is richer but longer. | /wireframes or user | Before /spec |
| 8 | MP3 cleanup policy when a book is deleted, or when a section's summary is regenerated. Auto-delete vs orphan-and-warn? | /spec | During /spec |
| 9 | Is "play book summary" on the library list page (not just book detail) in v1, or is book detail enough? Affects how aggressive the surface coverage is. | Maneesh | Before /spec |

## Wireframes

Generated: 2026-05-02
Folder: `docs/wireframes/2026-05-02-audiobook-mode/`
Index: `docs/wireframes/2026-05-02-audiobook-mode/index.html`
PSYCH walkthrough: `docs/wireframes/2026-05-02-audiobook-mode/psych-findings.md`
MSF analysis: `docs/wireframes/2026-05-02-audiobook-mode/msf-findings.md` (canonical at `docs/msf/2026-05-02-audiobook-mode-msf-analysis.md`)

| # | Component | Devices | States | File |
|---|-----------|---------|--------|------|
| 01 | Reader · Section player | desktop-web, mobile-web | 7 (default · playing-with-highlight · paused-with-resume · loading-voice · no-summary-disabled · stale-source-banner · mid-listen-regen-banner) | `01_reader-section-player_{device}.html` |
| 02 | Book summary player | desktop-web, mobile-web | 3 (default · playing · ended-auto-advance) | `02_book-summary-player_{device}.html` |
| 03 | Book detail · Audio panel | desktop-web, mobile-web | 4 (no-audio · partial · full · generating) | `03_book-detail-audio_{device}.html` |
| 04 | Generate audio modal | desktop-web, mobile-web | 3 (default · model-download-required · error) | `04_generate-audio-modal_{device}.html` |
| 05 | Audio files list | desktop-web, mobile-web | 3 (populated · empty · partial-failed) | `05_audio-files-list_{device}.html` |
| 06 | Annotations playlist player | desktop-web, mobile-web | 3 (default-list · playing · empty) | `06_annotations-player_{device}.html` |
| 07 | Settings · TTS panel | desktop-web, mobile-web | 4 (default · voice-sample-loading · model-not-downloaded · no-voices-available) | `07_settings-tts_{device}.html` |

## Wireframes & UX Analysis Updates (2026-05-02)

Added during `/wireframes` Phase 6 (PSYCH) and Phase 7 (MSF). These are scope additions or hardening notes that must carry forward into `/spec`.

### Hard requirements added by MSF

- **M1 — Spike-derived voice guidance is a Settings UI requirement, not boilerplate.** The existing Success Metric "Spike materially shapes v1" is restated as a hard /spec requirement: the Settings → TTS pane MUST surface a 2–3 sentence spike-derived comparison (Web Speech vs. Kokoro on the user's actual content), include a "Listen to comparison" button that plays the same passage in both, and link to `docs/spikes/2026-05-XX-tts-engine-spike.md`. The wireframe (`07_settings-tts_*.html`) reflects this.
- **S1 — Web Speech voice MUST also be sample-able from Settings.** Sampling cannot be Kokoro-only; the user has to A/B before committing.
- **S2 — Annotations playlist checkbox in the Generate Audio modal defaults to ON** (with a "recommended" pill). The annotations playlist is a named v1 goal; OFF-default contradicted that.
- **S3 — Pre-warm the Kokoro engine on `bookcompanion serve` startup** when local engine is selected. Surface the warm/cold state in Settings → TTS as a status indicator. (Already implied by req-doc Friction §cold-start; making it a /spec requirement.)

### v1 scope additions

- **N1 — Per-row Delete on the Audio Files page.** Surgical control after re-summarizing one section. Wireframe updated.
- **N2 — Library-level "Regenerate all stale audio" CTA.** When multiple books have stale audio (per the existing stale-source banner D13), a single library-level action removes the per-book regenerate friction P3 (Library-curator) hits. Defer to /spec for placement; v1 scope addition.
- **N3 — Playbar shows section elapsed/total + sentence index** (e.g., "2:14 / 6:08 · sentence 17 of 47"). Wireframe updated.
- **N4 — Visualize the 0.5-second pause + tone-shift cue** between highlight and note in the Annotations playlist UI (a thin divider with ♪ icon). Wireframe updated.

### Scope rejections (v1)

- **S4 — Library-list "Has audio" filter — REJECTED by user.** Rationale: an on-demand filter for "books with audio" is rarely needed enough to justify a permanent UI affordance. Books that have audio are surfaced via the per-book detail page; cross-library queries can be done on demand.

### Copy / behavior changes from PSYCH walkthrough

- **F1 — Generate-audio CTA on book detail now shows an inline cost estimate** ("~12 min · ~140 MB for 47 sections"). Wireframe `03_book-detail-audio_*.html` updated.
- **F2 — "Play as audio" CTA on annotations tab now shows estimated playlist duration** ("~9 min · 18 highlights"). Wireframe `06_annotations-player_*.html` updated.
- **F3 — Resume context disclaimer is "from this browser" not "on this device".** Per D9 the position is per-browser; cross-device handoff is best-effort and out of v1. Update Journey 1 step 7 to use "browser" terminology consistently.
- **F4 — Annotations player engine chip carries an explanatory annotation** about the pre-gen requirement (D14 fallback rule). Wireframe `06_annotations-player_*.html` updated.

### Open question added by MSF

- **OQ-10:** Should the annotations playlist support runtime Web Speech streaming when no pre-gen MP3 exists (consistent with D14's section-summary rule), or does it require pre-generation? Wireframe currently assumes "pre-gen recommended, Web Speech fallback available". Confirm in /spec.
