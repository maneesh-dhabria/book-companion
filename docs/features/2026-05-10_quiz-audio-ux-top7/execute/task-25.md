---
task_number: 25
task_name: "FR-19 Sample text from book.sections[0] + FR-22 footer anchor"
plan_path: "docs/features/2026-05-10_quiz-audio-ux-top7/03_plan.md"
branch: "feat/quiz-audio-ux-top7"
worktree_path: "/Users/maneeshdhabria/Desktop/Projects/personal/book-companion-quiz-audio-ux-top7"
status: done
started_at: 2026-05-10T17:04:00Z
completed_at: 2026-05-10T17:09:00Z
files_touched:
  - frontend/src/components/settings/SpikeFindingsBlock.vue
  - frontend/src/components/audio/GenerateAudioModal.vue
  - frontend/src/components/settings/__tests__/SpikeFindingsBlock.sampleText.spec.ts
---

**FR-19** — `SpikeFindingsBlock` accepts an optional `bookId` prop. On first listen-comparison click, if `bookId` is set and the cache is cold, fetches `/api/v1/books/{id}` and uses `sections[0].content_md` markdown-stripped (inline `stripMarkdown` util — bold/italic/heading/inline-code/link wrappers + whitespace collapse) sliced to 280 chars. Caches the result in a `sampleTextCache` ref so subsequent clicks reuse it. Falls back to the pangram in any of: no `bookId` prop, fetch failed, stripped text < 20 chars (likely an empty section).

**FR-22 footer anchor** — `GenerateAudioModal` now mounts a `<router-link to="/settings/tts#audio">Settings → Text-to-speech</router-link>` (`data-testid="settings-link"`) below the action buttons so users can jump to the wpm + voice settings without leaving context.

DEVIATION from plan: plan's "fetch + strip markdown via existing util" — no markdown-strip util existed in `frontend/src`, so the strip is inline. Kept it minimal — handles the markdown the parser actually emits in `content_md` (bold, italic, headings, links, inline code). A more thorough strip would belong in a shared util later.

2 new tests; 8/8 SpikeFindingsBlock specs green; 344 audio + quiz + settings + stores regression green; vue-tsc clean.

**Phase 6 complete.** All Settings → TTS tasks (T22-T25) landed.
