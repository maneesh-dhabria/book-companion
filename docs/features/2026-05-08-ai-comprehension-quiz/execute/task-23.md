---
task_number: 23
task_name: "Quiz REST client"
task_goal_hash: 142b19bad369bf583ef62313b7efdc3279cc85026aa22d72583043a26859f39d
plan_path: "docs/features/2026-05-08-ai-comprehension-quiz/03_plan.md"
branch: "feature/ai-comprehension-quiz"
worktree_path: ".worktrees/ai-comprehension-quiz"
status: done
started_at: 2026-05-09T05:05:00Z
completed_at: 2026-05-09T05:08:00Z
files_touched:
  - frontend/src/api/quizSessions.ts
  - frontend/src/api/__tests__/quizSessions.spec.ts
---

## Summary

12 typed async functions, one per quiz route, delegating to the existing `apiClient` (which prepends `/api/v1` and throws `ApiError` carrying `status` + `detail`).

| Function | Method | Path |
|---|---|---|
| `listSessions(bookId)` | GET | `/books/:id/quiz-sessions` |
| `getLifetimeTally(bookId)` | GET | `/books/:id/quiz-sessions/lifetime-tally` |
| `startSession(bookId, body)` | POST | `/books/:id/quiz-sessions` |
| `getSession(sessionId)` | GET | `/quiz-sessions/:sid` |
| `nextQuestion(sessionId)` | POST | `/quiz-sessions/:sid/next-question` |
| `submitAnswer(sid, qid, answer)` | POST | `/quiz-sessions/:sid/questions/:qid/answer` |
| `recordSelfAssessment(sid, qid, sa)` | PATCH | `/quiz-sessions/:sid/questions/:qid` |
| `skipQuestion(sid, qid)` | POST | `/quiz-sessions/:sid/questions/:qid/skip` |
| `explainQuestion(sid, qid)` | POST | `/quiz-sessions/:sid/questions/:qid/explain` |
| `overrideQuestion(sid, qid, note)` | POST | `/quiz-sessions/:sid/questions/:qid/override` |
| `discardQuestion(sid, qid)` | POST | `/quiz-sessions/:sid/questions/:qid/discard` |
| `stopSession(sid)` | POST | `/quiz-sessions/:sid/stop` |

## Verification

- `npm run test:unit -- --run src/api/__tests__/quizSessions.spec.ts` → **13 passed**.
- `npm run type-check` → 0 errors.

## Notes

- Plan called for "11 quiz routes" in the commit message but actual count is 12 (list / lifetime / start / detail / next / answer / patch-self-assessment / skip / explain / override / discard / stop). Commit message reflects the correct 12.
- DEVIATION: `exportSessionUrl` is NOT in this client — plan defers it to T34 (export task).
- Reused `apiClient` rather than reinventing fetch wrappers; ApiError already exposes `status` + `detail` so the store's optimistic-rollback (T24) just inspects `e.status === 409`.
