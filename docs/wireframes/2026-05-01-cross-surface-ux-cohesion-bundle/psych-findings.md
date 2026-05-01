# PSYCH Walkthrough — Cross-Surface UX Cohesion Bundle

**Date:** 2026-05-01
**Tier:** 2 (mandatory PSYCH)
**Wireframes:** `docs/wireframes/2026-05-01-cross-surface-ux-cohesion-bundle/`
**Entry-context default:** Medium-intent = **40** (Maneesh, the sole user, is already engaged with the app — not a cold acquisition flow). Override: none.

---

## Driver palette

| + drivers | − drivers |
|---|---|
| Attractive visuals · Social proof · Credibility · Urgency · Progress indicators · Value previews · Completion cues · Immediate value | Form fields · Decisions · Clicks · Waiting · Ambiguous options · Unfamiliar terminology · Missing feedback · Unclear UI |

**Thresholds:** cumulative `<20` = danger · cumulative `<0` = bounce risk · single-screen Δ `<-20` = flagged regardless.

---

## Journey 1 — User reads the book summary

```
Start: 40 (Medium)
Step 1 → 01_book-detail-overview_desktop-web.html      (Default state)
Step 2 → 02_book-detail-summary-tab_desktop-web.html   (Populated state)
```

### Element scoring

| # | Screen | Element | + / − | Reason |
|---|---|---|---|---|
| 1 | 01 | Single primary `[▶ Read]` CTA | +5 | Decision clarity (Hick's law — 1 obvious action) |
| 2 | 01 | New `[Summary]` tab visible in tab strip | +6 | Recognition over recall — user sees the path before clicking |
| 3 | 01 | Status pill "✓ All 21 sections summarized" | +4 | Credibility signal that the summary will be coherent |
| 4 | 01 | Overflow `[⋯]` button (purpose ambiguous) | −3 | Hidden options; user must learn what's behind it |
| | | **Screen Δ:** | **+12** | Cumulative: 52 |
| 5 | 02 | Tab indicator on Summary | +2 | Confirms successful navigation |
| 6 | 02 | Markdown summary renders immediately | +8 | Immediate value delivery — the "aha" moment |
| 7 | 02 | "Generated 2026-04-29 with preset `practitioner_bullets`" | +3 | Credibility / provenance |
| 8 | 02 | "Read in reader" + "Regenerate" actions | +2 | Clear next-step affordances |
| | | **Screen Δ:** | **+15** | Cumulative: **67** ✓ healthy |

### Screen rollup

| Step | Screen | Δ | Cumulative | Status |
|---|---|---|---|---|
| 1 | 01 Book Detail Overview | +12 | 52 | OK |
| 2 | 02 Summary tab (populated) | +15 | 67 | OK |

**Verdict:** strong journey. The `[Summary]` tab being visible in the tab strip is the load-bearing affordance — without it the user wouldn't know book summaries exist.

---

## Journey 2 — User generates a book summary for the first time

```
Start: 40 (Medium)
Step 1 → 01_book-detail-overview_desktop-web.html       (Default — assumes some sections summarized)
Step 2 → 02_book-detail-summary-tab_desktop-web.html    (Empty state)
Step 3 → 02_book-detail-summary-tab_desktop-web.html    (In-progress state — determinate progress bar)
Step 4 → 02_book-detail-summary-tab_desktop-web.html    (Populated state)
```

### Element scoring

| # | Screen | Element | + / − | Reason |
|---|---|---|---|---|
| 1 | 01 | New `[Summary]` tab + "21 sections summarized" pill | +6 | Recognition — user sees the path |
| | | **Screen Δ:** | **+6** | Cumulative: 46 |
| 2 | 02-empty | Empty-state title "No book summary yet" + 1-sentence why | +5 | Plain-language explanation, low friction |
| 3 | 02-empty | "X of Y sections summarized so far" reassurance | +4 | Removes "do I need to do something else first?" anxiety |
| 4 | 02-empty | Single `Generate book summary` primary CTA | +6 | Decision clarity |
| 5 | 02-empty | Implicit wait time unknown | −4 | Missing feedback — user doesn't know if this takes 10s or 5min |
| | | **Screen Δ:** | **+11** | Cumulative: 57 |
| 6 | 02-progress | Determinate progress bar "14 of 21" | +8 | Strong progress signal — addresses the wait-time anxiety from step 5 |
| 7 | 02-progress | Per-section label "Processing section 14: Where to Play…" | +5 | Visibility of system status — user sees what's happening now |
| 8 | 02-progress | Cancel button visible | +3 | User control & freedom |
| 9 | 02-progress | No ETA shown | −2 | Could amplify the +8 if "≈ 2 min remaining" were shown |
| | | **Screen Δ:** | **+14** | Cumulative: 71 |
| 10 | 02-populated | Summary appears | +10 | Reward — "aha" moment |
| 11 | 02-populated | Compression footer ("≈ ~10% of section summaries") | +2 | Credibility signal |
| | | **Screen Δ:** | **+12** | Cumulative: **83** ✓ very healthy |

### Screen rollup

| Step | Screen | Δ | Cumulative | Status |
|---|---|---|---|---|
| 1 | 01 Book Detail Overview | +6 | 46 | OK |
| 2 | 02 Summary tab (empty) | +11 | 57 | OK |
| 3 | 02 Summary tab (in-progress) | +14 | 71 | OK |
| 4 | 02 Summary tab (populated) | +12 | 83 | OK |

**Verdict:** healthy throughout. The determinate progress bar is the load-bearing element — without it, the wait between Step 2 and Step 4 would create a danger zone.

**Finding F1 (low):** consider adding ETA next to the progress bar ("≈ 2 min remaining") to upgrade an already-good state.

---

## Journey 3 — User creates a custom preset

```
Start: 40 (Medium)
Step 1 → 06_preset-detail-system_desktop-web.html       (System preset selected)
Step 2 → 06 → click "+ New preset" → opens 05
Step 3 → 05_preset-create-edit-form_desktop-web.html    (New-empty)
Step 4 → 05_preset-create-edit-form_desktop-web.html    (Saving)
Step 5 → 06_preset-detail-system_desktop-web.html       (User-selected, the new preset)
```

### Element scoring

| # | Screen | Element | + / − | Reason |
|---|---|---|---|---|
| 1 | 06 | Preset list showing system + user presets with badges | +5 | Recognition — user understands the IA before acting |
| 2 | 06 | Raw Jinja template visible for the system preset they're studying | +6 | Credibility / understanding — they can see what they're emulating |
| 3 | 06 | "+ New preset" button, top-of-list | +5 | Discoverable entry point |
| | | **Screen Δ:** | **+16** | Cumulative: 56 |
| 4 | 05-empty | Modal opens, title "New preset" | +2 | Confirms navigation |
| 5 | 05-empty | 3 stacked text fields (name/label/description) | −4 | Form fields — pure friction |
| 6 | 05-empty | 4-card facet grid (visual, click-to-pick chips) | +6 | Reduces decision cost vs. dropdowns; "Decisions" friction softened |
| 7 | 05-empty | Facet vocabulary unfamiliar to a first-timer ("content_focus", "compression") | −5 | Unfamiliar terminology — biggest friction in this journey |
| 8 | 05-empty | No inline help / tooltip explaining facets | −4 | Missing feedback / Help |
| 9 | 05-empty | Save disabled until valid | +3 | Error prevention |
| | | **Screen Δ:** | **−2** | Cumulative: 54 — flagged: single-screen Δ went negative |
| 10 | 05-saving | Spinner + "Saving…" | +2 | Visibility of system status |
| | | **Screen Δ:** | **+2** | Cumulative: 56 |
| 11 | 06-user-sel | New preset appears in list with "user" badge | +6 | Reward — completion cue |
| 12 | 06-user-sel | Edit + Delete buttons exposed | +3 | Affordance for next steps |
| | | **Screen Δ:** | **+9** | Cumulative: **65** ✓ recovered |

### Screen rollup

| Step | Screen | Δ | Cumulative | Status |
|---|---|---|---|---|
| 1 | 06 Preset detail (system) | +16 | 56 | OK |
| 3 | 05 New preset form (empty) | −2 | 54 | ⚠️ Δ negative — single-screen flag |
| 4 | 05 Saving | +2 | 56 | OK |
| 5 | 06 User-selected (new preset) | +9 | 65 | OK ✓ |

**Verdict:** the form-fill step is the weak link. Cumulative never enters danger (lowest = 54), but Δ goes negative on Step 3 because facet terminology is opaque to a user who hasn't used the CLI before. Two findings worth surfacing.

**Finding F2 (medium):** facet vocabulary on the New Preset form is jargon. Add inline help (a `?` tooltip or a single-sentence subhead per card) explaining what each dimension does in plain language.

**Finding F3 (low):** consider showing the resulting prompt template *preview* alongside the facet pickers (read-only), so the user sees what their choices produce before saving. Strong "value preview" driver.

---

## Drive curve (sparkline)

```
J1: 40 → 52 → 67               ▁▆█
J2: 40 → 46 → 57 → 71 → 83     ▁▃▅▇█
J3: 40 → 56 → 54 → 56 → 65     ▁█▇█▇█  (dip at the form, recovery at completion)
```

---

## Findings to surface

| ID | Severity | Finding | Target | Proposed fix |
|---|---|---|---|---|
| F1 | low | No ETA on book-summary in-progress state | wireframe 02 | Add "≈ N min remaining" next to progress bar |
| F2 | medium | Facet vocabulary on New Preset form is jargon (compression / content_focus / audience) without inline help | wireframe 05 | Add a one-sentence subhead per facet card explaining the dimension in plain language; e.g., "Audience — who is this summary written for?" |
| F3 | low | New Preset form doesn't show a preview of the resulting prompt template | wireframe 05 | Add a collapsible "Preview prompt" panel at the bottom that updates as facets change |

---

## Applied changes

| Journey | Screen | Finding | Fix | Status |
|---|---|---|---|---|
| J3 | wireframe 05 (all 4 states) | F2 — facet vocabulary jargon | Added 1-sentence plain-language subhead under each of the 4 facet card titles (Style, Audience, Compression, Content focus). 16 total inserts (4 facets × 4 states). | Applied |
| J2 | wireframe 02 | F1 — no ETA on progress | **Skipped** per user disposition — low severity, requires per-section timing infra not yet present. | Skipped |
| J3 | wireframe 05 | F3 — no live preview of resulting prompt | **Skipped** per user disposition — raw Jinja viewer on system presets (wireframe 06) is sufficient; users can copy-and-edit. | Skipped |

## Unsurfaced findings

None — all 3 findings surfaced.
