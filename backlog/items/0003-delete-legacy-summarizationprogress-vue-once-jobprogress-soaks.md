---
id: 0003
title: Delete legacy SummarizationProgress.vue once JobProgress has soaked
type: tech-debt
status: inbox
priority: could
labels: [frontend, cleanup]
created: 2026-04-30
updated: 2026-04-30
source: docs/plans/2026-04-30-upload-summarize-flow-ux-fixes-implementation-plan.md
spec_doc:
plan_doc:
pr:
parent:
dependencies: []
---

## Context

Per decision P7 in the upload+summarize UX-fixes plan, `<JobProgress>` is the new canonical job-state component (used in UploadWizard Step 4 and PersistentProcessingIndicator). `frontend/src/components/book/SummarizationProgress.vue` is left mounted only on `BookDetailView` to avoid scope creep. Once JobProgress has run in production for a while and proven correct across all states, SummarizationProgress.vue should be removed and BookDetailView migrated to use JobProgress (or the queue-store getters directly).

## Acceptance Criteria

- `frontend/src/components/book/SummarizationProgress.vue` deleted.
- `BookDetailView.vue` no longer imports it (uses `<JobProgress>` or reads `useJobQueueStore()` getters directly).
- All references in tests removed.
- `npm run test:unit` and `npm run type-check` green.
