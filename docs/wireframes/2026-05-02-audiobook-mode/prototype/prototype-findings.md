# Prototype Findings — Audiobook Mode

Generated: 2026-05-02
Reviewers: 2 subagents (one per device file). Aggregated below by severity, then device.
Loop count: 1 (per skill cap of 2; second loop deferred — findings surfaced to user instead).

---

## Surfaced to user via Phase 8 (top 4)

These are surfaced via AskUserQuestion for explicit disposition. See conversation transcript.

| # | Severity | Source | Finding | Proposed fix |
|---|---|---|---|---|
| 1 | high | mobile | Many controls render with aria-label + visual affordance but no onClick (Original/Summary toggle, TOC button, top-bar More, BookHeader More, section-row More/Generate, Download, Cancel, Retry, every stale-source Regenerate banner). For dispatchers / accessibility users, this is worse than missing — the affordance is announced but does nothing. | Wire each to a meaningful state change or toast. Highest-leverage fixes: (a) Original/Summary toggle should switch the rendered text; (b) Stale-source Regenerate buttons should mark the section non-stale and show a success toast; (c) Settings TOC + More buttons should toast "not in v1 prototype". |
| 2 | medium | both | ReaderSection always highlights sentence index 2, regardless of `player.sentence_index`. The headline value of audiobook mode (sentence sync as audio plays) is undersold. | Bind active-sentence index to `player.sentence_index % section.summary_sentences.length` so the karaoke effect is visible when the user clicks Play. |
| 3 | medium | desktop | Resume affordance only renders when state-switcher is set to `paused`. With `audio.rememberPosition: true`, returning users with a stored position should see the resume card on default load. | When opening a section whose mock data implies a saved position (audio_status === "complete"), show the resume card by default. Alternative: fold the resume affordance into the play button copy ("Resume from sentence 16 / Start from beginning"). |
| 4 | medium | both | Anti-pattern: second accent color. `bc-status-pill--running` (blue #1e40af) and `bc-banner--info` (blue) introduce a non-indigo blue palette next to the indigo EngineChip. Users will struggle to disambiguate "engine" vs "running" vs "info" because all three sit in adjacent tints of blue. | Re-tint info banner and running pill to indigo (`#eef2ff` bg, `#c7d2fe` border, `#3730a3` text), or move the running pill to neutral grey. Reserve indigo strictly for the EngineChip + accent CTAs. |

---

## All findings (logged for spec handoff; not auto-fixed)

### Desktop · `index.desktop-web.html`

| # | Severity | Heuristic | Finding | Suggested fix |
|---|---|---|---|---|
| D1 | medium | x-interaction:defaultStates.empty | AnnotationsPlayerScreen empty state shows only title + description, no CTA. | Add icon (✎) + CTA Button "Open reader" to first section. |
| D2 | medium | x-interaction:defaultStates.empty | BookAudioTabScreen "No sections indexed" empty state has no icon and no CTA. | Add icon + CTA "Re-import book" or "Back to library". |
| D3 | medium | x-content.buttonVerbs | AnnotationsPlayer primary CTA reads "Play all" — buttonVerbs contract specifies "Listen". | Rename to "Listen to all" (matches "Listen to book summary" used elsewhere). |
| D4 | medium | second accent color | bc-status-pill--running and bc-banner--info both use a blue palette, distinct from the indigo EngineChip. | Re-tint to indigo or move running-pill to neutral grey. |
| D5 | medium | engine vs status conflation | Inside the BookAudioTab progress card, the EngineChip (indigo) sits next to a Badge tone="info" (also indigo-ish) showing sections progress. Tonal collision between "engine" and "job state". | Use neutral grey Badge for the "4 / 11 sections" counter; keep status pills on warm/grey/green. |
| D6 | medium | x-interaction:audio.rememberPosition | Resume card only appears in paused state-tab; with `rememberPosition: true` it should appear on default load when a position exists. | Show bc-resume-card on default load when audio_status === "complete". |
| D7 | low | I3 / consistency | Sections table renders identical "stale" pill from two paths: `(audio_status === "complete" && is_stale)` AND `audio_status === "stale"`. | Pick canonical representation; remove the dead branch. |
| D8 | low | x-content.formats.duration | Job ETA renders as "~N min" but section durations use M:SS — minor inconsistency. | Document the exception (ETA = round-minute) or unify. |
| D9 | low | M1 / discoverability | GenerateAudioModal filters voices to `engine === "kokoro"`, so Web Speech voices aren't sample-able from the Generate flow. (They are sample-able from Settings — contract met, but not transparent here.) | Add a "Web Speech can't be pre-generated — sample voices in Settings" hint inside the modal. |
| D10 | low | V1 / TopBar redundancy | Sidebar has Settings nav AND TopBar has Settings link — two entry points to the same destination. | Drop the topbar Settings link on desktop. |
| D11 | low | A3 / decorative emoji | Settings spike-summary banner uses 🔬 icon; sidebar uses 📚/⚙/📖. DESIGN.md voice rule lists "emoji in copy" as something to avoid. | Replace with monochrome line icons or stylized text characters. |
| D12 | low | I2 / playbar engine visibility | Playbar component is mounted but I cannot verify from this file alone whether it renders engine + voice. | Confirm `<EngineChip engine={p.engine} voice={p.voice} />` is rendered inside Playbar (it is — components.js Playbar atom renders the chip). |

### Mobile · `index.mobile-web.html`

| # | Severity | Heuristic | Finding | Suggested fix |
|---|---|---|---|---|
| M1 | high | I3 / state-feedback | ~12 dead controls with aria-label + visual affordance but no onClick. (Detailed list in Surfaced #1.) | Wire each to a meaningful state change or toast. |
| M2 | medium | V2 / sentence-sync fidelity | Always highlights sentence index 2; player.sentence_index is ignored. | Bind to `player.sentence_index % length`. |
| M3 | medium | I2 / play/pause toggle | Annotations playlist Listen button switches label to "Playing" but doesn't toggle to Pause. | When playing, show "Pause" with onClick that pauses. |
| M4 | medium | I3 / Settings sampling concurrency | playSample early-returns when stateKey === "sample"; tapping a different voice silently no-ops. | Cancel in-flight sample, start new one. Or disable other Sample buttons. |
| M5 | medium | x-interaction:loading=skeleton | Reader "Loading voice" state uses inline Spinner pill, not skeleton block. | Replace spinner pill with skeleton matching the prose region. |
| M6 | low | x-content.buttonVerbs | GenerateAudioModal uses ▶ glyph for sample; Settings uses labeled "Sample" button. Same action, two affordances. | Use labeled "Sample" in both. |
| M7 | low | M3 / bottom-nav active state | Bottom-nav Search tab toasts "not implemented" but never enters active state — Library stays highlighted, contradicting tap. | Remove Search from bottom-nav, or briefly highlight before reverting. |
| M8 | low | A3 / dead aria-labels | Many controls have descriptive aria-labels but no handler. Screen-reader users hear actions that don't exist. | Wire or remove; at minimum mark `aria-disabled="true"` and grey. |
| M9 | low | R2 / cost estimate | `minutes = sectionsCount * 9` over-counts already-generated sections. | Subtract `audio_sections_count` or filter `audio_status !== "complete"`. |
| M10 | low | R3 / heuristic divergence | Annotation playlist hard-coded "~9 min" but modal estimator uses 1.5 min/highlight. | Single helper `estimatePlaylistMinutes(n)`. |
| M11 | low | J3 / Kbd on mobile | "?" Keyboard shortcuts button shown on mobile-web — touch users have no keyboard. | Hide on mobile shell (or render only when hover-capable input detected). |
| M12 | low | V3 / sticky StateSwitcher | StateSwitcher pill row sits above the sticky reader-header; on scroll the switcher slides away while the header docks — visually jarring. | Either both sticky, or make StateSwitcher floating. |

---

## Unsurfaced findings (deferred to /spec)

All low-severity items above plus:

- Engine chip in sidebar / cover initials (`📖`) — emoji glyphs vs SVG icons trade-off; deferable.
- Skeleton vs spinner contract enforcement could be added as a /verify lint rule.
- Cost-estimate constants live inline; would benefit from a shared helper.

## Applied changes

None this loop. Findings surfaced to user; user decides whether to apply, defer, or update upstream wireframes/req-doc.

---

## Loop tracker

- Loop 1: dispatched 2 reviewer subagents (one per device file). Findings recorded above. **Did not run loop 2** — second loop reserved for fixes; surfaced to user instead per Phase 8 of the skill.
