---
task_number: 22
task_name: "FR-16 WpmSlider + dual listen/reading sliders"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T16:51:00Z
completed_at: 2026-05-10T16:55:00Z
files_touched:
  - frontend/src/components/settings/WpmSlider.vue
  - frontend/src/components/settings/SettingsTtsPanel.vue
  - frontend/src/components/settings/__tests__/WpmSlider.spec.ts
---

New `WpmSlider.vue` reusable component: range input + label + live value text, `change` handler emits `update:modelValue` and PATCHes `/settings` with a nested body built from a dot-path (`tts.listen_wpm` → `{tts: {listen_wpm: N}}`). PATCH failure surfaces a friendly error toast (`Failed to save <label>`).

Mounted twice in `SettingsTtsPanel.vue` (co-located rather than spinning up a new `SettingsReadingPanel.vue` per plan's "or new panel" alternative — same panel keeps the dual sliders next to each other where the user expects to compare them):
- Listen wpm: 100–400 step 25, bound to `settings.tts.listen_wpm` (default 180)
- Reading wpm: 100–500 step 25, bound to `settings.reading.reading_wpm` (default 250)

DEVIATION from plan: plan suggested optionally a new `SettingsReadingPanel.vue`. Skipped — both speeds are user-facing under the same "Text-to-speech" panel header where they compare directly. Re-titled the playback fieldset region to "Reading + listening speed" so the grouping reads naturally.

4 new tests; 77 settings + audio + quiz + stores green; vue-tsc clean.
