/**
 * Verbatim copy strings for the AI Comprehension Quiz feature (NFR-08).
 * Tests assert on these literals — do not edit ad-hoc.
 */
export const COPY = {
  noLLMBanner: 'No LLM provider detected — install Claude Code or Codex CLI.',
  noSummariesGate: 'Generate summaries first to quiz across all summaries.',
  pickAtLeastOneChapter: 'Pick at least one chapter.',
  wouldExceedBudget: 'Would exceed budget — deselect a chapter to add.',
  loadingQuestion: 'Reading the book to draft your question…',
  loadingGrading: 'Reading your answer alongside the book…',
  explainSoftCap: 'Try answering or Skip',
  fatigueClause: 'Want to keep going or wrap up here?',
  selfAssessmentMicrocopy: 'Your click is the source of truth for the tally.',
  alreadyAskedTooltip: 'Discards this question and asks the agent for a different one.',
  abandonedExportError: 'Cannot export an abandoned session — answer at least one question first.',
  resumeBanner: 'You have a session in progress —',
  resumeButton: 'Resume',
  stopAndStartButton: 'Stop & start a new one',
} as const

export type CopyKey = keyof typeof COPY
