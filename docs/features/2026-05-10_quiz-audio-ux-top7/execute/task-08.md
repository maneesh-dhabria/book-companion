---
status: done
started_at: 2026-05-10T12:46:00Z
completed_at: 2026-05-10T12:48:00Z
files_touched:
  - frontend/src/api/client.ts
  - frontend/src/api/__tests__/client.error.spec.ts
---

Extended `ApiError` constructor with branch for object-shaped detail (`{detail: string, llm_stderr_tail?: string}`) — message taken from inner `detail`, tail captured on `llmStderrTail` (typed `string | null`). Legacy string and pydantic-array shapes preserved verbatim. Per D15 the constructor stays faithful — empty/HTML substitution lives in the store layer (T9). 3 new tests cover all three shapes; type-check + local lint clean for touched files.
