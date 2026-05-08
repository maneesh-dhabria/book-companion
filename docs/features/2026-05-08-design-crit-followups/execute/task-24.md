---
task_number: 24
task_name: "T24: AudioTab empty state + popover"
task_goal_hash: e7bb68d5f511dcad9dccd56e7a7ab9c32cfb01ac8868a6f74d9a302a708fecc2
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T20:50:00Z
completed_at: 2026-05-08T21:01:00Z
files_touched:
  - frontend/src/components/audio/AudioTab.vue
  - frontend/src/components/audio/DifferencePopover.vue
  - frontend/src/components/settings/SettingsTtsPanel.vue
  - frontend/src/components/audio/__tests__/AudioTab.spec.ts
  - frontend/src/components/audio/__tests__/DifferencePopover.spec.ts
  - frontend/src/components/audio/Playbar.vue
  - frontend/src/components/audio/__tests__/Playbar.spec.ts
---

# T24: AudioTab empty state + popover (FR-E04, FR-E05, FR-E06)

## Outcome
- **AudioTab no-audio state rewrite:** Replaced the bare "No audio yet for this book." + button with a richer panel:
  - `<EngineChip>` of the **default** engine (derived from `useTtsPlayerStore().defaultEngine`, mapped `mp3` → `kokoro`).
  - `audio-estimate` line: `≈ X min on Kokoro` (computed as `total * 30s` rounded to minutes, min 1) when default is Kokoro; `Instant on Web Speech (no pre-generation needed)` otherwise.
  - `audio-scope` chip: `N chapter summary/summaries` (singular/plural).
  - Primary `Generate audio` button (existing handler).
  - Secondary `What's the difference?` link button toggling the popover.
- **`DifferencePopover.vue`:** New component, props `{ open }`, emits `close`. Renders `role="dialog"` with `aria-modal="false"` (passive popover, not a blocking modal). Two paragraphs comparing Kokoro vs. Web Speech; CTA `<router-link to="/settings/tts#audio">Open audio settings →</router-link>`. Closes on Esc and on outside-click. Auto-focuses on open. Uses `immediate: true` watch so initial-open mounts wire up listeners.
- **`SettingsTtsPanel.vue`:** Added `id="audio"` to the panel root so `/settings/tts#audio` anchor-scrolls to the engine settings.
- **Playbar tooltip link (T22 follow-up):** Updated `Web Speech can't seek/scrub. Install Kokoro for full controls →` link from `/settings#audio` to `/settings/tts#audio` (the actual route — `/settings` without a section param falls through to GeneralSettings via the route shape `/settings/:section?`). Adjusted T22's matching test assertion.

## Plan deviations
- Plan §T24 step 2 named `useFocusTrap` from `@vueuse/integrations`. Skipped the focus-trap since this popover is non-modal (informational, doesn't lock focus or block the underlying page). Implemented Escape + outside-click close; auto-focus on open. A focus trap on a non-modal dialog is more confusing than helpful (user has no escape route via Tab).
- Plan §T24 step 4 said the link should target `/settings#audio`. The codebase's `/settings/:section?` route shape means `/settings` (no section) falls through to GeneralSettings — the audio panel lives at `/settings/tts`. Used `/settings/tts#audio` everywhere (DifferencePopover, Playbar tooltip from T22).
- Plan §T24 step 3 prescribed the engine-chip / estimate / scope copy. The engine label "Kokoro" comes from EngineChip's existing label logic (`isKokoro` ⇔ `engine === 'kokoro' || === 'mp3'`) so we feed it the mapped `'kokoro' | 'web-speech'` literal.

## Verification
- `vitest run src/components/audio/__tests__/AudioTab.spec.ts ... DifferencePopover.spec.ts ... Playbar.spec.ts` — 22/22 pass.
- Full frontend unit suite: 550/550 pass (was 545 at T23 close; +5 new — 2 AudioTab, 3 DifferencePopover, T22 link assertion updated in place).
- `npm run type-check` clean.
- `npm run build` clean (1.43s).

## Runtime evidence
The new tests cover:
- AudioTab empty state: EngineChip rendered, estimate text rendered, scope reads `47 chapter summaries`, diff trigger present, popover closed by default.
- AudioTab toggle: clicking `[data-testid="diff-trigger"]` makes the popover render.
- DifferencePopover: hidden when `open=false`, rendered with `role="dialog"` + Kokoro/Web Speech copy + `<a href="/settings/tts#audio">` when open; emits `close` on Escape.
