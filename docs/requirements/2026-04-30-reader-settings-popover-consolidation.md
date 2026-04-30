# Reader Settings Popover Consolidation — Requirements

**Date:** 2026-04-30
**Status:** Draft
**Tier:** 2 — Enhancement / UX Fix

## Problem

The reader settings popover (the gear icon on the section reading view) presents two stacked theme pickers showing the same six themes, plus typography/layout controls visible by default that most users never touch. The result is visually confusing, vertically long (~1100px in a ~600px viewport), and forces users to scroll past redundant controls to reach what they actually want. Custom-theme editing is interleaved into the main flow, and the sticky save bar overlaps content beneath it.

### Who & Why Now

- **Persona:** Anyone reading a book in the web UI who wants to switch theme, dim the page, or tweak text size for comfort.
- **Trigger:** The current popover shipped with v1.5 reader work and the v1.5 polish loop layered new affordances (PresetCards, Custom slot, sticky save bar) without removing the older theme grid. Visual review on 2026-04-30 confirmed the duplication is now user-visible and the layout is cluttered enough to look broken.

## Goals & Non-Goals

### Goals

- **One theme picker** — the popover shows exactly one grid of theme cards, with a clear "THEME" label and consistent visual style.
- **Compact default state** — when the popover opens, the user sees only the theme grid plus the lightweight reader chrome toggles (highlights, annotations scope). Typography and layout controls are hidden until the user opts in.
- **Customisation is opt-in and inline** — clicking the Custom card expands the full editor (background/foreground swatches, accent picker, font, size, line spacing, content width) inside the popover, anchored to the Custom card. No modal, no separate flyout.
- **Presets are immutable** — picking Sepia/Dark/etc. applies the bundle as-is. Any deviation forks into Custom. Users never see a "preset is selected but font is mutated" half-state.
- **Save-bar never occludes content** — when the inline editor is open and dirty, the save/revert affordance sits inside the editor flow, not pinned over other rows.
- **Single active-state visual language** — exactly one styling rule (e.g. 2px primary border + corner ✓) used across every card the user can pick.
- **Keyboard & screen-reader accessible** — the theme grid supports keyboard navigation; the active card exposes its state to assistive tech.

### Non-Goals

- NOT redesigning the `/settings → Reading` page in this iteration, because that surface owns persistent defaults (default summarization preset, custom CSS, per-book overrides) and its scope is unchanged. We will only ensure the two surfaces don't overlap.
- NOT changing the underlying preset model, the `appliedPresetKey` state machine, or the reading-presets API, because the existing data model already supports the consolidated UX — this is a presentation-layer cleanup.
- NOT introducing user-creatable named presets (e.g. "Save current as…"), because it expands scope and the current six shipped themes plus Custom cover the observed need.
- NOT migrating mobile/touch ergonomics, because the popover is desktop-first today and a separate mobile pass is its own work.

## Solution Direction

**Wireframes:** `docs/wireframes/2026-04-30_reader_settings_popover/`
- [`01_default_state.html`](../wireframes/2026-04-30_reader_settings_popover/01_default_state.html) — Compact default popover (Light active, no editor).
- [`02_custom_editor_expanded.html`](../wireframes/2026-04-30_reader_settings_popover/02_custom_editor_expanded.html) — Custom selected, inline editor expanded with dirty edits.
- [`03_states_compared.html`](../wireframes/2026-04-30_reader_settings_popover/03_states_compared.html) — Side-by-side: default · Custom collapsed · Custom expanded.

The popover collapses into three vertical zones, in order:

```
┌─ Reader Settings ─────────────────── × ┐
│                                         │
│  THEME                                  │
│  ┌──────┐ ┌──────┐ ┌──────┐             │
│  │Light │ │Sepia │ │Dark  │             │
│  │  Aa  │ │  Aa  │ │  Aa  │             │
│  └──────┘ └──────┘ └──────┘             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │Night │ │Paper │ │HiCon │ │Custom│    │
│  │  Aa  │ │  Aa  │ │  Aa  │ │  ✎   │    │
│  └──────┘ └──────┘ └──────┘ └──────┘    │
│                                         │
│  ▸ (when Custom active, inline editor   │
│     expands here: bg / fg / accent /    │
│     font / size / line-spacing / width  │
│     / live preview / Save · Revert)     │
│                                         │
│  ☑ Show highlights inline               │
│  Annotations scope: [Current ▾]         │
└─────────────────────────────────────────┘
```

**Key shifts vs. today:**

1. The current `PresetCards` grid is removed. The "THEME" grid (the one with colored backgrounds and "Aa" samples) becomes the single picker, with Custom appended as the seventh card.
2. Typography/layout controls (font, size, line spacing, content width) and the colour swatches are no longer rendered at all unless the user clicks Custom. When Custom is active, the full editor expands inline beneath the grid.
3. The sticky save bar is removed; Save/Revert buttons sit at the bottom of the inline editor where they belong contextually.
4. Picking a non-Custom theme card collapses any open Custom editor and applies the preset as a bundle. There is no concept of a "preset with mutated font" — that state is what Custom is for.

## User Journeys

### Primary Journey — Switching to Sepia for evening reading

1. User is reading section 4 of a book; gear icon top-right.
2. Click gear → popover opens to compact default state: THEME grid + chrome toggles. No typography clutter.
3. Click the "Sepia" card → page background and text instantly recolour. Sepia card shows the active checkmark. Popover stays open.
4. User clicks elsewhere or presses Esc → popover closes.

### Secondary Journey — Customising the theme

1. From the popover default state, click the "Custom" card.
2. Inline editor expands directly under the grid, seeded from whichever preset was active (e.g., Sepia colours, Georgia 16px, 1.6 line height, 720px width).
3. User adjusts background swatch, drops font size to 15px. A "Custom theme preview (not saved)" hint appears with Save and Revert buttons inside the editor.
4. User clicks Save → values persist to the Custom slot, editor stays open showing the saved state, Custom card shows active checkmark.
5. Subsequent popover opens land on the compact default with Custom active; clicking Custom re-expands the editor with the saved values.

### Alternate Journey — Returning to a preset from Custom

1. Custom is active and the inline editor is open.
2. User clicks "Light" card.
3. Inline editor collapses, any unsaved Custom edits are discarded with no prompt (they were never committed), Light becomes active. Saved Custom slot is preserved untouched for next time.

### Error / Edge Cases

| Scenario | Condition | Expected Behavior |
|----------|-----------|-------------------|
| Preset list fails to load | Network error on `/api/v1/reading-presets` | Popover shows a single error message instead of an empty grid; no theme cards rendered; chrome toggles still work. |
| Saved Custom slot empty on first open | User has never edited Custom | Custom card swatch shows a neutral placeholder; clicking it expands the editor with the active preset's values pre-seeded. |
| User has unsaved Custom edits, clicks another preset | Editor dirty, picks Light | Edits discarded silently (consistent with today). No confirm dialog — the cost of accidental loss is low and the prompt would create more friction than it saves. |
| Migrated/legacy `appliedPresetKey` references a deleted preset | localStorage points to system:99 | Existing fallback in store (`loadPresets()`) applies first available preset; no UI change needed. |
| Quota-exceeded when persisting | localStorage full | Existing one-shot toast fires; popover behaves as if the preference saved. |
| Keyboard-only user | No mouse | Tabbing into the popover lands on the close button; arrow keys move within the THEME grid; Enter/Space activates a card; the active card is announced as pressed. |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|----------|--------------------|-----------|
| D1 | Collapse to a single theme grid | (a) Keep both; differentiate as "Saved presets" vs "Themes". (b) Replace with a dropdown. (c) Single grid using the THEME-style cards. | (c). The current PresetCards style ("swatch strip + caption") looks generic; the THEME-style cards (live colour + Aa sample) preview the actual reading surface. Two grids for the same list is the root cause of "two sets of cards" confusion. |
| D2 | Hide typography/layout by default | (a) Show inline always (today). (b) Hide unless Custom active. (c) Move to `/settings/reading`. | (b). Most users pick a preset and don't tweak; surfacing six numeric controls upfront pays for an interaction <5% of users perform per session. Hiding inside Custom cleanly aligns with "presets are bundles". |
| D3 | Custom editor expands inline below the grid | (a) Modal dialog. (b) Side flyout. (c) Inline expand. | (c). Inline keeps the user in one visual context, avoids stacking-context bugs, and matches the user's stated preference. Modal/flyout would add nav cost for a frequent action. |
| D4 | Presets are strictly immutable | (a) Tweaks silently fork to Custom. (b) Tweaks live next to the grid. (c) Strict — no inline tweaks while a preset is active. | (c). Eliminates the "preset selected but font mutated" half-state. Users wanting to fine-tune already have one click to Custom; the tradeoff is a single explicit click vs. permanent latent confusion. |
| D5 | Save/Revert lives inside the inline editor | (a) Sticky bar pinned to popover bottom (today). (b) Inside the inline editor block. (c) Inside the Custom card itself. | (b). The current sticky bar overlaps content during scroll. Embedding the actions inside the editor block makes the dirty/save scope unambiguous. |
| D6 | Active state = single visual rule across all cards | (a) Keep separate styles. (b) Outline-offset everywhere. (c) 2px primary border + corner ✓ everywhere. | (c). One rule is easier to learn and easier to maintain. Border + ✓ doubles up so colour-blind users still get the affordance. |
| D7 | Theme card order: Light → Dark → Sepia → Night → Paper → High Contrast → Custom | (a) Alphabetical (today's PresetCards). (b) Brightness-grouped. (c) Backend-declared order. | (b). Light anchors as the default; Dark/Night/Sepia cluster as low-light options; Paper/High Contrast follow as specialised; Custom is the escape hatch and always last. |
| D8 | Unsaved Custom edits are discarded silently when switching presets | (a) Confirm dialog. (b) Auto-save on switch. (c) Silent discard. | (c). Edits aren't applied to the reader until Save anyway; the user has already implicitly abandoned them by clicking another card. A confirm dialog would block a common path. |
| D9 | A11y: roving tabindex within grid, aria-pressed on active card | (a) Defer to follow-up. (b) Include in this iteration. | (b). The grid is small and the patterns are well established; cost is low and it locks in the right semantics before further iteration. |

## Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| 1 | Should we track a metric for "popover opens that ended in a theme change vs no-op" to validate the compact default actually reduces churn? | Maneesh | Before /spec |
| 2 | When the inline editor is open and the user resizes the window so the popover would clip the viewport, do we shrink the editor, scroll inside the popover, or close the editor? | Maneesh | Before /spec |
| 3 | Does Custom store a single global slot (today) or one slot per book? Today's behaviour is global; confirm this stays. | Maneesh | Before /spec |
| 4 | The `/settings → Reading` page currently surfaces font/size/etc. via `ReadingSettings.vue`. Are any of those fields user-set today, or only API defaults? Determines whether we need to migrate values out of that page. | Maneesh | Before /spec |

## Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | Pending | Pending |
