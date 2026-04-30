# Reader Settings Popover Consolidation — Implementation Plan

**Date:** 2026-04-30
**Spec:** `docs/specs/2026-04-30-reader-settings-popover-consolidation-spec.md`
**Requirements:** `docs/requirements/2026-04-30-reader-settings-popover-consolidation.md`

---

## Overview

Frontend-only refactor of the section-reader gear popover. Collapse two redundant theme grids into one `ThemeGrid` component, hide typography/colour/width controls behind an opt-in `CustomEditor` (mounted iff `editingCustom === true`), delete `PresetCards.vue` and `StickySaveBar.vue`, add Esc/outside-click dismissal, add roving-tabindex keyboard nav, and surface a one-line error notice when `/api/v1/reading-presets` fails. No backend, no API, no DB, no migrations.

**Done when:** `frontend/src/components/settings/PresetCards.vue` and `frontend/src/components/common/StickySaveBar.vue` are deleted, `ReaderSettingsPopover.vue` renders exactly seven theme cards in a single grid (default state ≤480px scrollHeight on 1280×800), the inline `CustomEditor` mounts only when Custom is the active preset and editor is toggled open, all store/component Vitest specs pass, type-check + lint clean, and a Playwright MCP walkthrough on `:8765` exercises every user journey from spec §5 with no console errors.

**Execution order:**
```
T1 (red baseline)
   ↓
T2 (store: toggleCustomEditor + watcher + remove openCustomPicker)
   ↓
T3 [P] (ThemeCard.vue)        T4 [P] (Stepper.vue + ColorSwatchRow.vue)
   ↓                              ↓
T5 (ThemeGrid.vue + roving tabindex)
   ↓
T6 (CustomEditor.vue + focus mgmt)
   ↓
T7 (rewrite ReaderSettingsPopover.vue + default-state guard)
   ↓
T8 (Esc + outside-click dismissal)
   ↓
T9 (preset-load-fail notice)
   ↓
T10 (delete PresetCards.vue, StickySaveBar.vue, stale tests)
   ↓
T11 (rewrite component tests; add new specs)
   ↓
T12 (final verification — type-check, build, Playwright MCP, screenshots)
```

---

## Decision Log

> Inherits architecture decisions from spec §4 (D1–D13). Entries below are implementation-specific.

| # | Decision | Options Considered | Rationale |
|---|----------|--------------------|-----------|
| P1 | Outside-click + Esc handlers use native `document.addEventListener('mousedown'/'keydown', …)` with `onScopeDispose` cleanup, no new deps | (a) Add `@vueuse/core` for `useEventListener`/`onClickOutside`. (b) Native listeners + `onScopeDispose`. (c) Move to `AppShell` v-show overlay (per workstream 2026-04-25 decision for command palette). | (b). Two listeners total, popover scope is narrow. `@vueuse/core` adds a dep + bundle for ~20 lines of code. (c) is overkill — popover already mounts inside `BookDetailView` and lifecycle is simple. |
| P2 | Skip `axe-core` programmatic a11y assertion; do manual a11y via Playwright MCP + targeted Vitest unit assertions on `aria-pressed`, `role`, `aria-label`, focus targets | (a) Install `@axe-core/playwright` + add an axe pass in T12. (b) Install `axe-core` for jsdom Vitest run. (c) Manual a11y assertions in component specs + Playwright MCP snapshot review. | (c). Node 20.10 (below 20.12) limits dep upgrades; jsdom-axe coverage is partial; the WAI-ARIA radiogroup pattern's surface is small enough that targeted assertions on `aria-pressed`/roving-tabindex are higher signal than an axe pass. NFR-02 still satisfied via explicit assertions. |
| P3 | Build store changes BEFORE components (T2 first), then leaf components (T3–T4 [P]) before composites (T5–T7) | (a) Components first with stub store. (b) Store first, then leaves, then composites. | (b). Component specs in T11 mock the store; getting store API stable first prevents type-churn churn across multiple component specs. |
| P4 | Keep `CustomThemeSlot.name` field in localStorage payload (always literal `'Custom'`); do NOT migrate the schema | (a) Drop the field, write a one-shot migration to strip it. (b) Keep the field, hold value as constant. | (b). NFR-04 mandates schema stability; the field is harmless and removing it forces a migration sidecar without user benefit. |
| P5 | Inline editor is its own `CustomEditor.vue` component (not inline template in popover) | (a) Inline 80+ lines in popover template. (b) Extract to `CustomEditor.vue`. | (b). Keeps popover under ~120 lines, scopes editor tests, and matches D5 from spec. Stepper + ColorSwatchRow extracted to reduce CustomEditor duplication. |
| P6 | Roving tabindex implemented locally in `ThemeGrid.vue` (no new dep, no shared composable) | (a) Generic `useRovingTabindex` composable. (b) Inline in `ThemeGrid.vue`. | (b). Only one consumer; pre-emptive abstraction adds no value. ~30 lines of focused logic. |
| P7 | Delete `StickySaveBar.vue` after grep verification confirms zero remaining consumers | (a) Mark deprecated, defer deletion. (b) Delete in T10 with grep gate. | (b). Spec FR-29 mandates deletion; deferring leaves dead CSS + tests. |
| P8 | Editor expand → focus first BACKGROUND swatch button via `nextTick` + ref; collapse → focus Custom card via grid imperative method | (a) Use Vue's `Teleport` + native focus trap. (b) `nextTick` + ref-based focus. | (b). Editor is a child of the popover (not a portal); Vue's reactive ref pattern is sufficient and matches spec FR-13b without trap overhead. |
| P9 | Preset-load-fail notice is an inline `<div class="presets-error">` inside `ThemeGrid`; do NOT reuse `PresetsFetchError.vue` | (a) Reuse `PresetsFetchError.vue`. (b) Inline div. | (b). Avoids cross-component test churn (T5 spec asserts `.presets-error`); message is a single sentence with no retry button (presets refresh on next popover open via existing `loadPresets` lifecycle). One source of truth, no branching in T9. |
| P10 | Render whatever `store.presets` returns; do NOT hardcode preset names. Frontend owns display order via a `NAME_ORDER` array and the theme→hex `themeMap` (extracted to a single shared file at `frontend/src/components/settings/themeColors.ts`). | (a) Hardcode 6 system themes (today's pattern in `ReaderSettingsPopover.vue` lines 25-32). (b) Render `store.presets` as-is, sorted by frontend `NAME_ORDER`. | (b). The API is the source of truth for which presets exist; frontend owns the UX-driven display order (spec D3). Eliminates the silent-no-op-on-missing-preset class of bug. `themeMap` stays on frontend because the API doesn't return hex values (Non-Goal per spec §3). |

---

## Code Study Notes

- **Store (`stores/readerSettings.ts`)** — already exposes `popoverOpen`, `editingCustom`, `applyCustom()`, `applyPreset()`, `stageCustom()`, `saveCustom()`, `discardCustom()`, `customTheme`, `pendingCustom`, `dirty`, plus chrome refs. Only API changes needed: add `toggleCustomEditor()`, remove `openCustomPicker()`, add a `popoverOpen` watcher that resets `editingCustom = false` on `false → true`, and ensure `applyCustom()` no longer touches `editingCustom`. (Today's `applyCustom()` does NOT touch `editingCustom` — confirmed by reading lines 256-298. Only `openCustomPicker()` touches it. So removing `openCustomPicker()` automatically satisfies FR-24.)
- **`PresetCards.vue`** — current dual-affordance "card click + pencil" model; sole responsibility is to be deleted.
- **`ReaderSettingsPopover.vue`** — 430 lines today, mixes 6-card theme picker, custom-editor swatches, font/size/spacing/width steppers, chrome toggles, live preview, and `<StickySaveBar>` consumer. Will be reduced to ~120 lines orchestrating extracted components.
- **`StickySaveBar.vue`** — sole consumer is `ReaderSettingsPopover.vue` (verified via grep). Safe to delete.
- **`BookDetailView.vue:215-220`** — gear button toggles `store.popoverOpen`; popover anchor unchanged. The `popoverOpen` watcher in T2 will fire on every gear-click open, satisfying FR-09/FR-26.
- **`ContrastBadge.vue`** — existing 54-line component, takes `:fg`/`:bg` props. Unchanged.
- **`ReadingSettings.vue`** — confirmed only owns `summarization.default_preset` + `customCss`. Q4 audit passes — no fields to migrate.
- **Test infra** — Vitest 2.1.4, @vue/test-utils 2.4.6, Playwright 1.59.1. Node 20.10. No `@vueuse/core`, no `axe-core`. Plan must not add deps that require Node ≥ 20.12 (per workstream learnings).
- **Existing tests that conflict with new behaviour:**
  - `stores/__tests__/readerSettings.spec.ts:194-204` — tests `openCustomPicker`. Must be replaced by `toggleCustomEditor` + watcher tests.
  - `components/settings/__tests__/PresetCards.spec.ts` — entire file deleted in T10.
  - `components/settings/__tests__/ReaderSettingsPopover.spec.ts` — current assertions ("does not render `.theme-card.custom`") contradict the new design (Custom IS in the grid as the 7th card). Rewrite in T11.
- **No existing data-flow pipeline crosses backend/frontend** — purely UI presentation. Skip the trace.

---

## Prerequisites

- Branch off `main`. Suggested branch name: `feat/reader-settings-popover-consolidation`.
- `frontend/` working dir for all `npm` commands.
- For T12 Playwright MCP: backend running on `:8765` with a seeded book; frontend built into `backend/app/static/` per CLAUDE.md "Interactive verification".

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `frontend/src/stores/readerSettings.ts` | Add `toggleCustomEditor()`; add `popoverOpen` watcher (resets `editingCustom`); remove `openCustomPicker()`. |
| Create | `frontend/src/components/settings/ThemeCard.vue` | Single theme card: live bg/fg colour, "Aa" sample, label, ✓ + 2px outline when active, `role="radio"`, `aria-pressed`. |
| Create | `frontend/src/components/settings/ThemeGrid.vue` | 7-card grid (Light → Dark → Sepia → Night → Paper → High Contrast → Custom). Roving tabindex, arrow-key navigation, Enter/Space activation, click handlers wired to `applyPreset`/`applyCustom`+`toggleCustomEditor`. Two empty grid cells in row 3 are inert/aria-hidden. Exposes `focusActiveCard()` imperative method via `defineExpose`. |
| Create | `frontend/src/components/settings/Stepper.vue` | Reusable − [value] + stepper. Props: `modelValue`, `step`, `format`, `aria-label`. Emits `update:modelValue`. |
| Create | `frontend/src/components/settings/ColorSwatchRow.vue` | Reusable swatch row. Props: `palette`, `modelValue`, `aria-label-prefix`. Emits `update:modelValue`. |
| Create | `frontend/src/components/settings/CustomEditor.vue` | Inline editor: BACKGROUND/FOREGROUND swatch rows, ACCENT picker, FONT select, SIZE/LINE SPACING/CONTENT WIDTH steppers, ContrastBadge, live preview, dirty hint, Save/Revert buttons. On mount, focuses first bg swatch. Emits `requestCollapse` so the parent can toggle the editor closed and refocus the Custom card. |
| Modify | `frontend/src/components/settings/ReaderSettingsPopover.vue` | Full rewrite: header + ThemeGrid + (CustomEditor v-if editingCustom) + chrome toggles. Wires Esc + outside-click. ~120 lines. |
| Delete | `frontend/src/components/settings/PresetCards.vue` | Replaced by ThemeGrid. |
| Delete | `frontend/src/components/common/StickySaveBar.vue` | Save/Revert moved into CustomEditor. |
| Modify | `frontend/src/stores/__tests__/readerSettings.spec.ts` | Drop `openCustomPicker` test; add `toggleCustomEditor` + popoverOpen-watcher tests; assert `applyCustom()` does not touch `editingCustom`. |
| Delete | `frontend/src/components/settings/__tests__/PresetCards.spec.ts` | Component is gone. |
| Modify | `frontend/src/components/settings/__tests__/ReaderSettingsPopover.spec.ts` | Full rewrite to match new structure (7 cards, Custom in grid, chrome toggles always visible, no font/size in default state). |
| Create | `frontend/src/components/settings/__tests__/ThemeGrid.spec.ts` | Card count + order, click → applyPreset, Custom click → applyCustom + toggleCustomEditor, arrow-key navigation, Enter activation, aria-pressed. |
| Create | `frontend/src/components/settings/__tests__/ThemeCard.spec.ts` | Renders bg/fg colour from props, renders ✓ when active, aria-pressed reflects active. |
| Create | `frontend/src/components/settings/__tests__/CustomEditor.spec.ts` | Bg swatch click stages patch; Save disabled when not dirty; Save calls saveCustom + applyCustom; Revert calls discardCustom; first-bg-swatch focused on mount. |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Outside-click handler fires when interacting with native `<input type="color">` color picker dialog (E10) | Medium | Color picker opens a browser-managed dialog; the click happens on the popover's own `<input>` element which is inside `popoverEl`, so `popoverEl.contains(target)` returns true. Guard logic: also exclude clicks on elements with `role="dialog"` outside the popover (defensive). Verified in T8 inline test. |
| Roving tabindex breaks when grid container loses focus mid-key-press | Low | Standard pattern: store `focusedIndex` in component state; on focus-leave, do nothing (next focus-enter restores focus to active card per WAI-ARIA). Vitest spec covers this. |
| Vitest jsdom does not implement `Element.focus()` reliably for assertions | Low | Use `vi.spyOn(el, 'focus')` rather than asserting `document.activeElement === el`. Pattern already used in repo. |
| Existing `customTheme.name` schema reads from localStorage might break if a future writer drops the field | Low | Loader at `loadCustom()` already coerces missing `name` to `'Custom'`. Plan does not change this code path. |
| Bundle size increase from extracted components | Negligible | All new components are <120 lines; total LOC across new files is less than the deleted `PresetCards.vue` + `StickySaveBar.vue` + the deleted lines from `ReaderSettingsPopover.vue`. Confirm via `npm run build` size check in T12. |

---

## Tasks

### T1: Baseline — capture current behaviour and run the suite

**Goal:** Establish a known-good state on `main` before any changes; record current popover render so the design diff in PR review is unambiguous.
**Spec refs:** None (process gate).

**Files:**
- Read-only.

**Steps:**

- [ ] Confirm clean working tree
  Run: `git status -s`
  Expected: empty (or only the requirements/spec docs untracked).

- [ ] Run the full frontend test suite as the regression baseline
  Run: `cd frontend && npm run test:unit -- --run`
  Expected: PASS, capture pass count to compare against T11 / T12.

- [ ] Run lint and type-check baseline
  Run: `cd frontend && npm run lint && npm run type-check`
  Expected: both exit 0. If pre-existing failures exist, capture them so T12 can scope its assertions to "no new failures vs. baseline".

- [ ] Capture before-state screenshot of the popover (manual)
  Open `localhost:5173` → book → gear → take a screenshot. Save as `reader-settings-before.png` in repo root (already in git status from prior session as `reader-settings-default.png`/etc — ensure they exist; if missing, capture now).
  Expected: at least one before-state screenshot exists.

**Inline verification:**
- `npm run test:unit -- --run` — N passes, 0 failures (record N).
- `npm run lint` — exit 0 or pre-existing baseline noted.

**Commit:** No commit (read-only baseline).

---

### T2: Store changes — add `toggleCustomEditor`, watcher, remove `openCustomPicker`

**Goal:** Land all `useReaderSettingsStore` API changes in one task with TDD, before any component touches the store.
**Spec refs:** FR-09, FR-23, FR-24, FR-25, FR-26, D11, D12.

**Files:**
- Modify: `frontend/src/stores/readerSettings.ts`
- Modify: `frontend/src/stores/__tests__/readerSettings.spec.ts`

**Steps:**

- [ ] Step 1: Write the failing tests — replace existing `openCustomPicker` test (line 194) with three new tests
  Edit `frontend/src/stores/__tests__/readerSettings.spec.ts`:
  - Delete the existing `it('openCustomPicker opens popover, sets editingCustom, and applies Custom', ...)` test.
  - Add:
    ```ts
    it('toggleCustomEditor flips editingCustom', async () => {
      mockListPresets(); mockHintNull()
      const s = useReaderSettingsStore()
      await s.loadPresets()
      expect(s.editingCustom).toBe(false)
      s.toggleCustomEditor()
      expect(s.editingCustom).toBe(true)
      s.toggleCustomEditor()
      expect(s.editingCustom).toBe(false)
    })

    it('opening the popover resets editingCustom to false', async () => {
      mockListPresets(); mockHintNull()
      const s = useReaderSettingsStore()
      await s.loadPresets()
      s.editingCustom = true
      s.popoverOpen = false
      // simulate a fresh open
      s.popoverOpen = true
      await Promise.resolve()
      expect(s.editingCustom).toBe(false)
    })

    it('applyCustom() does not mutate editingCustom (regression for D11/FR-24)', async () => {
      mockListPresets(); mockHintNull()
      const s = useReaderSettingsStore()
      await s.loadPresets()
      s.applyPreset(1)
      s.editingCustom = false
      s.applyCustom()
      expect(s.editingCustom).toBe(false)
      s.editingCustom = true
      s.applyCustom()
      expect(s.editingCustom).toBe(true)
    })

    it('openCustomPicker is no longer exported', async () => {
      const s = useReaderSettingsStore()
      // @ts-expect-error - removed API
      expect(s.openCustomPicker).toBeUndefined()
    })
    ```

- [ ] Step 2: Run tests, verify red
  Run: `cd frontend && npm run test:unit -- --run src/stores/__tests__/readerSettings.spec.ts`
  Expected: 4 new tests fail (`toggleCustomEditor is not a function`, watcher absent, `openCustomPicker` still defined).

- [ ] Step 3: Implement store changes in `frontend/src/stores/readerSettings.ts`:
  - Inside `defineStore` setup function, after the existing `watch([highlightsVisible, annotationsScope], …)`, add a watcher:
    ```ts
    watch(popoverOpen, (open, wasOpen) => {
      if (open && !wasOpen) editingCustom.value = false
    })
    ```
  - Add a new function near `applyCustom`:
    ```ts
    function toggleCustomEditor() {
      editingCustom.value = !editingCustom.value
    }
    ```
  - Delete the entire `openCustomPicker` function (lines 300-305).
  - In the `return { … }` block at the bottom: replace `openCustomPicker` with `toggleCustomEditor`.

- [ ] Step 4: Run targeted tests, verify green
  Run: `cd frontend && npm run test:unit -- --run src/stores/__tests__/readerSettings.spec.ts`
  Expected: all tests in the file PASS (including legacy ones that don't touch the changes).

- [ ] Step 5: Type-check
  Run: `cd frontend && npm run type-check`
  Expected: exit 0. (Note: `PresetCards.vue` still references `openCustomPicker` and will fail type-check — that is EXPECTED at this point; record the failure scope and proceed; T7/T10 fix the call sites. If the failure is broader, stop and investigate.)

- [ ] Step 6: Commit
  ```bash
  git add frontend/src/stores/readerSettings.ts frontend/src/stores/__tests__/readerSettings.spec.ts
  git commit -m "feat(reader-settings): add toggleCustomEditor, popoverOpen watcher, remove openCustomPicker"
  ```

**Inline verification:**
- `npm run test:unit -- --run src/stores/__tests__/readerSettings.spec.ts` — all PASS.
- `grep -n "openCustomPicker" src/stores/readerSettings.ts` — zero matches.
- `grep -n "toggleCustomEditor" src/stores/readerSettings.ts` — at least 2 matches (function def + return).
- **FR-27 regression:** confirm existing tests for `applyPreset`, `stageCustom`, `saveCustom`, `discardCustom`, `updateSetting`, `loadPresets`, chrome refs all still PASS unchanged in this run — their signatures and semantics must not have moved. Re-run `npm run test:unit -- --run src/stores/__tests__/readerSettings.spec.ts` and visually confirm those test names appear in the green list.

---

### T3 [P]: New component — `ThemeCard.vue`

**Goal:** Single reusable theme-card component; foundation for the new grid.
**Spec refs:** FR-03, FR-04, FR-05, FR-06.

**Files:**
- Create: `frontend/src/components/settings/ThemeCard.vue`
- Create: `frontend/src/components/settings/__tests__/ThemeCard.spec.ts`

**Steps:**

- [ ] Step 1: Write failing test
  Create `frontend/src/components/settings/__tests__/ThemeCard.spec.ts`:
  ```ts
  import { mount } from '@vue/test-utils'
  import { describe, it, expect } from 'vitest'
  import ThemeCard from '../ThemeCard.vue'

  describe('ThemeCard', () => {
    it('renders bg as background and fg as text colour', () => {
      const w = mount(ThemeCard, {
        props: { label: 'Sepia', bg: '#f4ecd8', fg: '#3a2f1d', active: false },
      })
      const el = w.get('button')
      expect(el.attributes('style')).toContain('background')
      expect(el.text()).toContain('Sepia')
      expect(el.text()).toContain('Aa')
    })

    it('shows ✓ glyph and aria-pressed=true when active', () => {
      const w = mount(ThemeCard, {
        props: { label: 'Light', bg: '#fff', fg: '#111', active: true },
      })
      expect(w.text()).toContain('✓')
      expect(w.get('button').attributes('aria-pressed')).toBe('true')
    })

    it('aria-pressed=false when inactive', () => {
      const w = mount(ThemeCard, {
        props: { label: 'Light', bg: '#fff', fg: '#111', active: false },
      })
      expect(w.get('button').attributes('aria-pressed')).toBe('false')
      expect(w.text()).not.toContain('✓')
    })

    it('emits click when clicked', async () => {
      const w = mount(ThemeCard, {
        props: { label: 'Light', bg: '#fff', fg: '#111', active: false },
      })
      await w.get('button').trigger('click')
      expect(w.emitted('click')).toBeTruthy()
    })

    it('honours tabindex prop for roving-tabindex pattern', () => {
      const w = mount(ThemeCard, {
        props: { label: 'Light', bg: '#fff', fg: '#111', active: false, tabindex: -1 },
      })
      expect(w.get('button').attributes('tabindex')).toBe('-1')
    })
  })
  ```

- [ ] Step 2: Verify red
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ThemeCard.spec.ts`
  Expected: FAIL — file does not exist.

- [ ] Step 3: Implement `ThemeCard.vue`
  Create `frontend/src/components/settings/ThemeCard.vue` with:
  - Props: `label: string`, `bg: string`, `fg: string`, `active: boolean`, `tabindex?: number` (default 0), `emptyCustom?: boolean` (default false).
  - Template: a `<button type="button" role="radio" :aria-pressed="active" :aria-label="`${label} theme`" :tabindex="tabindex">` containing a span for label, a span for "Aa" (or the literal "Customise" if `emptyCustom`), and a `<span class="card-check" v-if="active">✓</span>`.
  - Style: card uses `bg` as background, `fg` as text colour; active state uses `outline: 2px solid var(--color-primary, #4f46e5); outline-offset: 2px;`. Empty-Custom variant uses a linear-gradient instead of solid bg.
  - Emits: `click` (forwarded from native button).

- [ ] Step 4: Verify green
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ThemeCard.spec.ts`
  Expected: 5/5 PASS.

- [ ] Step 5: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/ThemeCard.vue src/components/settings/__tests__/ThemeCard.spec.ts
  git commit -m "feat(reader-settings): add ThemeCard component"
  ```

**Inline verification:**
- 5 tests pass.
- `npm run lint` exits 0.

---

### T4 [P]: New leaf components — `Stepper.vue` and `ColorSwatchRow.vue`

**Goal:** Extract reusable bits used by `CustomEditor`. Independent of T3, can run in parallel.
**Spec refs:** FR-13 (size, line-spacing, content-width steppers; bg/fg swatch rows).

**Files:**
- Create: `frontend/src/components/settings/Stepper.vue`
- Create: `frontend/src/components/settings/ColorSwatchRow.vue`
- Create: `frontend/src/components/settings/__tests__/Stepper.spec.ts`
- Create: `frontend/src/components/settings/__tests__/ColorSwatchRow.spec.ts`

**Steps:**

- [ ] Step 1: Stepper failing test
  Create `Stepper.spec.ts`:
  ```ts
  import { mount } from '@vue/test-utils'
  import { describe, it, expect } from 'vitest'
  import Stepper from '../Stepper.vue'

  describe('Stepper', () => {
    it('renders − [value] + and emits update on click', async () => {
      const w = mount(Stepper, {
        props: { modelValue: 16, step: 1, format: (v: number) => `${v}px`, ariaLabel: 'Size' },
      })
      expect(w.text()).toContain('16px')
      const buttons = w.findAll('button')
      await buttons[1].trigger('click') // +
      expect(w.emitted('update:modelValue')![0]).toEqual([17])
      await buttons[0].trigger('click') // −
      expect(w.emitted('update:modelValue')![1]).toEqual([15])
    })

    it('respects custom step size for fractional values', async () => {
      const w = mount(Stepper, {
        props: { modelValue: 1.6, step: 0.1, format: (v: number) => v.toFixed(1), ariaLabel: 'Spacing' },
      })
      await w.findAll('button')[1].trigger('click')
      const emitted = w.emitted('update:modelValue')![0][0] as number
      expect(emitted).toBeCloseTo(1.7, 5)
    })
  })
  ```

- [ ] Step 2: ColorSwatchRow failing test
  Create `ColorSwatchRow.spec.ts`:
  ```ts
  import { mount } from '@vue/test-utils'
  import { describe, it, expect } from 'vitest'
  import ColorSwatchRow from '../ColorSwatchRow.vue'

  describe('ColorSwatchRow', () => {
    it('renders one button per palette colour and marks the active one', () => {
      const w = mount(ColorSwatchRow, {
        props: { palette: ['#fff', '#000', '#abc'], modelValue: '#000', ariaLabelPrefix: 'Background' },
      })
      const buttons = w.findAll('button')
      expect(buttons).toHaveLength(3)
      expect(buttons[1].classes()).toContain('active')
      expect(buttons[0].classes()).not.toContain('active')
    })

    it('emits update:modelValue on swatch click', async () => {
      const w = mount(ColorSwatchRow, {
        props: { palette: ['#fff', '#000'], modelValue: '#fff', ariaLabelPrefix: 'Foreground' },
      })
      await w.findAll('button')[1].trigger('click')
      expect(w.emitted('update:modelValue')![0]).toEqual(['#000'])
    })

    it('aria-label uses prefix + colour', () => {
      const w = mount(ColorSwatchRow, {
        props: { palette: ['#fff'], modelValue: '#fff', ariaLabelPrefix: 'Background' },
      })
      expect(w.get('button').attributes('aria-label')).toBe('Background #fff')
    })
  })
  ```

- [ ] Step 3: Verify red (both)
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/Stepper.spec.ts src/components/settings/__tests__/ColorSwatchRow.spec.ts`
  Expected: FAIL (files do not exist).

- [ ] Step 4: Implement `Stepper.vue`
  - Props: `modelValue: number`, `step: number`, `format: (v: number) => string`, `ariaLabel: string`.
  - Template: a flex row with `<button type="button" :aria-label="`Decrease ${ariaLabel}`" @click="emit('update:modelValue', modelValue - step)">−</button>`, `<span>{{ format(modelValue) }}</span>`, `<button … @click="emit('update:modelValue', modelValue + step)">+</button>`.
  - Style: reuse `.stepper` class pattern from current popover (port the CSS).

- [ ] Step 5: Implement `ColorSwatchRow.vue`
  - Props: `palette: string[]`, `modelValue: string`, `ariaLabelPrefix: string`.
  - Template: `<div class="swatch-row">` with `<button v-for="c in palette" :class="{active: modelValue === c}" :aria-label="`${ariaLabelPrefix} ${c}`" :style="{background: c}" @click="emit('update:modelValue', c)" />`.
  - Style: ported `.swatch-row` and `.swatch` CSS from current popover.

- [ ] Step 6: Verify green (both)
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/Stepper.spec.ts src/components/settings/__tests__/ColorSwatchRow.spec.ts`
  Expected: all PASS.

- [ ] Step 7: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/Stepper.vue src/components/settings/ColorSwatchRow.vue \
          src/components/settings/__tests__/Stepper.spec.ts \
          src/components/settings/__tests__/ColorSwatchRow.spec.ts
  git commit -m "feat(reader-settings): add Stepper and ColorSwatchRow components"
  ```

**Inline verification:**
- 5 tests pass total (2 Stepper + 3 ColorSwatchRow).
- `npm run lint` exits 0.

---

### T5: New component — `ThemeGrid.vue` (with roving tabindex)

**Goal:** Compose seven `ThemeCard`s with WAI-ARIA radiogroup keyboard nav.
**Spec refs:** FR-01, FR-02, FR-02b, FR-06, FR-07, FR-08, NFR-02, D2, D13.

**Files:**
- Create: `frontend/src/components/settings/ThemeGrid.vue`
- Create: `frontend/src/components/settings/__tests__/ThemeGrid.spec.ts`

**Steps:**

- [ ] Step 1: Failing test
  Create `ThemeGrid.spec.ts`:
  ```ts
  import { mount } from '@vue/test-utils'
  import { setActivePinia, createPinia } from 'pinia'
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import ThemeGrid from '../ThemeGrid.vue'
  import { useReaderSettingsStore } from '@/stores/readerSettings'

  const PRESETS = [
    { id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' },
    { id: 2, name: 'Dark', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'dark', created_at: '' },
    { id: 3, name: 'Sepia', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'sepia', created_at: '' },
    { id: 4, name: 'Night', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'night', created_at: '' },
    { id: 5, name: 'Paper', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'paper', created_at: '' },
    { id: 6, name: 'High Contrast', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'contrast', created_at: '' },
  ]

  describe('ThemeGrid', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('renders 7 cards in spec order: Light, Dark, Sepia, Night, Paper, High Contrast, Custom', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      const w = mount(ThemeGrid)
      const labels = w.findAllComponents({ name: 'ThemeCard' }).map(c => c.props('label'))
      expect(labels).toEqual(['Light', 'Dark', 'Sepia', 'Night', 'Paper', 'High Contrast', 'Custom'])
    })

    it('grid has role=radiogroup with aria-label', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      const w = mount(ThemeGrid)
      const grid = w.get('[role="radiogroup"]')
      expect(grid.attributes('aria-label')).toMatch(/theme/i)
    })

    it('clicking Sepia card calls applyPreset(3)', async () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      const spy = vi.spyOn(s, 'applyPreset').mockImplementation(() => {})
      const w = mount(ThemeGrid)
      const sepia = w.findAllComponents({ name: 'ThemeCard' }).find(c => c.props('label') === 'Sepia')!
      await sepia.trigger('click')
      expect(spy).toHaveBeenCalledWith(3)
    })

    it('clicking Custom card (when not active) calls applyCustom + toggleCustomEditor', async () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      const applyCustomSpy = vi.spyOn(s, 'applyCustom').mockImplementation(() => {})
      const toggleSpy = vi.spyOn(s, 'toggleCustomEditor').mockImplementation(() => {})
      const w = mount(ThemeGrid)
      const custom = w.findAllComponents({ name: 'ThemeCard' }).find(c => c.props('label') === 'Custom')!
      await custom.trigger('click')
      expect(applyCustomSpy).toHaveBeenCalled()
      expect(toggleSpy).toHaveBeenCalled()
    })

    it('clicking Custom (already active) calls toggleCustomEditor only', async () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      s.appliedPresetKey = 'custom'
      const applyCustomSpy = vi.spyOn(s, 'applyCustom').mockImplementation(() => {})
      const toggleSpy = vi.spyOn(s, 'toggleCustomEditor').mockImplementation(() => {})
      const w = mount(ThemeGrid)
      const custom = w.findAllComponents({ name: 'ThemeCard' }).find(c => c.props('label') === 'Custom')!
      await custom.trigger('click')
      expect(applyCustomSpy).not.toHaveBeenCalled()
      expect(toggleSpy).toHaveBeenCalled()
    })

    it('arrow-right moves focus to next card', async () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      s.appliedPresetKey = 'system:1'
      const w = mount(ThemeGrid, { attachTo: document.body })
      const cards = w.findAll('button[role="radio"]')
      // Light is active (focusedIndex=0); press ArrowRight.
      await cards[0].trigger('keydown', { key: 'ArrowRight' })
      // The new focused card (Dark) should now have tabindex=0; others -1.
      expect(cards[1].attributes('tabindex')).toBe('0')
      expect(cards[0].attributes('tabindex')).toBe('-1')
      w.unmount()
    })

    it('arrow-right wraps from Custom (last) back to Light (first)', async () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      s.appliedPresetKey = 'custom'
      const w = mount(ThemeGrid, { attachTo: document.body })
      const cards = w.findAll('button[role="radio"]')
      await cards[6].trigger('keydown', { key: 'ArrowRight' })
      expect(cards[0].attributes('tabindex')).toBe('0')
      w.unmount()
    })

    it('Enter key on focused card activates it', async () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      const spy = vi.spyOn(s, 'applyPreset').mockImplementation(() => {})
      const w = mount(ThemeGrid)
      const cards = w.findAll('button[role="radio"]')
      await cards[2].trigger('keydown', { key: 'Enter' })  // Sepia (idx 2)
      expect(spy).toHaveBeenCalledWith(3)
    })

    it('renders empty grid cells (FR-02b) as inert and aria-hidden', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never
      const w = mount(ThemeGrid)
      const empties = w.findAll('.empty-cell')
      expect(empties.length).toBe(2)
      empties.forEach(e => {
        expect(e.attributes('aria-hidden')).toBe('true')
        expect((e.element as HTMLElement).style.pointerEvents).toBe('none')
      })
    })

    it('shows error notice when presets is empty (E1 / Q5)', () => {
      const s = useReaderSettingsStore(); s.presets = [] as never
      const w = mount(ThemeGrid)
      expect(w.find('.presets-error').exists()).toBe(true)
      // Custom card still rendered
      const labels = w.findAllComponents({ name: 'ThemeCard' }).map(c => c.props('label'))
      expect(labels).toEqual(['Custom'])
    })
  })
  ```

- [ ] Step 2: Verify red
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ThemeGrid.spec.ts`
  Expected: FAIL — file does not exist.

- [ ] Step 3: Implement `ThemeGrid.vue`
  - Imports: `ThemeCard`, `useReaderSettingsStore`, `ref`, `computed`, `watch`, `nextTick`.
  - Render whatever `store.presets` returns; do NOT hardcode the preset list. The API is the source of truth for which presets exist.
  - For ordering, use a frontend-defined display sort (D3 is a UX decision, not a backend concern):
    ```ts
    const NAME_ORDER = ['Light','Dark','Sepia','Night','Paper','High Contrast']
    function rank(name: string) { const i = NAME_ORDER.indexOf(name); return i === -1 ? 999 : i }
    ```
  - For card colours, use a frontend `themeMap` keyed by `preset.theme` (the API returns `theme: 'light' | 'sepia' | ...` without hex; the existing `deriveCustomFromPreset` in the store already has this map — extract to a shared `frontend/src/components/settings/themeColors.ts` and re-import in both store and ThemeGrid; **a single source of truth**). Default colours for an unknown `theme` value: `{bg:'#ffffff', fg:'#111827', accent:'#4f46e5'}` (Light).
  - Build a computed `cards` array:
    ```ts
    const systemCards = computed(() =>
      [...store.presets]
        .sort((a,b) => rank(a.name) - rank(b.name))
        .map(p => {
          const c = themeMap[p.theme] ?? themeMap.light
          return { key: `system:${p.id}`, label: p.name, bg: c.bg, fg: c.fg, presetId: p.id, type: 'system' as const }
        })
    )
    const customCard = computed(() => ({
      key: 'custom',
      label: 'Custom',
      bg: store.customTheme?.bg ?? null,
      fg: store.customTheme?.fg ?? null,
      type: 'custom' as const,
      empty: !store.customTheme,
    }))
    const cards = computed(() => [...systemCards.value, customCard.value])
    ```
  - Layout: 3-column CSS grid; render `cards.value.length` cards, then pad with `<div class="empty-cell" aria-hidden="true" style="pointer-events:none" />` so the last row is filled to a multiple of 3. With 6 system + Custom = 7 cards, that yields 2 empty cells in row 3 (matches FR-02b). With fewer presets (e.g. 4), 0 empty cells if 4+1=5 leaves 1 empty cell in row 2; trivial CSS.
  - Build a computed `activeIndex` based on `appliedPresetKey`.
  - Local `focusedIndex` ref, initialised to `activeIndex.value ?? 0`.
  - Click handler:
    ```ts
    function onCardClick(idx: number) {
      const c = cards.value[idx]
      if (c.type === 'system') store.applyPreset(c.presetId)
      else { // custom
        if (store.appliedPresetKey !== 'custom') store.applyCustom()
        store.toggleCustomEditor()
      }
    }
    ```
  - Keydown handler on each card:
    - `ArrowRight`/`ArrowDown`: `focusedIndex = (focusedIndex+1) % 7; nextTick(focus card)`
    - `ArrowLeft`/`ArrowUp`: `(focusedIndex-1+7) % 7`
    - `Enter` or `Space`: call `onCardClick(focusedIndex)`; preventDefault for Space.
    - `Home`: 0; `End`: 6.
  - Render: `<div role="radiogroup" aria-label="Reader theme" class="theme-grid">` containing 7 `<ThemeCard>` plus 2 `<div class="empty-cell" aria-hidden="true" style="pointer-events:none" />` slotted into row 3 (cells 8 and 9). Each ThemeCard receives `tabindex = (idx === focusedIndex ? 0 : -1)`.
  - Above the grid (or in place of it when empty): `<div v-if="store.presets.length === 0" class="presets-error">Couldn't load themes.</div>` and render only the Custom card.
  - `defineExpose({ focusActiveCard() { /* sync focusedIndex = activeIndex.value first, then nextTick → query the card whose tabindex=0 → .focus(); this guarantees subsequent arrow-key nav starts from the active card per the WAI-ARIA roving-tabindex pattern */ } })`.

  **Note on the existing `themeMap` duplication:** `frontend/src/stores/readerSettings.ts` lines 144-155 already have a `themeMap` inside `deriveCustomFromPreset`. Extract it to `frontend/src/components/settings/themeColors.ts` (one file, named export `themeMap`) and re-import in both the store and `ThemeGrid.vue`. This is a small, safe refactor that prevents the two copies from drifting. Confirm via grep that there's exactly one `themeMap` definition after the change.

- [ ] Step 4: Verify green
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ThemeGrid.spec.ts`
  Expected: 10/10 PASS.

- [ ] Step 5: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/ThemeGrid.vue src/components/settings/__tests__/ThemeGrid.spec.ts
  git commit -m "feat(reader-settings): add ThemeGrid with roving tabindex and error notice"
  ```

**Inline verification:**
- 10 tests pass, including roving-tabindex and Custom-active behaviour.
- Lint exit 0.

---

### T6: New component — `CustomEditor.vue`

**Goal:** Inline editor block. Mounts only when parent renders it. Owns Save/Revert buttons. Focuses first BG swatch on mount; emits `requestCollapse` when user wants editor closed (e.g. nothing here yet — collapse is parent-driven).
**Spec refs:** FR-12, FR-13, FR-13b, FR-14, FR-15, FR-16, FR-16b, FR-17, FR-18, FR-19, NFR-02, NFR-03, D5, D8, P8.

**Files:**
- Create: `frontend/src/components/settings/CustomEditor.vue`
- Create: `frontend/src/components/settings/__tests__/CustomEditor.spec.ts`

**Steps:**

- [ ] Step 1: Failing test
  ```ts
  import { mount } from '@vue/test-utils'
  import { setActivePinia, createPinia } from 'pinia'
  import { describe, it, expect, beforeEach, vi, nextTick } from 'vitest'
  import CustomEditor from '../CustomEditor.vue'
  import { useReaderSettingsStore } from '@/stores/readerSettings'

  describe('CustomEditor', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('clicking a bg swatch calls store.stageCustom with new bg', async () => {
      const s = useReaderSettingsStore()
      s.customTheme = { name: 'Custom', bg: '#ffffff', fg: '#111827', accent: '#4f46e5' }
      const stageSpy = vi.spyOn(s, 'stageCustom')
      const w = mount(CustomEditor)
      const bgRow = w.findAllComponents({ name: 'ColorSwatchRow' })[0]
      bgRow.vm.$emit('update:modelValue', '#000000')
      await nextTick()
      expect(stageSpy).toHaveBeenCalledWith(expect.objectContaining({ bg: '#000000' }))
    })

    it('Save button disabled when not dirty', () => {
      const s = useReaderSettingsStore()
      s.dirty = false
      const w = mount(CustomEditor)
      const save = w.findAll('button').find(b => /save/i.test(b.text()))!
      expect(save.attributes('disabled')).toBeDefined()
    })

    it('Save button enabled and calls saveCustom + applyCustom when dirty', async () => {
      const s = useReaderSettingsStore()
      s.customTheme = { name: 'Custom', bg: '#fff', fg: '#111', accent: '#4f46e5' }
      s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#4f46e5' }
      s.dirty = true
      const saveSpy = vi.spyOn(s, 'saveCustom')
      const applySpy = vi.spyOn(s, 'applyCustom').mockImplementation(() => {})
      const w = mount(CustomEditor)
      const save = w.findAll('button').find(b => /save/i.test(b.text()))!
      expect(save.attributes('disabled')).toBeUndefined()
      await save.trigger('click')
      expect(saveSpy).toHaveBeenCalled()
      expect(applySpy).toHaveBeenCalled()
    })

    it('Revert button calls discardCustom', async () => {
      const s = useReaderSettingsStore()
      s.dirty = true
      s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#4f46e5' }
      const discardSpy = vi.spyOn(s, 'discardCustom')
      const w = mount(CustomEditor)
      const revert = w.findAll('button').find(b => /revert/i.test(b.text()))!
      await revert.trigger('click')
      expect(discardSpy).toHaveBeenCalled()
    })

    it('shows dirty hint only when dirty', async () => {
      const s = useReaderSettingsStore()
      s.dirty = false
      const w = mount(CustomEditor)
      expect(w.text()).not.toMatch(/not saved/i)
      s.dirty = true
      await nextTick()
      expect(w.text()).toMatch(/not saved/i)
    })

    it('focuses first BACKGROUND swatch on mount (FR-13b)', async () => {
      const s = useReaderSettingsStore()
      s.customTheme = { name: 'Custom', bg: '#fff', fg: '#111', accent: '#4f46e5' }
      const w = mount(CustomEditor, { attachTo: document.body })
      await nextTick()
      const firstBgSwatch = w.findAllComponents({ name: 'ColorSwatchRow' })[0]
        .findAll('button')[0].element as HTMLElement
      expect(document.activeElement).toBe(firstBgSwatch)
      w.unmount()
    })

    it('font select calls updateSetting on change', async () => {
      const s = useReaderSettingsStore()
      const updateSpy = vi.spyOn(s, 'updateSetting')
      const w = mount(CustomEditor)
      const fontSelect = w.find('select')
      await fontSelect.setValue('Inter')
      expect(updateSpy).toHaveBeenCalledWith('font_family', 'Inter')
    })

    it('size stepper increments call updateSetting', async () => {
      const s = useReaderSettingsStore()
      s.currentSettings = { ...s.currentSettings, font_size_px: 16 }
      const updateSpy = vi.spyOn(s, 'updateSetting')
      const w = mount(CustomEditor)
      const stepper = w.findAllComponents({ name: 'Stepper' }).find(c => c.props('ariaLabel') === 'Size')!
      stepper.vm.$emit('update:modelValue', 17)
      await nextTick()
      expect(updateSpy).toHaveBeenCalledWith('font_size_px', 17)
    })
  })
  ```

- [ ] Step 2: Verify red
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/CustomEditor.spec.ts`
  Expected: FAIL — file does not exist.

- [ ] Step 3: Implement `CustomEditor.vue`
  - Imports: `ColorSwatchRow`, `Stepper`, `ContrastBadge`, store, `ref`, `computed`, `onMounted`, `nextTick`.
  - Constants: `BG_PALETTE`, `FG_PALETTE`, `FONTS` arrays (port from existing popover).
  - Computed `activeBg`/`activeFg`/`activeAccent` mirroring the existing `activeCustomBg/Fg/Accent` logic in current popover.
  - `stagePatch(patch)`: same as current popover (copy from `ReaderSettingsPopover.vue:65-73`).
  - `commit()`: calls `store.saveCustom()` then `store.applyCustom()`.
  - `revert()`: calls `store.discardCustom()`.
  - Template (in spec FR-13 order): BACKGROUND `<ColorSwatchRow>` (ref the first button), FOREGROUND `<ColorSwatchRow>`, ACCENT `<input type="color">`, FONT `<select>`, SIZE `<Stepper>`, LINE SPACING `<Stepper>`, CONTENT WIDTH `<Stepper>`, `<ContrastBadge>`, live preview block, action row (dirty hint + Revert + Save).
  - Action row: `<div class="actions-row">` with `<span v-if="store.dirty">Custom theme preview (not saved)</span>` and two buttons (`:disabled="!store.dirty"`).
  - `onMounted(async () => { await nextTick(); firstBgSwatchRef.value?.focus() })` where `firstBgSwatchRef` is captured via the BG `ColorSwatchRow`'s exposed first-button or via a query inside the row.
    - Pragmatic implementation: give the BG row a `data-first-swatch-host` attribute and inside `onMounted` do `(el.value?.querySelector('button') as HTMLElement | null)?.focus()`.

- [ ] Step 4: Verify green
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/CustomEditor.spec.ts`
  Expected: 8/8 PASS.

- [ ] Step 5: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/CustomEditor.vue src/components/settings/__tests__/CustomEditor.spec.ts
  git commit -m "feat(reader-settings): add CustomEditor with inline Save/Revert"
  ```

**Inline verification:**
- 8 tests pass.
- `grep -n 'StickySaveBar' src/components/settings/CustomEditor.vue` — zero matches (Save/Revert is inline).

---

### T7: Rewrite `ReaderSettingsPopover.vue` — compose new components

**Goal:** Reduce popover to header + ThemeGrid + (CustomEditor v-if) + chrome toggles. Default state ≤480px tall. Custom card click→editor expand wires focus into CustomEditor; closing the editor refocuses the Custom card via the grid's exposed method.
**Spec refs:** FR-09, FR-10, FR-11, FR-12, FR-13b, FR-21, FR-22, FR-30, D7.

**Files:**
- Modify: `frontend/src/components/settings/ReaderSettingsPopover.vue`

**Steps:**

- [ ] Step 1: Add a placeholder rewrite test (will be expanded in T11)
  Edit `src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`. Replace the whole file with a minimal smoke test:
  ```ts
  import { mount } from '@vue/test-utils'
  import { setActivePinia, createPinia } from 'pinia'
  import { describe, it, expect, beforeEach } from 'vitest'
  import ReaderSettingsPopover from '../ReaderSettingsPopover.vue'
  import { useReaderSettingsStore } from '@/stores/readerSettings'

  const PRESETS = [
    { id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' },
  ]

  describe('ReaderSettingsPopover (T7 smoke)', () => {
    beforeEach(() => setActivePinia(createPinia()))

    it('renders ThemeGrid and chrome toggles when popoverOpen', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true
      const w = mount(ReaderSettingsPopover)
      expect(w.findComponent({ name: 'ThemeGrid' }).exists()).toBe(true)
      expect(w.text()).toMatch(/highlights/i)
    })

    it('does not render CustomEditor by default', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true; s.editingCustom = false
      const w = mount(ReaderSettingsPopover)
      expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(false)
    })

    it('renders CustomEditor when editingCustom and Custom is applied', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true
      s.appliedPresetKey = 'custom'
      s.editingCustom = true
      const w = mount(ReaderSettingsPopover)
      expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(true)
    })

    it('does NOT render font/size/spacing/width controls in default state (FR-10)', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true; s.editingCustom = false
      const w = mount(ReaderSettingsPopover)
      // No <select> for font in default state (the chrome scope select is fine — assert it lives outside CustomEditor only)
      expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(false)
      expect(w.text()).not.toMatch(/^Font$/m)
      expect(w.text()).not.toMatch(/Line Spacing/i)
      expect(w.text()).not.toMatch(/Content Width/i)
    })

    it('does NOT render StickySaveBar (FR-29 / D5)', () => {
      const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true
      const w = mount(ReaderSettingsPopover)
      expect(w.findComponent({ name: 'StickySaveBar' }).exists()).toBe(false)
    })
  })
  ```

- [ ] Step 2: Verify red
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`
  Expected: All 5 FAIL.

- [ ] Step 3: Rewrite `ReaderSettingsPopover.vue`
  Replace the file entirely with:
  - Imports: `ThemeGrid`, `CustomEditor`, store, `computed`, `ref`, `nextTick`, `watch`.
  - Template (top-level v-if `store.popoverOpen`):
    ```html
    <div class="settings-popover" v-if="store.popoverOpen" ref="popoverRef">
      <header class="settings-header">
        <h2>Reader Settings</h2>
        <button class="close-btn" type="button" @click="store.popoverOpen = false">×</button>
      </header>

      <ThemeGrid ref="gridRef" />

      <CustomEditor v-if="store.editingCustom && store.appliedPresetKey === 'custom'" />

      <div class="settings-section toggle-row">
        <label class="toggle-cell">
          <input type="checkbox" :checked="store.highlightsVisible"
            @change="store.highlightsVisible = ($event.target as HTMLInputElement).checked" />
          <span>Show highlights inline</span>
        </label>
        <label class="toggle-cell">
          <span>Annotations scope</span>
          <select :value="store.annotationsScope"
            @change="store.annotationsScope = ($event.target as HTMLSelectElement).value as any">
            <option value="current">Current section</option>
            <option value="all">All sections</option>
          </select>
        </label>
      </div>
    </div>
    ```
  - Script: `popoverRef = ref<HTMLElement|null>(null)`; `gridRef = ref<InstanceType<typeof ThemeGrid>|null>(null)`. Add a watcher: when `editingCustom` flips `true → false` AND `popoverOpen` is true, call `await nextTick(); gridRef.value?.focusActiveCard()` (FR-13b — focus returns to Custom card; the Custom card is the active card whenever `appliedPresetKey === 'custom'`).
  - Style: keep the existing popover container CSS (width 400px, border-radius, box-shadow, max-height: 85vh, overflow-y: auto). DELETE all other CSS — it now lives in the extracted components.

- [ ] Step 4: Verify green
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`
  Expected: 5/5 PASS.

- [ ] Step 5: Type-check (PresetCards still references missing API but is no longer imported by popover; fine until T10 deletes it)
  Run: `cd frontend && npm run type-check`
  Expected: errors only inside `PresetCards.vue` (T10 deletes it). If errors elsewhere, stop and investigate.

- [ ] Step 6: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/ReaderSettingsPopover.vue src/components/settings/__tests__/ReaderSettingsPopover.spec.ts
  git commit -m "feat(reader-settings): rewrite popover to compose ThemeGrid + CustomEditor"
  ```

**Inline verification:**
- 5 popover smoke tests pass.
- `wc -l src/components/settings/ReaderSettingsPopover.vue` — under ~150 lines (~430 → ≤150).

---

### T8: Esc + outside-click dismissal

**Goal:** Pressing Esc closes the popover and returns focus to the gear button. Clicking outside the popover (and outside the gear) closes the popover. Pending Custom edits are preserved either way.
**Spec refs:** FR-31, FR-32, P1.

**Files:**
- Modify: `frontend/src/components/settings/ReaderSettingsPopover.vue`
- Modify: `frontend/src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`

**Steps:**

- [ ] Step 1: Failing tests — append to popover spec:
  ```ts
  it('Escape key closes the popover', async () => {
    const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true
    mount(ReaderSettingsPopover, { attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await new Promise(r => setTimeout(r, 0))
    expect(s.popoverOpen).toBe(false)
  })

  it('outside click closes the popover', async () => {
    const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true
    const w = mount(ReaderSettingsPopover, { attachTo: document.body })
    const outside = document.createElement('div'); document.body.appendChild(outside)
    outside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await new Promise(r => setTimeout(r, 0))
    expect(s.popoverOpen).toBe(false)
    outside.remove(); w.unmount()
  })

  it('click inside popover does NOT close', async () => {
    const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true
    const w = mount(ReaderSettingsPopover, { attachTo: document.body })
    const inside = w.find('.settings-popover').element
    inside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await new Promise(r => setTimeout(r, 0))
    expect(s.popoverOpen).toBe(true)
    w.unmount()
  })

  it('outside click preserves pendingCustom (E9)', async () => {
    const s = useReaderSettingsStore(); s.presets = PRESETS as never; s.popoverOpen = true
    s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#abc' }; s.dirty = true
    const w = mount(ReaderSettingsPopover, { attachTo: document.body })
    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await new Promise(r => setTimeout(r, 0))
    expect(s.pendingCustom).toEqual({ name: 'Custom', bg: '#000', fg: '#fff', accent: '#abc' })
    expect(s.dirty).toBe(true)
    w.unmount()
  })
  ```

- [ ] Step 2: Verify red
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`
  Expected: 4 new tests fail.

- [ ] Step 2.5 (prerequisite): add `aria-label="Reader settings"` to the gear button in `frontend/src/views/BookDetailView.vue` near line 215 (existing `class="action-btn"` button with `title="Reader settings"`). Keep the title attribute too (tooltip). Run `grep -n 'aria-label="Reader settings"' src/views/BookDetailView.vue` — expect 1 match.

- [ ] Step 3: Implement in `ReaderSettingsPopover.vue`:
  - Use `onMounted` and `onBeforeUnmount` to attach/detach two document listeners:
    ```ts
    function onKeydown(e: KeyboardEvent) {
      if (e.key === 'Escape' && store.popoverOpen) {
        store.popoverOpen = false
        // Best-effort focus return: query the gear button by aria-label/title.
        const gear = document.querySelector('[aria-label="Reader settings"]') as HTMLElement | null
        gear?.focus()
      }
    }
    function onMousedown(e: MouseEvent) {
      if (!store.popoverOpen) return
      const target = e.target as Node
      const popoverEl = popoverRef.value
      const gear = document.querySelector('[aria-label="Reader settings"]')
      if (popoverEl?.contains(target)) return
      if (gear?.contains(target)) return  // Let the gear's own click handler toggle.
      store.popoverOpen = false
    }
    onMounted(() => {
      document.addEventListener('keydown', onKeydown)
      document.addEventListener('mousedown', onMousedown)
    })
    onBeforeUnmount(() => {
      document.removeEventListener('keydown', onKeydown)
      document.removeEventListener('mousedown', onMousedown)
    })
    ```
  - Note on E10 (native `<input type="color">` dialog): the dialog opens after a click on the input that is INSIDE the popover, so the mousedown is contained — no false dismissal.

- [ ] Step 4: Verify green
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`
  Expected: 9/9 PASS (5 original + 4 new).

- [ ] Step 5: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/ReaderSettingsPopover.vue src/components/settings/__tests__/ReaderSettingsPopover.spec.ts
  git commit -m "feat(reader-settings): Esc + outside-click dismissal preserves pendingCustom"
  ```

**Inline verification:**
- 9 popover tests pass.
- `grep -n '@vueuse' src/components/settings/ReaderSettingsPopover.vue` — zero matches (no new dep).

---

### T9: Preset-load-fail notice — popover-level integration (Q5 / E1)

**Goal:** Verify the inline `<div class="presets-error">` from T5 surfaces correctly through the popover. Per Decision P9, we keep the inline div (no reuse of `PresetsFetchError.vue`) for predictable testing.
**Spec refs:** E1, P9.

**Files:**
- Modify: `frontend/src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`

**Steps:**

- [ ] Step 1: Add an end-to-end assertion to the popover spec:
  ```ts
  it('shows preset-load-fail notice in popover when presets empty', () => {
    const s = useReaderSettingsStore(); s.presets = [] as never; s.popoverOpen = true
    const w = mount(ReaderSettingsPopover)
    expect(w.text()).toMatch(/couldn't load themes/i)
  })
  ```

- [ ] Step 2: Verify green
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/`
  Expected: all settings specs PASS.

- [ ] Step 3: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/__tests__/ReaderSettingsPopover.spec.ts
  git commit -m "test(reader-settings): popover-level assertion for preset-load-fail notice (E1)"
  ```

**Inline verification:**
- Popover spec includes the "couldn't load themes" assertion and passes.

---

### T10: Delete `PresetCards.vue`, `StickySaveBar.vue`, and stale tests

**Goal:** Remove dead code; gate via grep.
**Spec refs:** FR-28, FR-29.

**Files:**
- Delete: `frontend/src/components/settings/PresetCards.vue`
- Delete: `frontend/src/components/settings/__tests__/PresetCards.spec.ts`
- Delete: `frontend/src/components/common/StickySaveBar.vue`

**Steps:**

- [ ] Step 1: Pre-delete grep — confirm no remaining import outside the files being deleted
  Run:
  ```bash
  cd frontend && grep -rn "PresetCards" src --include='*.vue' --include='*.ts' | grep -v 'PresetCards.vue:\|PresetCards.spec.ts:'
  grep -rn "StickySaveBar" src --include='*.vue' --include='*.ts' | grep -v 'StickySaveBar.vue:'
  grep -rn "openCustomPicker" src --include='*.vue' --include='*.ts' | grep -v 'PresetCards.vue:\|PresetCards.spec.ts:'
  ```
  Expected: all three commands output zero lines.

- [ ] Step 2: Delete the files
  ```bash
  cd frontend
  git rm src/components/settings/PresetCards.vue
  git rm src/components/settings/__tests__/PresetCards.spec.ts
  git rm src/components/common/StickySaveBar.vue
  ```

- [ ] Step 3: Re-run cleanup greps — confirm zero matches
  Run:
  ```bash
  cd frontend
  ! grep -rn "PresetCards" src --include='*.vue' --include='*.ts'
  ! grep -rn "StickySaveBar" src --include='*.vue' --include='*.ts'
  ! grep -rn "openCustomPicker" src --include='*.vue' --include='*.ts'
  ```
  Expected: every `!` exits 0 (i.e. each grep returned no matches).

- [ ] Step 4: Type-check + full unit-test suite
  Run: `cd frontend && npm run type-check && npm run test:unit -- --run`
  Expected: type-check exits 0 (PresetCards is gone — no more residual errors); all unit tests pass.

- [ ] Step 5: Lint + commit
  ```bash
  cd frontend && npm run lint
  git commit -m "feat(reader-settings): delete PresetCards and StickySaveBar"
  ```

**Inline verification:**
- All three greps return zero matches.
- `npm run type-check` exits 0.
- Full unit suite passes.

---

### T11: Round out component tests + integration coverage

**Goal:** Sweep for coverage gaps surfaced by the rewrite. Add the integration tests the spec calls out that aren't yet covered: switching from Custom to a preset mid-edit, save-then-reopen, popover open resets editingCustom in real component flow.
**Spec refs:** §13.1, §13.2, FR-09, FR-13b, FR-20, E5, E6.

**Files:**
- Modify: `frontend/src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`
- Modify: `frontend/src/stores/__tests__/readerSettings.spec.ts`

**Steps:**

- [ ] Step 1: Add the following integration tests to the popover spec:
  ```ts
  it('switching from Custom to Sepia mid-edit collapses editor and clears pending state (E5)', async () => {
    const s = useReaderSettingsStore()
    s.presets = [
      { id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' },
      { id: 3, name: 'Sepia', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'sepia', created_at: '' },
    ] as never
    s.popoverOpen = true; s.appliedPresetKey = 'custom'; s.editingCustom = true
    s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#abc' }; s.dirty = true
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(true)
    // Click Sepia
    const sepia = w.findAllComponents({ name: 'ThemeCard' }).find(c => c.props('label') === 'Sepia')!
    await sepia.trigger('click')
    expect(s.appliedPresetKey).toBe('system:3')
    expect(s.editingCustom).toBe(false)
    expect(s.pendingCustom).toBeNull()
    expect(s.dirty).toBe(false)
  })

  it('toggling editor closed via second Custom click preserves pendingCustom (Q6/E6)', async () => {
    const s = useReaderSettingsStore()
    s.presets = [{ id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' }] as never
    s.popoverOpen = true; s.appliedPresetKey = 'custom'; s.editingCustom = true
    s.pendingCustom = { name: 'Custom', bg: '#222', fg: '#eee', accent: '#abc' }; s.dirty = true
    const w = mount(ReaderSettingsPopover)
    const customCard = w.findAllComponents({ name: 'ThemeCard' }).find(c => c.props('label') === 'Custom')!
    await customCard.trigger('click')
    expect(s.editingCustom).toBe(false)
    // Spec Q6 answer: pendingCustom preserved.
    expect(s.pendingCustom).toEqual({ name: 'Custom', bg: '#222', fg: '#eee', accent: '#abc' })
    expect(s.dirty).toBe(true)
  })

  it('reopening the popover with Custom active leaves editor collapsed (D7/D12)', async () => {
    const s = useReaderSettingsStore()
    s.presets = [{ id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' }] as never
    s.appliedPresetKey = 'custom'; s.editingCustom = true; s.popoverOpen = true
    // Simulate close + open
    s.popoverOpen = false
    await new Promise(r => setTimeout(r, 0))
    s.popoverOpen = true
    await new Promise(r => setTimeout(r, 0))
    expect(s.editingCustom).toBe(false)
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(false)
  })
  ```

- [ ] Step 2: Verify red, then green (these may pass already from T2/T7 — that's fine; they codify behaviour)
  Run: `cd frontend && npm run test:unit -- --run src/components/settings/__tests__/ReaderSettingsPopover.spec.ts`
  Expected: all PASS.

- [ ] Step 3: Run the entire frontend suite to catch any regression
  Run: `cd frontend && npm run test:unit -- --run`
  Expected: total pass count ≥ T1 baseline (minus the 8 deleted PresetCards tests + 1 store test, plus the new tests added in T2–T11).

- [ ] Step 4: Lint + commit
  ```bash
  cd frontend && npm run lint
  git add src/components/settings/__tests__/ReaderSettingsPopover.spec.ts src/stores/__tests__/readerSettings.spec.ts
  git commit -m "test(reader-settings): add integration coverage for mid-edit switch and editor toggle"
  ```

**Inline verification:**
- All popover specs PASS.
- Full unit-test suite PASSes.

---

### T12: Final verification — type-check, build, Playwright MCP, screenshots

**Goal:** End-to-end proof. Type-check, lint, build, then run the spec §5 user journeys interactively against a built app on `:8765`.
**Spec refs:** All FR/NFR.

**Files:**
- None (verification only).

**Steps:**

- [ ] Step 1: Lint + format
  Run: `cd frontend && npm run lint && npx prettier --check src/components/settings src/stores`
  Expected: both exit 0.

- [ ] Step 2: Type-check
  Run: `cd frontend && npm run type-check`
  Expected: exit 0.

- [ ] Step 3: Full unit suite
  Run: `cd frontend && npm run test:unit -- --run`
  Expected: all PASS, total pass count = T1 baseline − 9 (deleted) + (new tests added across T2–T11). Record exact count.

- [ ] Step 4: Production build + size sanity check
  Run: `cd frontend && npm run build`
  Expected: exit 0; `dist/` produced. Inspect `dist/assets/` — no chunk grew by more than ~5 KB vs. main (run `git diff` against a stashed before-state if rigour required; otherwise visual sanity check).

- [ ] Step 5: Cleanup grep gate
  Run:
  ```bash
  cd frontend
  ! grep -rn "PresetCards" src --include='*.vue' --include='*.ts'
  ! grep -rn "StickySaveBar" src --include='*.vue' --include='*.ts'
  ! grep -rn "openCustomPicker" src --include='*.vue' --include='*.ts'
  ```
  Expected: every command exits 0 (zero matches).

- [ ] Step 6: Ship the build into the backend's static dir
  Run:
  ```bash
  cd /Users/maneeshdhabria/Desktop/Projects/personal/book-companion
  rm -rf backend/app/static && cp -R frontend/dist backend/app/static
  ```

- [ ] Step 7: Start a verification server on :8765 (per CLAUDE.md "Interactive verification")
  Run:
  ```bash
  cd backend && uv run bookcompanion serve --port 8765 &
  sleep 2 && curl -sf http://localhost:8765/api/v1/health
  ```
  Expected: health check 200.

- [ ] Step 8: Seed at least one book if DB is empty
  Run:
  ```bash
  sqlite3 ~/Library/Application\ Support/bookcompanion/library.db "SELECT count(*) FROM books"
  # If 0:
  cd backend && uv run python tests/fixtures/download_fixtures.py
  echo n | uv run bookcompanion add tests/fixtures/sample_epub/art_of_war.epub
  ```

- [ ] Step 9: Playwright MCP walkthrough — exercise spec §5 journeys
  Sequence (use `mcp__plugin_playwright_playwright__browser_*` tools):
  1. `browser_navigate` to `http://localhost:8765/books/1/sections/1` (or whichever section URL is valid).
  2. `browser_evaluate(() => document.querySelector('[aria-label="Reader settings"]')?.click())` — open popover.
  3. `browser_evaluate(() => document.querySelector('.settings-popover')?.scrollHeight)` — assert ≤ 480.
  4. `browser_snapshot` — visually inspect: 7 cards in a 3×3 grid, no font/size controls, no sticky save bar.
  5. Click a non-Custom card (e.g. Sepia) via `browser_click`. Take a screenshot — page recoloured, ✓ on Sepia.
  6. Click Custom card — editor expands; assert focus on first BG swatch via `browser_evaluate(() => document.activeElement?.getAttribute('aria-label'))`.
  7. Adjust size stepper down to 15 → click Save. Take screenshot. Reopen popover (close, then click gear) → editor must be collapsed (D7).
  8. Click Custom again → editor reopens with size still 15.
  9. Press Escape → popover closes. Take screenshot.
  10. Reopen, click outside the popover → popover closes.
  11. Keyboard test: focus the gear (Tab), press Enter → popover opens. Tab into grid, ArrowRight twice, Enter → assert applied preset matches.
  12. `browser_console_messages(level: 'error')` — assert empty.

  **Hard assertions (in addition to the visual snapshot) — collect via `browser_evaluate` and verify in the same run:**
  - `document.querySelectorAll('.theme-grid [role="radio"]').length === 7`
  - `document.querySelector('.settings-popover').scrollHeight <= 480`
  - After clicking Sepia: `document.querySelector('.theme-grid [aria-pressed="true"]').textContent.includes('Sepia')`
  - After clicking Custom: `document.querySelectorAll('.custom-editor, [data-testid="custom-editor"]').length >= 1` AND `document.activeElement.getAttribute('aria-label')?.startsWith('Background ')` (FR-13b focus target)
  - After Save and reopen: `document.querySelectorAll('.custom-editor, [data-testid="custom-editor"]').length === 0` (D7 collapsed-on-reopen)
  - After Esc: `document.querySelectorAll('.settings-popover').length === 0`
  - **NFR-01 network check:** `mcp__plugin_playwright_playwright__browser_network_requests` between popover-open and theme-change — assert zero new XHR/fetch calls beyond the initial preset fetch already cached.

- [ ] Step 10: Take a final after-state screenshot of the popover for the PR description
  Save as `reader-settings-after.png` in repo root.

- [ ] Step 11: Tear down the verification server
  Run: `kill $(lsof -ti:8765 2>/dev/null) 2>/dev/null || true`

- [ ] Step 12 (NFR-05 i18n check): `grep -rn "i18n\|t(" frontend/src/components/settings/ThemeGrid.vue frontend/src/components/settings/CustomEditor.vue frontend/src/components/settings/ThemeCard.vue frontend/src/components/settings/Stepper.vue frontend/src/components/settings/ColorSwatchRow.vue` — expect zero matches; all user-visible strings are inline literals matching project convention.

- [ ] Step 13: Update changelog if the user maintains one
  Run: `cd /Users/maneeshdhabria/Desktop/Projects/personal/book-companion && grep -l 'reader-settings\|popover' docs/changelog.md && echo "changelog likely updated"`
  - If a session-log/changelog convention applies (per CLAUDE.md), append a one-line entry. Otherwise skip.

**Cleanup:**

- [ ] Remove `reader-settings-default.png`, `reader-settings-bottom.png`, `reader-settings-custom.png`, `reader-settings-custom-mid.png` (before-state captures from the requirements session) only if no longer needed for the PR; otherwise keep them attached.
- [ ] Stop verification server: `kill $(lsof -ti:8765) 2>/dev/null || true`
- [ ] Remove the temporary `backend/app/static` if it shouldn't be checked in (per repo convention — leave it alone if `static` is gitignored).

**Inline verification:**
- All commands above exit 0.
- 7 cards visible in the snapshot, no font/size controls in default state.
- Console errors empty.
- `npm run test:unit -- --run` total pass count = (T1 baseline − 9) + (new tests added).

---

## Review Log

| Loop | Findings | Changes Made |
|------|----------|-------------|
| 1    | (S1) FR-27 not cited; (S2) NFR-01 + NFR-05 not cited; (D1) Playwright walkthrough relied on visual review for several assertions; (D2) Esc focus-return used fragile `[title=]` selector. | (S1) Added FR-27 regression assertion to T2 inline verification. (S2) Added explicit NFR-01 network-call check + NFR-05 i18n grep to T12. (D1) Added hard `browser_evaluate` assertions to T12 step 9 (card count, scrollHeight, aria-pressed, focus target, network). (D2) Switched to `[aria-label="Reader settings"]` and added a step in T8 to set `aria-label` on the gear button in `BookDetailView.vue`. |
| 2    | (L2-1) ThemeGrid implementation hardcoded a 6-theme list with "render stub if preset missing" pattern — not data-driven. (L2-2) `focusActiveCard()` didn't sync local `focusedIndex`, breaking arrow-nav after focus return. (L2-3) T9 had a "decide reuse of PresetsFetchError.vue at recon time" branch that risked T5 spec churn. | (L2-1) Rewrote T5 step 3 to render `store.presets` data-driven with frontend-owned `NAME_ORDER` sort + extracted shared `themeMap` to `themeColors.ts`. Added decision P10 to log. (L2-2) Added explicit note in T5 that `focusActiveCard()` syncs `focusedIndex = activeIndex` before focusing. (L2-3) Pinned decision to "always inline div" via P9; simplified T9 to a single popover-level integration test. |

---

## Open Questions

| # | Question | Owner | Resolution |
|---|----------|-------|-----------|
| Q1 | Analytics instrumentation | Maneesh | Skipped (deferred to follow-up). |
| Q2 | Viewport overflow | Maneesh | Resolved — scroll inside popover (existing `max-height: 85vh; overflow-y: auto`). No new code. |
| Q3 | Custom slot scope | Maneesh | Stay global per device. |
| Q4 | `ReadingSettings.vue` migration | Maneesh | Audit confirmed no font/size fields to migrate. |
| Q5 | Preset-load-fail UI | Maneesh | "Couldn't load themes" notice + Custom-only grid. |
| Q6 | `pendingCustom` on editor toggle close | Maneesh | Preserve (consistent with E9 popover-close). |
