---
task_number: 16
task_name: "Audio empty-state verb-led + parallel CTAs (FR-10)"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T15:56:00Z
completed_at: 2026-05-10T16:05:00Z
files_touched:
  - frontend/src/components/audio/AudioTab.vue
  - frontend/src/components/audio/__tests__/AudioTab.empty.spec.ts
  - frontend/src/components/audio/__tests__/AudioTab.spec.ts
---

Empty-state markup restructured: H2 (`audio-empty-heading`) sits at the top, subtitle reads "Instant playback via your browser, or generate MP3s for offline listening.", parallel `[Listen]` (btn-primary, `data-testid="listen-cta"`) and `[Generate MP3 files]` (btn-secondary, `data-testid="generate-cta"`) live as siblings inside the `flex flex-wrap items-center gap-3` action row, demoted caption "No audio files yet — generate to enable seek/scrub." closes with `text-slate-500 text-sm` (REVIEW-LOG contrast fix).

DEVIATION from plan: `data-testid="generate-audio"` retired in favour of `data-testid="generate-cta"` to match T16 spec (and disambiguate from T19's modal-open generate button). Existing AudioTab.spec.ts updated to follow the rename + the new caption copy. 1 new test + 247-test full regression green.
