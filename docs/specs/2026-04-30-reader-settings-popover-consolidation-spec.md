# Reader Settings Popover Consolidation — Spec

**Date:** 2026-04-30
**Status:** Draft
**Tier:** 2 — Enhancement / UX Fix
**Requirements:** `docs/requirements/2026-04-30-reader-settings-popover-consolidation.md`

---

## 1. Problem Statement

The reader settings popover renders two redundant theme grids and surfaces typography/layout controls upfront that most users never touch. The result is visually confusing (1100px tall in a ~600px viewport), the sticky save bar overlaps content during scroll, and the Custom card has competing click affordances. The fix collapses the two grids into one, hides typography/colour controls behind an opt-in Custom editor, and unifies the active-state visual language. Primary success metric: popover scrollHeight ≤ 480px in default state on a 1280×800 viewport.

---

## 2. Goals

| # | Goal | Success Metric |
|---|------|---------------|
| G1 | One theme picker in the popover | Exactly one element with `role="radiogroup"` (or equivalent) for theme selection in `ReaderSettingsPopover.vue` |
| G2 | Compact default popover state | Popover scrollHeight ≤ 480px when no preset is being edited (1280×800 viewport, default font) |
| G3 | Customisation is opt-in and inline | Bg/fg/accent swatches, font, size, line spacing, content width, live preview render only when `editingCustom === true` |
| G4 | Presets are immutable bundles | No control mutates `currentSettings.font_*`/`line_spacing`/`content_width_px` while `appliedPresetKey` matches `system:*` |
| G5 | Save/Revert inline, never occludes | No `position: sticky` save bar; Save/Revert sit inside the inline editor block |
| G6 | One active-state visual rule | All theme cards use a single CSS class for active state (2px primary border + corner ✓) |
| G7 | Keyboard & SR accessible | Theme grid passes axe-core; arrow keys navigate within grid; active card exposes `aria-pressed="true"` |

---

## 3. Non-Goals

- NOT redesigning `/settings → Reading` page — out of scope per requirements §Non-Goals.
- NOT changing `ReadingPreset` data model, the reading-presets API, or `appliedPresetKey` storage format — purely presentation-layer.
- NOT introducing user-creatable named presets (multiple Custom slots) — separate requirements doc if pursued.
- NOT migrating to a mobile-first layout — desktop popover only; mobile is its own pass.
- NOT replacing localStorage with backend persistence for the Custom slot — current behaviour kept.

---

## 4. Decision Log

| # | Decision | Options Considered | Rationale |
|---|----------|--------------------|-----------|
| D1 | Replace `PresetCards.vue` with a new single grid component using THEME-style cards (live colour bg + Aa sample) | (a) Keep PresetCards, restyle. (b) Keep both, differentiate. (c) New unified component. | (c). PresetCards' "swatch strip + caption" style is the part the user found unattractive. The THEME grid's live-colour cards are the keep-side of the design. Building one new component is cleaner than restyling and keeps the diff focused. |
| D2 | Grid layout: 3 columns × 3 rows (Custom on row 3, two empty cells) | (a) 4×2 (cards too narrow at popover's 400px width). (b) 2×4 (too tall). (c) 3×3 with Custom anchored bottom-left. | (c). Symmetric rows, Custom visually distinguished as "different kind". Cards stay ≥110px wide for legible Aa preview. |
| D3 | Theme card order: Light → Dark → Sepia → Night → Paper → High Contrast → Custom | (a) Alphabetical. (b) Brightness-grouped. (c) Backend order. | (b). Light = default first, low-light cluster (Dark/Sepia/Night), specialised (Paper/HiCon), Custom last as escape hatch. Decision pre-agreed in requirements D7. |
| D4 | Hide typography/layout controls until Custom is active | (a) Always visible (today). (b) Hidden unless `editingCustom`. (c) Always visible under a "More" disclosure. | (b). Pre-agreed in requirements D2. |
| D5 | Inline editor anchors below the entire grid as a full-width block | (a) Full-width below grid. (b) Below the row containing Custom (row-spanning). (c) Slide-in right panel. | (a). Simplest CSS, no row-spanning gymnastics, no width breakage at 400px. Editor block owns vertical flow when expanded. |
| D6 | Custom card single click target (no pencil) — click toggles editor + applies Custom | (a) Card = apply, pencil = edit. (b) Card = apply+edit, no pencil (toggle on second click). (c) Card = apply+edit, second click no-op. | (b). One affordance, one mental model. Toggle on second click is the natural inverse of expand-on-first. Cost of accidental collapse is zero (state is preserved). |
| D7 | Editor collapsed on every popover open, regardless of active preset | (a) Collapsed always. (b) Auto-expand if Custom active. | (a). Compact default applies symmetrically to all presets including Custom. Reopening to a tall popover would defeat G2. User clicks Custom to re-open editor (one click). |
| D8 | Empty Custom card shows neutral gradient + label "Customise" | (a) Today's gradient + "Tap to edit". (b) Mirror active preset bg/fg. (c) Big "+" icon. | (a). Imperative verb ("Customise") communicates action, gradient signals "empty/unset". Avoids the (b) ambiguity of "is this Custom or just a copy?". |
| D9 | Live preview block ("The quick brown fox…") rendered inside the inline editor only | (a) Always at popover bottom. (b) Inside editor only. (c) Remove entirely. | (b). The reader page itself is the preview when a preset is active. Preview is useful only while tweaking custom values where the popover overlays the page. |
| D10 | Reader chrome toggles (highlights, annotations scope) stay in the popover, always visible at bottom | (a) Stay (today). (b) Move to /settings/reading. (c) Hide under disclosure. | (a). Independent of theme, used per-section, small footprint. Moving them adds context-switch cost for a frequent toggle. |
| D11 | Implement `applyCustom()` semantics so it accepts a `{ openEditor: boolean }` flag, replacing the implicit popover-side state machine | (a) Keep `applyCustom()` + `openCustomPicker()` split (today). (b) Single `applyCustom({openEditor})`. (c) Editor toggle as separate store action. | (c). Cleanest separation: `applyCustom()` only changes the applied preset; a new `toggleCustomEditor()` drives `editingCustom`. Click handler calls both. |
| D12 | `editingCustom` is **not** persisted across popover opens; resets to `false` on every open | (a) Persist. (b) Reset on open. | (b). Implements D7. Implementation: `popoverOpen` watcher in store sets `editingCustom = false` on transition `false → true`. |
| D13 | Roving tabindex within theme grid; arrow keys move focus; Enter/Space activates | (a) Default tab order (each card tab-stop). (b) Roving tabindex. | (b). Standard ARIA pattern for radio-grid; keeps the popover's overall tab order short (1 stop for the grid). |

---

## 5. User Journeys

### 5.1 Switch to Sepia

1. User clicks gear → popover opens, default state (grid + chrome toggles, ~440px tall).
2. User clicks "Sepia" card → reader recolours instantly; Sepia card shows ✓; popover stays open.
3. User clicks outside or presses Esc → popover closes.

### 5.2 Customise theme (first-ever)

1. From default state, user clicks "Custom" card.
2. Reader applies Custom slot (seeded from active preset's bg/fg/accent + current font/size/spacing/width). Custom card shows ✓.
3. Editor expands below the grid: BACKGROUND swatches, FOREGROUND swatches, ACCENT (picker), FONT select, SIZE/LINE SPACING/CONTENT WIDTH steppers, ContrastBadge, live preview, Save/Revert.
4. User changes background, drops size to 15px → reader updates live; "Custom theme preview (not saved)" hint appears; Save enabled.
5. User clicks Save → values persist to localStorage Custom slot, hint disappears, editor stays open in saved state.
6. User clicks gear (close) → popover closes.

### 5.3 Re-edit saved Custom

1. User opens popover; Custom is the active preset.
2. Default state shows: grid (Custom card has ✓ + bg colour from saved slot), chrome toggles. Editor is **collapsed** (D7).
3. User clicks Custom card → editor expands with saved values pre-filled.

### 5.4 Switch from Custom back to Sepia

1. Editor open, dirty edits pending.
2. User clicks "Sepia" → editor collapses, pending edits silently discarded, Sepia applies.
3. Saved Custom slot in localStorage is untouched.

### 5.5 Toggle editor closed without switching preset

1. Editor open, Custom active.
2. User clicks "Custom" again → editor collapses; Custom remains active.
3. Reader unchanged.

### 5.6 Keyboard navigation

1. User opens popover via gear (clicked or Enter/Space on focused button).
2. Tab → focus lands on close (×) button.
3. Tab → focus lands on theme grid (the active card, or Light if none active).
4. Arrow Right/Down → focus moves to next card; Arrow Left/Up → previous. Wraps within row/grid per ARIA radiogroup norms.
5. Enter or Space on focused card → applies that preset (or toggles Custom editor).
6. Tab past grid → focus lands on chrome toggles, then (if editor open) into editor controls.

---

## 6. Functional Requirements

### 6.1 Theme grid

| ID | Requirement |
|----|-------------|
| FR-01 | Popover renders exactly one theme grid component containing seven cards in this order: Light, Dark, Sepia, Night, Paper, High Contrast, Custom. |
| FR-02 | Grid uses 3 columns; cards flow into row-major order. Custom anchors at row 3 column 1. |
| FR-02b | The two empty cells in row 3 render as transparent inert grid space: no border, no background, `pointer-events: none`, `aria-hidden="true"`. The inline editor (when expanded) sits flush below the grid with a 0.75rem top margin so row 3 reads visually as "Custom card on the left, blank to its right". |
| FR-03 | Each non-Custom card displays: live `bg` colour as card background, `fg` colour as text colour, the theme name (e.g. "Sepia"), an "Aa" sample. |
| FR-04 | Custom card displays: saved `bg` colour as background (or neutral gradient if slot empty), the label "Custom", and either an "Aa" sample (if slot saved) or "Customise" text (if slot empty). |
| FR-05 | The active card (one of seven, at most) shows a 2px primary-colour border and a ✓ glyph in its top-right corner. |
| FR-06 | Cards have `role="radio"`, `aria-pressed` reflecting active state, and `aria-label="<theme name> theme"`. The grid container has `role="radiogroup"` with `aria-label="Reader theme"`. |
| FR-07 | Clicking a non-Custom card calls `store.applyPreset(id)`. The popover stays open. |
| FR-08 | Clicking the Custom card invokes the behaviour table in §5 / D6: applies Custom (if not active) and toggles the editor. |

### 6.2 Default popover state

| ID | Requirement |
|----|-------------|
| FR-09 | When the popover opens, `editingCustom` is set to `false` (overrides any prior session value). |
| FR-10 | In default state, the popover renders only: header (title + close button), theme grid, chrome toggles row. No font/size/spacing/width/colour controls render. |
| FR-11 | Popover scrollHeight in default state is ≤ 480px on 1280×800 viewport with default font. |

### 6.3 Inline custom editor

| ID | Requirement |
|----|-------------|
| FR-12 | Editor renders only when `editingCustom === true`, immediately below the theme grid, as a full-width block. |
| FR-13 | Editor contains, in order: BACKGROUND swatches, FOREGROUND swatches, ACCENT (color picker), FONT select, SIZE stepper, LINE SPACING stepper, CONTENT WIDTH stepper, ContrastBadge, live preview block, Save/Revert action row. |
| FR-13b | When the editor expands (Custom click), focus moves programmatically to the first BACKGROUND swatch. When the editor collapses, focus returns to the Custom card. Implements the keyboard flow in §5.6 step 5. |
| FR-14 | Editor mutations call `store.stageCustom()` (for colour patches) or `store.updateSetting()` (for font/size/spacing/width). |
| FR-15 | When `dirty === true`, editor shows a "Custom theme preview (not saved)" hint above the action row. |
| FR-16 | Save button is enabled iff `dirty === true`; clicking calls `store.saveCustom()` then `store.applyCustom()`. Editor stays open. |
| FR-16b | If Save is invoked while `pendingCustom === null` (defensive — should be unreachable because `dirty === false` disables the button), it is a no-op. `saveCustom()` already implements this guard. |
| FR-17 | Revert button is enabled iff `dirty === true`; clicking calls `store.discardCustom()`. Editor stays open. |
| FR-18 | While `appliedPresetKey !== 'custom'`, the editor never renders even if `editingCustom === true` (impossible state guard; the click handler keeps these in sync). |

### 6.4 Preset immutability

| ID | Requirement |
|----|-------------|
| FR-19 | When `appliedPresetKey` matches `system:*`, no UI control allows mutating `currentSettings.font_family`, `font_size_px`, `line_spacing`, or `content_width_px`. (Today's font/size/spacing/width controls are removed from default state per FR-10.) |
| FR-20 | Switching from Custom to a system preset via FR-07 calls `applyPreset()` which already resets `pendingCustom`, `dirty`, and `editingCustom` to clean state. No additional logic needed. |

### 6.5 Reader chrome

| ID | Requirement |
|----|-------------|
| FR-21 | Chrome toggles row renders at the bottom of the popover in both default and editing states. Contains: "Show highlights inline" checkbox, "Annotations scope" select with options "Current section" / "All sections". |
| FR-22 | Chrome toggle changes are independent of theme/Custom state and persist immediately to `bookcompanion.reader-chrome.v1`. |

### 6.6 Store API changes

| ID | Requirement |
|----|-------------|
| FR-23 | Add `toggleCustomEditor()` action: flips `editingCustom`. Used by Custom card click handler. |
| FR-24 | Modify `applyCustom()` to no longer set `editingCustom`. Editor visibility is the click handler's responsibility. |
| FR-25 | Remove `openCustomPicker()` (split into `applyCustom()` + `toggleCustomEditor()` at call site). |
| FR-26 | Add a watcher on `popoverOpen`: on `false → true` transition, set `editingCustom = false`. Implements D12/FR-09. |
| FR-27 | All other store API (`applyPreset`, `stageCustom`, `saveCustom`, `discardCustom`, `updateSetting`, chrome refs) remains unchanged in signature and semantics. |

### 6.7 Component lifecycle

| ID | Requirement |
|----|-------------|
| FR-28 | Delete `frontend/src/components/settings/PresetCards.vue` and its test file `__tests__/PresetCards.spec.ts`. |
| FR-29 | Delete `frontend/src/components/common/StickySaveBar.vue` (no other consumers per grep verification). |
| FR-30 | `ReaderSettingsPopover.vue` is fully rewritten to host the new theme grid + inline editor. The popover container, header, and chrome toggles row keep their existing styles. |

### 6.8 Popover dismissal

| ID | Requirement |
|----|-------------|
| FR-31 | Pressing the Escape key while the popover is open sets `popoverOpen = false` and returns focus to the gear button that opened it. Keydown listener attached to the popover root (or document while popover is open). |
| FR-32 | Clicking outside the popover and outside the gear button (which toggles open/close) sets `popoverOpen = false`. Implementation: `useEventListener('mousedown', …)` on document; check `!popoverEl.contains(target) && !gearButton.contains(target)`. Esc and outside-click do NOT auto-save pending Custom edits — `pendingCustom` is preserved per E9. |

---

## 7. Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-01 | Performance | Popover open → first paint ≤ 16ms (one frame) on M1 dev hardware. No new network calls vs. today. |
| NFR-02 | Accessibility | Theme grid passes axe-core with zero violations. Active card exposes `aria-pressed="true"`. Roving tabindex per WAI-ARIA radiogroup pattern. ContrastBadge remains for Custom values. |
| NFR-03 | Accessibility | All interactive elements have visible focus indicators (2px outline at 2px offset on focus-visible). |
| NFR-04 | Compatibility | Storage keys (`bookcompanion.reader-applied.v1`, `…-custom.v1`, `…-chrome.v1`) and their value formats remain unchanged. Existing user state is read forward without migration. **Persistence scope:** the Custom slot values (bg/fg/accent) persist to `…-custom.v1` on Save. The `editingCustom` flag (editor expanded/collapsed) is transient in-memory state, reset to `false` on every popover open (FR-09/FR-26), and is never written to localStorage. |
| NFR-05 | i18n | All user-visible strings (theme labels, "Customise", section headers, button labels) use the project's existing literal-string convention; no new i18n framework required. |

---

## 8. API Contracts

No backend API changes. The popover continues to consume:

- `GET /api/v1/reading-presets` (existing, unchanged) — returns the seven shipped presets via `listPresets()` in `src/api/readingPresets.ts`.
- `GET /api/v1/reading-presets/legacy-active-hint` (existing, unchanged) — used by `consumeLegacyActiveHint()`.

The fetch shape, headers, and response schema are unchanged.

---

## 9. Database Design

No DB changes. No migrations. Reading presets continue to be served from the existing presets source.

---

## 10. Frontend Design

### 10.1 Component hierarchy

```
ReaderSettingsPopover.vue (rewritten)
├── PopoverHeader (inline: <h2> + close button)
├── ThemeGrid.vue                     ← NEW
│   └── ThemeCard.vue (×7)            ← NEW
├── CustomEditor.vue                  ← NEW (mounted iff editingCustom)
│   ├── ColorSwatchRow.vue (×2 — bg, fg)  ← NEW (extracted)
│   ├── AccentPicker (inline <input type="color">)
│   ├── FontSelect (inline <select>)
│   ├── Stepper.vue (×3 — size, spacing, width)  ← NEW (extracted)
│   ├── ContrastBadge.vue (existing)
│   ├── LivePreview (inline div)
│   └── EditorActions (inline: hint + Save + Revert)
└── ChromeToggles (inline: highlights checkbox + scope select)
```

`ThemeGrid.vue`, `ThemeCard.vue`, `CustomEditor.vue`, `ColorSwatchRow.vue`, `Stepper.vue` are new files in `frontend/src/components/settings/`.

### 10.2 State management

| State | Lives in | Notes |
|---|---|---|
| `popoverOpen` | `useReaderSettingsStore` | Toggled by gear button in `BookDetailView.vue` (unchanged). |
| `editingCustom` | `useReaderSettingsStore` | Reset to `false` on popover open (D12/FR-26). |
| `appliedPresetKey` | `useReaderSettingsStore` | Source of truth for active card highlighting. |
| `presets`, `currentSettings`, `customTheme`, `pendingCustom`, `dirty` | `useReaderSettingsStore` | Unchanged. |
| Roving tabindex focused index | Local state in `ThemeGrid.vue` | Keyboard nav state; not persisted. |
| `highlightsVisible`, `annotationsScope` | `useReaderSettingsStore` | Unchanged; persists to localStorage. |

### 10.3 UI specifications

**Popover container** (unchanged from today):
- Position: absolute, anchored to gear button via `BookDetailView.vue`.
- Width: 400px. Max-height: 85vh. Overflow-y: auto.
- Border-radius: 0.75rem; box-shadow: 0 8px 30px rgba(0,0,0,0.12).

**Theme grid:**
- `display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem;`
- Each card: 110px–120px wide × 64px tall, padding 0.5rem, border-radius 0.5rem, 2px transparent border (becomes primary on active).
- Card background = preset `bg`; text colour = preset `fg`; "Aa" sample uses preset `fg` at 1.1rem, weight 700.
- Custom (empty slot): linear-gradient(135deg, #f3f4f6 0%, #d1d5db 100%) + label "Custom" + small "Customise" caption.
- Custom (saved slot): bg = saved bg, "Aa" rendered in saved fg.
- Active state: `outline: 2px solid var(--color-primary, #4f46e5); outline-offset: 2px;` and corner `✓` (top-right, primary colour).
- Inert empty grid cells: no border, no background, `pointer-events: none`, `aria-hidden`.

**Inline editor:**
- Top margin 0.75rem from grid; padding 0.75rem; subtle background `#f8fafc`; border-radius 0.5rem.
- Section labels (BACKGROUND, FOREGROUND, ACCENT, FONT, SIZE, LINE SPACING, CONTENT WIDTH, PREVIEW) use the existing `.setting-label` style (caps, 0.75rem, secondary text).
- Swatches: 1.25rem circles, 2px transparent border (primary on active).
- Steppers: existing `.stepper` style (− [value] +).
- Action row: flex, justify-between; "Custom theme preview (not saved)" hint left, [Revert] [Save] buttons right. Buttons disabled when `!dirty`.

**Chrome toggles row:**
- `display: flex; flex-direction: column; gap: 0.35rem;` (unchanged).
- Always rendered last, after editor (or directly after grid in default state).

### 10.4 Animations

- Editor expand/collapse: instant (no animation) for v1. Animation deferred to a follow-up if user feedback demands it.
- Card hover: 100ms border-color transition (existing).

---

## 11. Edge Cases

| # | Scenario | Condition | Expected Behavior |
|---|----------|-----------|-------------------|
| E1 | Preset list fails to load | Network error on `/api/v1/reading-presets` | `store.presets` is `[]`. Theme grid renders only the Custom card (still functional via seeding fallback in `applyCustom()`). Optional: a small "Couldn't load themes" notice above the grid (Open Question Q5). |
| E2 | First-ever Custom click, no presets loaded | `presets === []`, `customTheme === null`, user clicks Custom | `applyCustom()` already warns and no-ops. UI state: editor expands but with default values (Light fallback bg/fg/accent). User can save; slot persists. |
| E3 | Active preset deleted on backend | localStorage points to `system:99` no longer in API response | Existing `loadPresets()` fallback applies first available preset. Active card highlights the fallback. |
| E4 | localStorage quota exceeded | `persistAppliedKey` / `persistCustom` throws DOMException | Existing one-shot toast fires. UI behaviour unchanged. |
| E5 | User switches preset while editor dirty | `editingCustom === true`, `dirty === true`, clicks Sepia | Editor collapses, `pendingCustom` cleared, `dirty = false`, Sepia applies. No confirm dialog. |
| E6 | User toggles editor closed via second Custom click | Custom active, editor open, clicks Custom | Editor collapses; Custom stays active; `pendingCustom` is **preserved** so reopening shows pending edits. (Open Question Q6 — confirm preservation vs. discard.) |
| E7 | Keyboard user tabs into grid | Tab focus reaches grid container | Focus lands on the active card (or Light if none active). Roving tabindex per radiogroup pattern. |
| E8 | Keyboard user activates Custom via Enter | Custom card focused, presses Enter | Same behaviour as click: applies Custom + expands editor. Focus moves to first editor control (background swatch row). |
| E9 | Popover closed while editor dirty | User clicks gear (toggle off) with dirty edits | Popover closes; `pendingCustom` and `dirty` are preserved; reopening shows the editor collapsed (D12) but with pending edits ready when user re-clicks Custom. Edits are NOT applied to the reader (they require Save). |
| E10 | Color picker (accent) opens browser native dialog | `<input type="color">` triggers native UI | Native dialog opens; popover may be visually overlapped by it. Closing the dialog returns focus correctly (browser default). |
| E11 | Empty Custom slot, user clicks Custom, immediately switches to Sepia | First click on Custom seeds slot from active preset; second click on Sepia | Empty slot was *not* persisted (only `applyCustom()` sets `customTheme.value` from `deriveCustomFromPreset()` and `persistCustom()` saves it). Verify: `applyCustom()` does persist on seed. So switching back to Custom later finds the seeded slot. Acceptable. |
| E12 | Reader chrome toggle changed mid-edit | Editor open, dirty; user clicks "Show highlights inline" checkbox | Chrome state persists; editor state untouched (`pendingCustom`, `dirty` preserved). |

---

## 12. Configuration & Feature Flags

None. This is a frontend-only refactor with no rollout staging required. Ship behind the standard release tag.

---

## 13. Testing & Verification Strategy

### 13.1 Unit tests (Vitest) — store

Location: `frontend/src/stores/__tests__/readerSettings.spec.ts` (extend existing).

Cases to add:
- `toggleCustomEditor()` flips `editingCustom`.
- Watcher on `popoverOpen`: open → close → open sequence resets `editingCustom = false` regardless of prior value.
- `applyCustom()` no longer touches `editingCustom` (regression test for D11/FR-24).
- `openCustomPicker()` is removed (test that the export is undefined).
- `applyPreset()` clears `pendingCustom`, `dirty`, `editingCustom` (existing behaviour, add explicit assertions).

### 13.2 Component tests (Vitest + @vue/test-utils) — popover

Location: `frontend/src/components/settings/__tests__/ReaderSettingsPopover.spec.ts` (rewrite).

Cases:
- Renders exactly 7 theme cards in default state, in the order Light → Dark → Sepia → Night → Paper → High Contrast → Custom.
- In default state, no element with class `.custom-editor` or label "Background"/"Foreground"/"Font"/"Size" is rendered.
- Clicking a non-Custom card calls `store.applyPreset` with the matching id; popover stays open.
- Clicking Custom card (Custom not active) calls `applyCustom` then `toggleCustomEditor`; editor renders.
- Clicking Custom card (Custom active, editor open) calls `toggleCustomEditor` only; editor unmounts.
- Switching from Custom to Sepia mid-edit collapses editor and clears pending state.
- Save button disabled when `!dirty`; clicking Save calls `saveCustom` then `applyCustom`.
- Active card has `aria-pressed="true"`; others `aria-pressed="false"`.

New tests (component):
- `ThemeGrid.spec.ts` — keyboard nav: Arrow Right moves focus, Enter activates, roving tabindex correct.
- `ThemeCard.spec.ts` — renders Aa sample with correct fg colour; renders ✓ when active.
- `CustomEditor.spec.ts` — bg swatch click stages patch; Save/Revert disabled state tracks `dirty`.

Delete: `__tests__/PresetCards.spec.ts`.

### 13.3 End-to-end (Playwright MCP)

Manual verification via Playwright MCP per CLAUDE.md "Interactive verification" section. Server on `:8765`, build copied into `backend/app/static`. Steps:

1. Navigate to a section reader URL.
2. Click the gear button → assert popover opens, `scrollHeight ≤ 480` via `browser_evaluate`.
3. Snapshot — assert exactly 7 theme cards and no font/size controls.
4. Click "Sepia" → assert page bg changes; assert popover still open; assert ✓ on Sepia card.
5. Click "Custom" → assert editor expands; assert font/size/spacing/width controls now present.
6. Adjust size to 15 → click Save → assert toast or visual confirmation; reopen popover → assert editor collapsed (D7).
7. Click Custom → assert editor reopens with 15 preserved.
8. Tab keyboard test: Tab into grid, Arrow Right, Enter on Dark → assert applied.
9. Console errors: `browser_console_messages level: 'error'` returns empty.

### 13.4 Visual / a11y

- Run `axe-core` against the popover (via a Vitest+jsdom integration or Playwright `@axe-core/playwright`). Zero violations required.
- Manual contrast check on each preset card's "Aa" sample (existing presets already meet AA; no new colours).

### 13.5 Cleanup verification commands

```bash
cd frontend
# Prove deleted components have no remaining references
! grep -rn "PresetCards" src --include='*.vue' --include='*.ts'
! grep -rn "StickySaveBar" src --include='*.vue' --include='*.ts'
! grep -rn "openCustomPicker" src --include='*.vue' --include='*.ts'

# Lint, type-check, tests
npm run lint
npm run type-check
npm run test:unit -- src/components/settings src/stores
npm run build
```

Each `grep` should return zero matches; each subsequent command should exit 0.

### 13.6 Acceptance script

A short script in the spec sense: open popover on a fresh browser profile, verify (a) 7 cards visible, (b) no font/size controls, (c) clicking Custom expands editor, (d) saving persists across reload, (e) keyboard tab order correct, (f) sticky save bar absent during scroll. Each step checkable in <30s.

---

## 14. Rollout Strategy

Frontend-only change, no flags. Land in a single PR. Pre-merge checklist:

- [ ] Vitest suite green (`npm run test:unit`).
- [ ] Type-check clean (`npm run type-check`).
- [ ] Lint clean (`npm run lint`).
- [ ] Cleanup greps return empty (§13.5).
- [ ] Manual Playwright pass on `localhost:8765` per §13.3.
- [ ] Screenshot before/after attached to PR description.

Rollback: pure git revert; no DB/API to undo.

---

## 15. Research Sources

| Source | Type | Key Takeaway |
|--------|------|-------------|
| `frontend/src/components/settings/ReaderSettingsPopover.vue` | Existing code | Today's dual-grid implementation; reference for what to remove. |
| `frontend/src/components/settings/PresetCards.vue` | Existing code | To be deleted; current `onCustomClick` two-state behaviour is the model we're simplifying. |
| `frontend/src/stores/readerSettings.ts` | Existing code | `appliedPresetKey` state machine + `editingCustom` flag both stay; only `openCustomPicker()` is removed. |
| `frontend/src/components/common/StickySaveBar.vue` | Existing code | Sole consumer is the popover; safe to delete. |
| `frontend/src/views/BookDetailView.vue` (lines 212–221) | Existing code | Popover anchor; gear button toggles `popoverOpen`. No changes needed. |
| Playwright MCP run on 2026-04-30 (screenshots `reader-settings-default.png`, `…-bottom.png`, `…-custom.png`, `…-custom-mid.png`) | Live verification | Confirmed the dual-grid duplication and StickySaveBar overlap that motivated this work. |
| WAI-ARIA Authoring Practices: Radio Group | External | Roving tabindex pattern reference for the new theme grid. |
| `docs/requirements/2026-04-30-reader-settings-popover-consolidation.md` | Requirements | Source of FR mappings; carries D-decisions D7, D8, D2 forward. |

---

## 16. Open Questions

| # | Question | Owner | Needed By |
|---|----------|-------|-----------|
| Q1 | Should we instrument popover open + theme-change events to validate the compact default reduces churn? Carried from requirements Q1. | Maneesh | Before /plan |
| Q2 | If the inline editor opens and the popover would overflow the viewport, do we shrink the editor, scroll inside the popover, or anchor differently? Carried from requirements Q2. | Maneesh | Before /plan |
| Q3 | Custom slot is global (one per device) — confirm staying global. Carried from requirements Q3. | Maneesh | Before /plan |
| Q4 | `ReadingSettings.vue` currently surfaces `summarization.default_preset` + custom CSS. Confirm no font/size fields need migrating out. Carried from requirements Q4. | Maneesh | Before /plan |
| Q5 | E1 — if presets fail to load, do we render an error notice or just the Custom card silently? | Maneesh | Before /plan |
| Q6 | E6 — when the user toggles the editor closed (second click on Custom), should `pendingCustom` be preserved or discarded? Spec currently assumes preserved. | Maneesh | Before /plan |

---

## 17. Review Log

| Loop | Findings | Changes Made |
|------|----------|--------------|
| 1 | (a) Empty grid cells visual behaviour undefined. (b) Save button no-op semantics undefined. (c) Esc-to-close not enforced as FR. (d) Click-outside-to-close not specified. | (a) Added FR-02b — empty cells transparent + inert; (b) Added FR-16b — Save no-op when not dirty; (c) Added FR-31 — Esc closes + restores focus; (d) Added FR-32 — outside click closes, preserves pendingCustom. |
| 2 | (a) Outside-click was a behaviour change vs today — confirmed in scope. (b) Decision Log had two redundant entries (delete StickySaveBar, silent discard) already stated in requirements. (c) Editor-expand focus target unspecified. (d) NFR-04 conflated saved Custom slot persistence with transient `editingCustom` flag. | (a) Kept FR-32 as scoped; (b) Removed D11 (StickySaveBar) and D14 (silent discard); renumbered D12→D11, D13→D12, D15→D13; updated all D-references in FR-26, §10.2, E9, §13.1; (c) Added FR-13b — focus moves to first BACKGROUND swatch on expand, returns to Custom card on collapse; (d) Expanded NFR-04 to distinguish persisted slot data from transient editor visibility. |
