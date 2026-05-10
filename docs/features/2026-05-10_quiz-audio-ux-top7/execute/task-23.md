---
task_number: 23
task_name: "FR-17 Compare voices heading rename + fallback rewrite"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T16:56:00Z
completed_at: 2026-05-10T16:59:00Z
files_touched:
  - frontend/src/components/settings/SpikeFindingsBlock.vue
  - frontend/src/components/settings/__tests__/SpikeFindingsBlock.compareVoices.spec.ts
  - frontend/src/components/settings/__tests__/SpikeFindingsBlock.spec.ts
---

Heading "Spike findings" → "Compare voices". Internal `SpikeResp` interface → `CompareVoicesResp`. Replaced dev-only fallback ("Spike not yet run. Run `bookcompanion spike tts`...") with user-facing copy: "Hear the same sample in both engines below. Click to compare Kokoro and your browser's Web Speech voice side by side." Listen-comparison button now mounts unconditionally — only the markdown body is gated on `data.available`. The `data.path` link is gated on `data.available && data.path` (it only makes sense when authored notes were loaded).

Per plan FR-17 explicit constraint: file rename to `CompareVoicesBlock.vue` is OUT of scope; the import path remains `SpikeFindingsBlock.vue`. Existing test was rewritten to cover the new fallback copy rather than the old dev-only one.

3 new tests + 5/5 total SpikeFindingsBlock specs green; vue-tsc clean.
