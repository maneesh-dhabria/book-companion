---
task_number: 2
task_name: "T2: readTime utility"
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T15:41:00Z
completed_at: 2026-05-08T15:42:00Z
files_touched:
  - frontend/src/utils/readTime.ts
  - frontend/src/utils/__tests__/readTime.spec.ts
---

# T2: readTime utility

## Outcome
Created `frontend/src/utils/readTime.ts` exporting `formatReadTime(chars)` and `formatReadTimeSum(chars[])` per spec §11.4. CHARS_PER_MINUTE = 1100.

## Verification
- `npm run test:unit -- src/utils/__tests__/readTime.spec.ts --run` → 14/14 passed.

## Notes / Deviation
The plan listed `[60001] → '1h'` as an expected value for `formatReadTimeSum`, but per spec §11.4's algorithm `60001 / 1100 = 54.55 → ceil = 55 min`, which is `<60` so output is `'55 min'`, not `'1h'`. Spec math is unambiguous; plan example was inconsistent. Followed the spec.
