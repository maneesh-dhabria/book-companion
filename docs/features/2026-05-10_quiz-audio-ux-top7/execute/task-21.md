---
task_number: 21
task_name: "FR-15 estimate-subline reactive on checkbox toggle"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T16:47:00Z
completed_at: 2026-05-10T16:49:00Z
files_touched:
  - frontend/src/components/audio/GenerateAudioModal.vue
  - frontend/src/components/audio/__tests__/GenerateAudioModal.reactivity.spec.ts
---

Switched the subline numerator from a deltaSummary-only binding (introduced in T19) to `totalUnitsToGenerate` so toggling any of the three checkboxes (section_summaries / book_summary / annotations) updates the count synchronously. Denominator stays at `totalUnits` (whole-book section count). estimate-generate (X) + estimate-disk (Z) already reacted via Vue's reactive `cost` computed; the regression test added in this task locks that in too.

DEVIATION from T19's interpretation: the subline used to count only sections-summary delta. Re-read of FR-15 ("estimate row reactive on checkbox toggle") makes clear the user's mental model is "I can see how big the job will be" — that means all three checkbox contributions, not just sections.

2 new tests; 14/14 modal specs + 261 audio/quiz/stores regression green; vue-tsc clean.

**Phase 5 complete.** All Generate-audio modal tasks (T19-T21) landed.
