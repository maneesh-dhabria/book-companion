import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import { useQuizSessionsStore } from '@/stores/quizSessions'
import { useUiStore } from '@/stores/ui'
import { ApiError } from '@/api/client'
import * as api from '@/api/quizSessions'

describe('quizSessions mid-session error flow (FR-06)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  function seedActive(quiz: ReturnType<typeof useQuizSessionsStore>): void {
    const state = quiz.byBook.get(1) ?? null
    if (state) return
    quiz.byBook.set(1, {
      sessions: [],
      lifetimeTally: {
        total_questions: 0,
        got_it: 0,
        partial: 0,
        missed: 0,
        session_count: 0,
        themes_summary: null,
      },
      themesSummary: null,
      activeSession: {
        id: 7,
        book_id: 1,
        scope: { mode: 'whole_book', section_ids: null },
        theme: null,
        status: 'in_progress',
        tally: { got_it: 0, partial: 0, missed: 0, skipped: 0, discarded: 0 },
        created_at: 't',
        updated_at: 't',
      } as never,
      currentQuestion: {
        id: 100,
        session_id: 7,
        ordinal: 1,
        question: 'Q1?',
        rationale: null,
        answer: null,
        self_assessment: null,
        discarded: false,
        created_at: 't',
      } as never,
      loading: false,
      loaded: true,
    })
  }

  it('loadNextQuestion 502 → midSessionError populated, no toast, session preserved', async () => {
    const quiz = useQuizSessionsStore()
    const ui = useUiStore()
    seedActive(quiz)
    const beforeQ = quiz.byBook.get(1)!.currentQuestion
    vi.spyOn(api, 'nextQuestion').mockRejectedValueOnce(
      new ApiError(502, { detail: 'next-q boom', llm_stderr_tail: 'tail' }),
    )

    await expect(quiz.loadNextQuestion(1)).rejects.toBeInstanceOf(ApiError)

    expect(ui.toasts).toHaveLength(0)
    expect(quiz.midSessionError).not.toBeNull()
    expect(quiz.midSessionError?.message).toBe('next-q boom')
    expect(quiz.byBook.get(1)!.currentQuestion).toBe(beforeQ)
    expect(quiz.byBook.get(1)!.activeSession).not.toBeNull()
  })

  it('retryMidSession invokes the failed action and clears the error on success', async () => {
    const quiz = useQuizSessionsStore()
    seedActive(quiz)
    const spy = vi
      .spyOn(api, 'nextQuestion')
      .mockRejectedValueOnce(new ApiError(502, { detail: 'boom' }))
      .mockResolvedValueOnce({
        question: {
          id: 101,
          session_id: 7,
          ordinal: 2,
          question: 'Q2?',
          rationale: null,
          answer: null,
          self_assessment: null,
          discarded: false,
          created_at: 't',
        },
      } as never)

    await expect(quiz.loadNextQuestion(1)).rejects.toBeInstanceOf(ApiError)
    expect(quiz.midSessionError).not.toBeNull()

    await quiz.retryMidSession!()

    expect(spy).toHaveBeenCalledTimes(2)
    expect(quiz.midSessionError).toBeNull()
    expect(quiz.byBook.get(1)!.currentQuestion!.id).toBe(101)
  })
})
