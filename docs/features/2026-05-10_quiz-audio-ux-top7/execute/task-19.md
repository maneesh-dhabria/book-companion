---
task_number: 19
task_name: "FR-13 3-field estimate row in Generate-audio modal"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T16:35:00Z
completed_at: 2026-05-10T16:42:00Z
files_touched:
  - frontend/src/components/audio/GenerateAudioModal.vue
  - frontend/src/components/audio/__tests__/GenerateAudioModal.estimate.spec.ts
  - frontend/src/components/audio/AudioTab.vue
---

Replaced the single `cost-estimate` line with 3 testid-tagged spans (`estimate-generate`, `estimate-listen`, `estimate-disk`) plus a reactive subline (`estimate-subline`). X (gen min) and Z (disk MB) reflect delta-only via new optional props `generatedCount` + `bookSummaryGenerated`; Y (listen min) reflects whole-book via new `totalWordCount` prop divided by `useSettingsStore().settings.tts.listen_wpm` (falls back to 180 wpm if settings unloaded). All-already-generated state (deltaSummary=0, deltaBook=0, deltaAnnotations=0) disables every checkbox and morphs the confirm button to "Nothing to generate" + disabled.

DEVIATION from plan: subline numerator binds to `sectionsToGenerateForSubline` (= deltaSummary when section_summaries checkbox is on, else 0) rather than full `totalUnitsToGenerate`. This keeps the "Generating 17 of 17 sections" copy honest — book-summary and annotations contributions belong in X/Z, not in the section-count denominator. T21's reactivity test will toggle a checkbox that affects deltaSummary directly (e.g., the section-summaries one) — adjusting the subline binding is a per-T21 concern.

3 new tests + 256 audio/quiz/stores regression green; vue-tsc clean. Existing `GenerateAudioModal.spec.ts` continued to pass (its `cost-estimate` testid wraps the new 3-span layout; its `'47'` text assertion lands on the subline denominator).
