/**
 * Frontend constants mirroring backend QuizConfig defaults.
 * Kept in sync with backend/app/config.py:QuizConfig manually — no settings
 * route consumed yet (see T31 hand-off note).
 */
export const QUIZ_EXPLAIN_SOFT_CAP = 2
export const QUIZ_OVERRIDE_MAX_CHARS = 500
export const QUIZ_SPECIFIC_CHAPTERS_TOKEN_BUDGET = 60_000
export const QUIZ_SUBMIT_FALLBACK_REENABLE_MS = 5_000
