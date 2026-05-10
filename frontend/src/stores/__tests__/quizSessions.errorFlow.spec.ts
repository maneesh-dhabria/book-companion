import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import { useQuizSessionsStore } from '@/stores/quizSessions'
import { useUiStore } from '@/stores/ui'
import { ApiError } from '@/api/client'
import * as api from '@/api/quizSessions'

const D15_FALLBACK = "Couldn't start quiz — the server returned an unexpected error. Retry?"

function make502(detail: unknown): ApiError {
  return new ApiError(502, detail)
}

describe('quizSessions startSession error flow (FR-05 / FR-07 / D15)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('502 with object detail → toast w/ Retry, dedupeKey, inlineDiagnostic populated', async () => {
    const quiz = useQuizSessionsStore()
    const ui = useUiStore()
    vi.spyOn(api, 'startSession').mockRejectedValueOnce(
      make502({ detail: 'LLM provider error: boom', llm_stderr_tail: 'trace data' }),
    )

    await expect(quiz.startSession(1, 'whole_book', null)).rejects.toBeInstanceOf(ApiError)

    expect(ui.toasts).toHaveLength(1)
    const t = ui.toasts[0]
    expect(t.actionable).toBe(true)
    expect(t.dismissible).toBe(false)
    expect(t.dedupeKey).toBe('quiz-start')
    expect(t.action?.label).toBe('Retry')
    expect(t.message).toBe('LLM provider error: boom')

    expect(quiz.inlineDiagnostic).toEqual({
      reason: 'LLM provider error: boom',
      stderrTail: 'trace data',
    })
  })

  it('502 with empty message → D15 substitution', async () => {
    const quiz = useQuizSessionsStore()
    const ui = useUiStore()
    vi.spyOn(api, 'startSession').mockRejectedValueOnce(make502({ detail: '' }))

    await expect(quiz.startSession(1, 'whole_book', null)).rejects.toBeInstanceOf(ApiError)

    expect(ui.toasts[0].message).toBe(D15_FALLBACK)
    expect(quiz.inlineDiagnostic?.reason).toBe(D15_FALLBACK)
    expect(quiz.inlineDiagnostic?.stderrTail).toBeNull()
  })

  it('502 with HTML body → D15 substitution', async () => {
    const quiz = useQuizSessionsStore()
    const ui = useUiStore()
    vi.spyOn(api, 'startSession').mockRejectedValueOnce(
      make502('<!DOCTYPE html><html><body>Bad Gateway</body></html>'),
    )

    await expect(quiz.startSession(1, 'whole_book', null)).rejects.toBeInstanceOf(ApiError)

    expect(ui.toasts[0].message).toBe(D15_FALLBACK)
    expect(quiz.inlineDiagnostic?.reason).toBe(D15_FALLBACK)
  })

  it('retry success → toast cleared, inlineDiagnostic null', async () => {
    const quiz = useQuizSessionsStore()
    const ui = useUiStore()
    const spy = vi
      .spyOn(api, 'startSession')
      .mockRejectedValueOnce(make502({ detail: 'boom' }))
      .mockResolvedValueOnce({
        session: {
          id: 7,
          book_id: 1,
          scope: 'whole_book',
          theme: null,
          status: 'in_progress',
          tally: { got_it: 0, partial: 0, missed: 0, skipped: 0, discarded: 0 },
          created_at: '2026-05-10T15:00:00Z',
          updated_at: '2026-05-10T15:00:00Z',
        },
        first_question: {
          id: 100,
          session_id: 7,
          ordinal: 1,
          question: 'Q?',
          rationale: null,
          answer: null,
          self_assessment: null,
          discarded: false,
          created_at: '2026-05-10T15:00:00Z',
        },
      } as never)

    await expect(quiz.startSession(1, 'whole_book', null)).rejects.toBeInstanceOf(ApiError)
    expect(ui.toasts).toHaveLength(1)
    const onClick = ui.toasts[0].action!.onClick

    await onClick()

    expect(spy).toHaveBeenCalledTimes(2)
    expect(ui.toasts).toHaveLength(0)
    expect(quiz.inlineDiagnostic).toBeNull()
  })
})
