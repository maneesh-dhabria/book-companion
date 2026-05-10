# Wireframes Review Log

**Date:** 2026-05-10
**Rigor:** medium (one cross-file reviewer pass; no second loop)
**Findings:** 17 (4 high, 7 medium, 6 low) → 7 applied, 10 deferred

## Applied (high + select medium)

| Severity | File(s) | Fix |
|----------|---------|-----|
| high | ALL 10 | `data-annotations="on"` → `"off"` (default state shows design first, not scaffolding) |
| high | `02_quiz_specific_chapters` | Removed all `tokens` / `LLM context` strings (G5 measurement compliance) — tooltip and at-cap copy rewritten as user-facing scope language |
| high | `06_audio_empty_no_web_speech` | Disabled-Listen tooltip caption contrast bumped from `text-slate-400` (~3.0:1) to `text-slate-600` (~7:1, AA-passing) |
| high | `07/08_generate_modal*` | Added `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, and an icon-only Close (×) button per modal |
| medium | `05_audio_empty_default` | Demoted-caption contrast bumped from `text-slate-400` to `text-slate-500` |
| medium | `01/03` state-switcher | Renamed `data-state="error"` → `"recovered"` for non-error recovered states |
| medium | `05/09` playbar | Wrapped ▶/⏸ glyphs in `<span aria-hidden="true">` to avoid SR double-announce next to `aria-label` |

## Deferred to /spec or /verify

These are real findings but lower-leverage; documented here for spec-time absorption.

| # | File(s) | Finding | Disposition |
|---|---------|---------|-------------|
| 1 | `03` | Toast meta-copy span ("No dismiss — sticky until retry success.") leaks designer intent into product UI | /spec: remove or move into the annotations layer |
| 2 | `06` | Default-state Listen button references `aria-describedby="listen-tip"` but the matching span only exists in Hover state | /spec: add a visually-hidden `<span class="sr-only">` carrying the tip on the default state |
| 3 | `04, 07-10` | State-slug `data-state="error"` reused for `confirming` and `toggled` states | /spec: align slugs to labels in the state-switcher implementation |
| 4 | ALL | Tabstrip tabs missing `aria-selected="false"` on inactive tabs and `role="tablist"` on later files | /spec: codify a Tabs component with consistent ARIA contract |
| 5 | `09` | Segmented engine picker placement adjacent-to-voice-selector but visually crowded on narrow widths | /spec: group segmented + voice in flex container with consistent ordering |
| 6 | `08` | Estimate row labels include `(delta)` parenthetical — engineering jargon | /spec: drop `(delta)` from labels (delta is conveyed by the "3 of 17 sections" subline) |
| 7 | `08` | Disabled-CTA copy "All sections already have MP3s" is sentence-shaped on a button surface | /spec: button label "Nothing to generate"; explanation lives in the emerald banner above |
| 8 | `07` | "Settings → Text-to-speech" footer ref not wired as anchor link | /spec: anchor to `10_settings_compare_voices.html#audio` |
| 9 | `10` | "Playing Web Speech" chip uses `bc-chip--neutral` while "Playing Kokoro" uses `bc-chip--engine` | /spec: use `bc-chip--engine` for both engine-currently-playing chips |
| 10 | `09` | Regenerate-CTA caption "~30 sec · ~9 MB delta" uses `delta` jargon | /spec: replace with "~30 sec to generate · ~9 MB on disk" matching modal vocabulary |

## Outcome

Visual language and FR fidelity are stable. The deferred set is implementation-detail / consistency hygiene, not architectural — fine to absorb during /spec when these wireframes get translated into Vue components.
