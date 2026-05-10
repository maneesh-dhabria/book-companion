import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import ActiveSession from '../ActiveSession.vue'
import { useQuizSessionsStore } from '@/stores/quizSessions'
import { useUiStore } from '@/stores/ui'
import * as api from '@/api/quizSessions'
import { ApiError } from '@/api/client'

function seedActive(quiz: ReturnType<typeof useQuizSessionsStore>): void {
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

describe('ActiveSession mid-session retry (FR-06)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('shows inline error block with Retry button after a 502; click recovers', async () => {
    const quiz = useQuizSessionsStore()
    const ui = useUiStore()
    seedActive(quiz)

    vi.spyOn(api, 'nextQuestion')
      .mockRejectedValueOnce(new ApiError(502, { detail: 'next-q boom' }))
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

    const wrapper = mount(ActiveSession, {
      props: { bookId: 1, bookSlug: 'b' },
      global: {
        stubs: {
          Teleport: true,
          SessionTally: true,
          WarmUpBanner: true,
          ExplainAffordance: true,
          QuestionTurn: true,
          FatiguePromptBanner: true,
          FeedbackPanel: true,
          SelfAssessmentButtons: true,
          OverrideAffordance: true,
          SkipButton: true,
          AlreadyAskedLink: true,
          SessionEndActions: true,
          LoadingSpinner: true,
        },
      },
    })

    await expect(quiz.loadNextQuestion(1)).rejects.toBeInstanceOf(ApiError)
    await flushPromises()

    const errBlock = wrapper.find('[data-testid="mid-session-error"]')
    expect(errBlock.exists()).toBe(true)
    expect(errBlock.text()).toContain('next-q boom')
    expect(ui.toasts).toHaveLength(0)
    expect(quiz.byBook.get(1)!.activeSession).not.toBeNull()

    await errBlock.find('button[data-action="retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="mid-session-error"]').exists()).toBe(false)
    expect(quiz.byBook.get(1)!.currentQuestion!.id).toBe(101)
  })
})
