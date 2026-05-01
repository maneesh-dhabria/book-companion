# Task 11 — F7: ContentToggle inactive tab styling

## Files touched
- frontend/src/components/reader/ContentToggle.vue
- frontend/src/components/__tests__/ContentToggle.spec.ts (new)

## Decisions / deviations
- Component emits a single `toggle` event (no payload). Tests assert
  `emitted('toggle')` rather than `update:mode` from the plan snippet —
  parent owns mode state.

## Runtime evidence
- `npx vitest run ContentToggle` — 2 / 2 pass.
