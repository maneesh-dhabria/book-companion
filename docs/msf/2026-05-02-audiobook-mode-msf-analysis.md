# MSF Analysis — Audiobook Mode

Generated: 2026-05-02
Requirements: `docs/requirements/2026-05-02-audiobook-mode-requirements.md`
Wireframes: `docs/wireframes/2026-05-02-audiobook-mode/`
PSYCH: `docs/wireframes/2026-05-02-audiobook-mode/psych-findings.md` (Pass B skipped — pre-computed)
Tier: 3

## Personas (single-user, modeled across usage modes)

| # | Persona | Scenarios |
|---|---------|-----------|
| P1 | **Power Reader (re-encounter)** — has 47-book library, audio is the additive re-encounter channel | (a) Cold-evening: opens laptop after dinner, picks a 6-month-old book to listen to during dishes. (b) Warm-resume: returns to a partly-played book the next morning. |
| P2 | **Setup-mode** — installing TTS for the first time after summarizing many books | (a) Methodical: tries Web Speech first, decides Kokoro is worth the install. (b) Skeptical: installs but unsure if disk cost is justified. |
| P3 | **Library-curator** — managing audio storage and freshness | (a) Disk pressure: 8 GB used across audio, decides which books to keep audio for. (b) Stale audio: regenerated a book's summaries, needs to refresh audio. |

## Journeys

| # | Journey | Primary persona |
|---|---------|----------------|
| J1 | Listen to a section summary right now | P1 (re-encounter) |
| J2 | Pre-generate audio for a whole book | P1 (a) + P3 (b) |
| J3 | Listen to annotations from a book | P1 |
| J4 | First-time setup → first audio generation → first listen | P2 |

---

## Pass A — MSF Analysis

### J1 × P1 (Power Reader, cold-evening scenario)

**Motivation**

| Question | Answer |
|---|---|
| Job to be done | "Re-encounter what I learned 6 months ago, hands-free while doing dishes" |
| Importance/urgency | Medium — additive, not blocking. Daily-ritual-adjacent. |
| Alternatives | Speechify (paid, lossy paste), Edge Read Aloud (no resume, no annotations), or *not listening* (status quo — effective rate = 0). |
| Benefits of acting | Compounding value from prior summarization investment; mental refresh while idle. |
| Cost of inaction | Each new book summarized is worth less if old ones aren't re-encountered. |

**Friction**

| Friction | Wireframe evidence | Severity |
|---|---|---|
| First-time picking which book to listen to has no "ranked-by-recency-or-relevance" surface | Library list (existing, not redesigned for audio) does not surface "books with audio coverage" | Should |
| Click play in reader = Web Speech, but identical visual to clicking play on a section that has Kokoro pre-gen — inconsistency between sections | `01_reader-section-player` uses engine chip but it's small; the playbar transport looks identical | Nice-to-have |
| Cold-start (Kokoro voice not loaded) is bounded but creates a "broken first impression" if it happens silently | `loading-voice` state exists but it's the user's first 2-5 seconds with the feature | Should |

**Satisfaction**

| Question | Answer |
|---|---|
| Fulfilled the job? | Yes — instant Web Speech start (J1 step 2 PSYCH +8) means the user actually walks away. |
| Lived up to expectations? | Yes — sentence highlight + auto-scroll + lock-screen Media Session match audiobook-app conventions. |
| Made them feel smart? | Yes — resume position respects time invested. (PSYCH +6 on resume copy) |

### J2 × P1 (Power Reader, deciding to commit to a book) + P3 (Library-curator regenerate)

**Motivation (P1)**

| Question | Answer |
|---|---|
| Job to be done | "Make this book listenable everywhere — including phone podcast app" |
| Importance | Medium-high IF the book is one they intend to revisit; low otherwise. → Selection criterion is: which books deserve the disk + CPU? |
| Alternatives | Skip pre-gen, rely on Web Speech every time (no MP3 export, no offline). |

**Motivation (P3)**

| Question | Answer |
|---|---|
| Job to be done | "Re-generate stale audio for a book I just re-summarized; OR delete audio for books I'm done with" |
| Importance | Low (housekeeping); urgent only when disk pressure or workflow demands. |

**Friction**

| Friction | Wireframe evidence | Severity |
|---|---|---|
| **No "which book deserves audio" rationale on entry CTA** — book detail says "Generate audio" but doesn't help decide whether THIS book is worth the cost (P1) | `03_book-detail-audio` no-audio state has CTA + (now) cost preview. Does NOT show "you've revisited this book 4 times" or "high-recall" signals. | Should |
| **Annotations checkbox is OFF by default** but the annotations playlist is one of the 3 named goals — feels like a hidden feature | `04_generate-audio-modal` default state — annotations checkbox unchecked | Should |
| **No bulk regenerate for stale audio** (P3) — if 5 books had summary edits, user must enter each book detail page individually | Wireframes show only per-book regenerate; no "Regenerate all stale audio" library-level surface | Nice-to-have |
| **Delete is at book level only** — no per-section delete in v1 (matches D12, but P3 may want surgical control after re-summarizing one section) | `03_book-detail-audio` full-audio state, Delete is whole-book; `05_audio-files-list` per-row has no Delete (only Play + Download) | Nice-to-have |

**Satisfaction**

| Question | Answer |
|---|---|
| Fulfilled the job? | Yes — 100% completion bar (PSYCH +8) is a strong satisfaction moment. |
| Live up to expectations? | Yes — same SSE progress UI as summarization (familiarity). |
| Reassuring? | Strongly — disk usage transparency + ID3 tagging signal "production-ready artifact". |

### J3 × P1 (Power Reader, annotation review)

**Motivation**

| Question | Answer |
|---|---|
| Job to be done | "Spaced-repetition-style review of what I've highlighted" |
| Importance | Medium for power users who annotate; LOW or N/A if user doesn't annotate. |

**Friction**

| Friction | Wireframe evidence | Severity |
|---|---|---|
| **The annotations playlist is hidden behind the Annotations tab + a button** — discoverability is low | `06_annotations-player` default-list state — Play CTA top-right of tab is non-obvious to a first-time user | Should |
| **Audible cue between highlight + note is invisible in wireframe** — user can't tell what they're getting before pressing Play | `06_annotations-player` playing state — the cue is annotated but only visible when annotations toggled on | Nice-to-have |

**Satisfaction**

| Question | Answer |
|---|---|
| Made them feel smart? | Yes — "I'm reviewing my own thoughts" lands well; tonal cue between highlight + note is a craft signal (PSYCH +2). |
| Reassuring? | Yes — section-pill context preserved per annotation card. |

### J4 × P2 (Setup-mode, first-time install)

**Motivation**

| Question | Answer |
|---|---|
| Job to be done | "Get audiobook mode working at all so I can decide if it's worth the install" |
| Importance | High — gate to the entire feature. |
| Urgency | Low — user chose the moment to set up. |
| Alternatives | Stay on Web Speech only; never install Kokoro. |
| Benefits of acting | File output / phone-podcast-app path / quality. |

**Friction**

| Friction | Wireframe evidence | Severity |
|---|---|---|
| **The spike is a settings-page artifact but settings doesn't show user-facing engine guidance derived from it** (Success Metric in req doc demands this!) | `07_settings-tts` default state shows engine radios + 1 sentence about D14, no spike-derived comparison ("Web Speech sounds X, Kokoro sounds Y on actual book content") | **Must** |
| **Voice samples are downstream of choosing engine** — user must commit to Kokoro radio before sampling. Can't A/B without picking. | `07_settings-tts` Voice (Kokoro) section is below the engine radio. Sample buttons sit on Kokoro voices only. No Web Speech sample. | Should |
| **First-time install path forces decision before any signal** — "Default engine" radio is at top of TTS settings before user has heard either | `07_settings-tts` form ordering | Should |
| **No "skip and decide later" affordance on settings** — user must commit to defaults | Save changes button at bottom; no "I'll decide later, just enable Web Speech" path | Nice-to-have |

**Satisfaction**

| Question | Answer |
|---|---|
| Fulfilled the job? | Yes if they survived the engine decision; no if abandoned at the 100MB download prompt (Web Speech fallback exists, but is it discoverable?). |
| Reassuring? | Mixed — model-not-downloaded banner (`07_settings-tts` model-not-downloaded state) provides a clear path but the value gate is "100 MB before I know if it's good" — and this is *exactly* what the spike was supposed to inform but doesn't surface to the user. |
| Felt smart? | Could be high if the spike-derived guidance made them feel like Maneesh thought through this for them. Currently low — settings reads generic. |

---

## Recommendations

### Must (block /spec until decided)

| # | Affected | Rec | Effort |
|---|----------|-----|--------|
| M1 | `07_settings-tts` (all states) + req doc Success Metrics | Surface a 2–3 sentence **spike-derived voice comparison** in the Default-engine section: "On a 1,200-word section of *Thinking, Fast and Slow*: Web Speech sounded [adjective], Kokoro sounded [adjective]. The default below is set based on this — change if your ear differs." Add a "Listen to comparison" button that plays the same passage in both engines. This was an explicit Success Metric in the req doc ("Spike materially shapes v1 → Settings UI engine-picker copy + ≥1 paragraph of user-facing engine guidance all derived from the spike's findings"). | Medium |

### Should (strong UX wins, low/medium cost)

| # | Affected | Rec | Effort |
|---|----------|-----|--------|
| S1 | `07_settings-tts` Voice section + Web Speech | Add a **"Sample this voice"** button on the Web Speech engine row too, not just Kokoro. Lets user A/B before committing. | Low |
| S2 | `04_generate-audio-modal` default state | **Default the annotations checkbox to ON** (or add a one-line note "Recommended for spaced-repetition review"). The annotations playlist is a named goal in the req doc; OFF-default contradicts that. | Low |
| S3 | `01_reader-section-player` loading-voice state | **Pre-warm the Kokoro engine on `bookcompanion serve` startup** when local engine is selected (already promised in Friction table of req doc, but not in wireframe — add a settings note + a small "Kokoro warm" indicator in TTS settings status). | Low (note); Medium (engine pre-warm — that's a /spec concern) |
| S4 | Library list view (existing surface, NOT in wireframes) + req doc | Add a **"Has audio" filter / sort** option on the library list — tells user which books are listenable without opening each. *Defer to /spec; flag as a v1 scope addition.* | Medium (small lib list change) |
| S5 | `06_annotations-player` default-list state | Add an **introductory caption** above the Play-as-audio button on first visit: "Listen to your highlights as a 9-minute review." Improves discoverability. | Low |

### Nice-to-Have

| # | Affected | Rec | Effort |
|---|----------|-----|--------|
| N1 | `05_audio-files-list` per-row | **Per-row Delete** button (not just per-book) — surgical control after re-summarizing one section. | Low |
| N2 | Library list view | **"Regenerate all stale audio"** library-level CTA when many books have stale audio. | Medium |
| N3 | `01_reader-section-player` playbar | Show **section progress bar** (not just sentence index) — "5:42 / 11:30" elapsed/total in the playbar. (J3 has a "3 of 18", J1 doesn't show similar.) | Low |
| N4 | `06_annotations-player` playing state | **Visualize the audible cue** between highlight + note (e.g., a thin divider with ♪ icon) so reviewers see what users will hear. | Low |

---

## Phase 5 — Scope of Applied Changes

Defaulting to `--default-scope=both` (req doc + wireframes), per-recommendation user approval recorded below.

### Applied changes

| Rec | Severity | Scope | Action | Files | Status |
|-----|----------|-------|--------|-------|--------|
| M1 | Must | wireframe + req doc | Spike-derived voice guidance block in Settings TTS (both devices); req doc updated to make this a hard /spec requirement | `07_settings-tts_desktop-web.html`, `07_settings-tts_mobile-web.html`, requirements doc | Applied |
| S1 | Should | wireframe | Sample button on Web Speech radio row | `07_settings-tts_*.html` | Applied |
| S2 | Should | wireframe | Annotations checkbox defaults to ON + "recommended" pill | `04_generate-audio-modal_*.html` | Applied |
| S3 | Should | wireframe + req doc | Kokoro warm-status indicator in Settings TTS; pre-warm-on-serve noted in req doc | `07_settings-tts_*.html`, requirements doc | Applied |
| S4 | Should | — | Library-list "Has audio" filter | n/a | **Rejected by user** (on-demand filter not justified) |
| S5 | Should | wireframe | Intro caption above "Play as audio" CTA on annotations tab | `06_annotations-player_*.html` | Applied |
| N1 | Nice | wireframe | Per-row Delete button on Audio Files page (10 desktop rows, 12 mobile rows) | `05_audio-files-list_*.html` | Applied |
| N2 | Nice | req doc | Library-level "Regenerate all stale audio" — noted as v1 scope addition | requirements doc | Applied (req doc only) |
| N3 | Nice | wireframe | Playbar shows "2:14 / 6:08 · sentence 17 of 47" | `01_reader-section-player_*.html` | Applied |
| N4 | Nice | wireframe | Audible-cue divider (♪ pause · voice shift) between highlight and note | `06_annotations-player_*.html` | Applied |

## Phase 6 — Consistency Pass

| Cross-check | Status |
|---|---|
| M1: Settings TTS now references the spike doc + has a comparison-listen affordance | ✅ verified in `07_settings-tts_desktop-web.html` (lines added with `bc-banner bc-banner--info` block) |
| Req doc Wireframes section now lists M1 as a hard /spec requirement | ✅ |
| S2: Modal annotations checkbox is `checked` in HTML | ✅ both desktop and mobile |
| Engine chip in `06_annotations-player` aligns with req doc D14 + new OQ-10 | ✅ chip carries pre-gen explanation; OQ-10 logged for /spec |
| Resume copy uses "browser" not "device" everywhere | ✅ both desktop and mobile of `01_reader-section-player` |
| Audio Files list — Delete buttons match per-row pattern, no orphan rows | ✅ scripted via Python regex; counts match (10 desktop / 12 mobile) |

No contradictions detected. Wireframes folder is internally consistent and aligned with the updated requirements doc.
