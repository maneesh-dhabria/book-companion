import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import SkipButton from '@/components/quiz/SkipButton.vue'
import ExplainAffordance from '@/components/quiz/ExplainAffordance.vue'
import AlreadyAskedLink from '@/components/quiz/AlreadyAskedLink.vue'
import { COPY } from '@/components/quiz/copy'
import type { QuizQuestion } from '@/types'

vi.mock('@/api/quizSessions', () => ({
  skipQuestion: vi.fn(),
  explainQuestion: vi.fn(),
  discardQuestion: vi.fn(),
}))

const baseQ: QuizQuestion = {
  id: 1,
  session_id: 1,
  book_id: 1,
  stem: 'stem',
  concept_label: 'c',
  citation: { section_id: 1, section_title: 't', snippet: 's' },
  shape: 'open',
  bloom_level: 'understand',
  mcq_options: null,
  intended_error: null,
  error_explanation: null,
  user_answer: null,
  feedback: null,
  self_assessment: null,
  override_note: null,
  explain_history: [],
  skip_count: 0,
  discarded: false,
  warm_up: false,
  is_pregen: false,
  is_stale: false,
  created_at: '2026-05-09T00:00:00Z',
}

beforeEach(() => {
  // No global pinia needed; components call api directly.
})
afterEach(() => vi.clearAllMocks())

describe('SkipButton', () => {
  it('disables on click and re-enables after response (FR-49)', async () => {
    const api = await import('@/api/quizSessions')
    let resolve!: (v: QuizQuestion) => void
    vi.mocked(api.skipQuestion).mockReturnValue(
      new Promise<QuizQuestion>((r) => {
        resolve = r
      }),
    )
    const wrapper = mount(SkipButton, {
      props: { sessionId: 1, questionId: 1 },
    })
    const btn = wrapper.find('button[data-test="skip"]')
    expect(btn.attributes('disabled')).toBeUndefined()
    await btn.trigger('click')
    expect(btn.attributes('disabled')).toBeDefined()
    resolve(baseQ)
    await flushPromises()
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('emits skipped on success', async () => {
    const api = await import('@/api/quizSessions')
    vi.mocked(api.skipQuestion).mockResolvedValue(baseQ)
    const wrapper = mount(SkipButton, {
      props: { sessionId: 1, questionId: 1 },
    })
    await wrapper.find('button[data-test="skip"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('skipped')).toBeTruthy()
  })
})

describe('ExplainAffordance', () => {
  it('stacks all explanations above the question card (FR-46a)', () => {
    const wrapper = mount(ExplainAffordance, {
      props: {
        sessionId: 1,
        question: { ...baseQ, explain_history: ['First clarification.', 'Second clarification.'] },
      },
    })
    const stack = wrapper.findAll('[data-test="explain-history-item"]')
    expect(stack.length).toBe(2)
    expect(stack[0].text()).toContain('First clarification.')
    expect(stack[1].text()).toContain('Second clarification.')
  })

  it('prefixes each entry with "Clarification:"', () => {
    const wrapper = mount(ExplainAffordance, {
      props: { sessionId: 1, question: { ...baseQ, explain_history: ['hello'] } },
    })
    expect(wrapper.text()).toContain('Clarification:')
  })

  it('replaces button with "Try answering or Skip" after 2 hits', () => {
    const wrapper = mount(ExplainAffordance, {
      props: { sessionId: 1, question: { ...baseQ, explain_history: ['a', 'b'] } },
    })
    expect(wrapper.find('button[data-test="explain"]').exists()).toBe(false)
    expect(wrapper.text()).toContain(COPY.explainSoftCap)
  })

  it('calls explainQuestion on click and emits explained', async () => {
    const api = await import('@/api/quizSessions')
    vi.mocked(api.explainQuestion).mockResolvedValue({
      explanation: 'because',
      question: { ...baseQ, explain_history: ['because'] },
    })
    const wrapper = mount(ExplainAffordance, {
      props: { sessionId: 1, question: baseQ },
    })
    await wrapper.find('button[data-test="explain"]').trigger('click')
    await flushPromises()
    expect(api.explainQuestion).toHaveBeenCalledWith(1, 1)
    expect(wrapper.emitted('explained')).toBeTruthy()
  })
})

describe('AlreadyAskedLink', () => {
  it('shows tooltip on first session-hover only (uses sessionStorage)', async () => {
    sessionStorage.removeItem('quiz.alreadyAsked.tooltipSeen')
    const wrapper = mount(AlreadyAskedLink, {
      props: { sessionId: 1, questionId: 1 },
    })
    await wrapper.find('a[data-test="already-asked"]').trigger('mouseenter')
    expect(wrapper.find('[data-test="already-asked-tooltip"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(COPY.alreadyAskedTooltip)
  })

  it('does NOT show tooltip when already-seen flag is set', async () => {
    sessionStorage.setItem('quiz.alreadyAsked.tooltipSeen', '1')
    const wrapper = mount(AlreadyAskedLink, {
      props: { sessionId: 1, questionId: 1 },
    })
    await wrapper.find('a[data-test="already-asked"]').trigger('mouseenter')
    expect(wrapper.find('[data-test="already-asked-tooltip"]').exists()).toBe(false)
  })

  it('click calls discardQuestion and emits discarded with replacement', async () => {
    const api = await import('@/api/quizSessions')
    const replacement = { ...baseQ, id: 99 }
    vi.mocked(api.discardQuestion).mockResolvedValue({
      question: { ...baseQ, discarded: true },
      replacement,
    })
    const wrapper = mount(AlreadyAskedLink, {
      props: { sessionId: 1, questionId: 1 },
    })
    await wrapper.find('a[data-test="already-asked"]').trigger('click')
    await flushPromises()
    expect(api.discardQuestion).toHaveBeenCalledWith(1, 1)
    const events = wrapper.emitted('discarded')
    expect(events).toBeTruthy()
    expect(events![0][0]).toMatchObject({ replacement: { id: 99 } })
  })
})
