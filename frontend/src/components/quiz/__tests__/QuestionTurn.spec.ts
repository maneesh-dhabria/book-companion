import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, afterEach } from 'vitest'
import QuestionTurn from '@/components/quiz/QuestionTurn.vue'
import LoadingSpinner from '@/components/quiz/LoadingSpinner.vue'
import { COPY } from '@/components/quiz/copy'
import type { QuizQuestion } from '@/types'

const baseQuestion: Omit<QuizQuestion, 'shape'> = {
  id: 1,
  session_id: 1,
  book_id: 1,
  stem: 'What is loss aversion?',
  concept_label: 'loss aversion',
  citation: { section_id: 5, section_title: 'Chapter 1', snippet: 'A snippet…' },
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

const mcqQuestion: QuizQuestion = {
  ...baseQuestion,
  shape: 'mcq',
  mcq_options: ['A', 'B', 'C', 'D'],
}

const openQuestion: QuizQuestion = { ...baseQuestion, shape: 'open' }

const spotErrorQuestion: QuizQuestion = {
  ...baseQuestion,
  shape: 'spot_error',
  intended_error:
    "People feel gains exactly as strongly as equivalent losses, all else being equal.",
  error_explanation: 'Loss aversion implies losses are felt ~2x stronger.',
}

afterEach(() => {
  vi.useRealTimers()
})

describe('QuestionTurn', () => {
  it('renders MCQ with 4 stacked buttons', () => {
    const wrapper = mount(QuestionTurn, { props: { question: mcqQuestion } })
    expect(wrapper.findAll('button[data-test="mcq-option"]').length).toBe(4)
  })

  it('renders open-ended autosize textarea', () => {
    const wrapper = mount(QuestionTurn, { props: { question: openQuestion } })
    expect(wrapper.find('textarea[data-test="open-input"]').exists()).toBe(true)
  })

  it('renders spot-error wrong-restatement callout + correction textarea', () => {
    const wrapper = mount(QuestionTurn, { props: { question: spotErrorQuestion } })
    expect(wrapper.find('[data-test="intended-error-callout"]').text()).toContain(
      'gains exactly as strongly as equivalent losses',
    )
    expect(wrapper.find('textarea[data-test="correction-input"]').exists()).toBe(true)
  })

  it('shows citation chip alongside question for open shape (FR-41)', () => {
    const wrapper = mount(QuestionTurn, { props: { question: openQuestion } })
    expect(wrapper.find('[data-test="citation-chip"]').exists()).toBe(true)
  })

  it('hides citation chip until after-answer for mcq (FR-41)', () => {
    const wrapper = mount(QuestionTurn, { props: { question: mcqQuestion } })
    expect(wrapper.find('[data-test="citation-chip"]').exists()).toBe(false)
  })

  it('hides citation chip until after-answer for spot_error (FR-41)', () => {
    const wrapper = mount(QuestionTurn, { props: { question: spotErrorQuestion } })
    expect(wrapper.find('[data-test="citation-chip"]').exists()).toBe(false)
  })

  it('shows citation chip after-answer for mcq when feedback is present', () => {
    const answered: QuizQuestion = {
      ...mcqQuestion,
      user_answer: 'A',
      feedback: { correct: 'x', missing: 'y', actual: 'z' },
    }
    const wrapper = mount(QuestionTurn, { props: { question: answered } })
    expect(wrapper.find('[data-test="citation-chip"]').exists()).toBe(true)
  })

  it('renders LoadingSpinner with verbatim "Reading the book to draft your question…" via copy prop', () => {
    const wrapper = mount(LoadingSpinner, {
      props: { copy: COPY.loadingQuestion },
    })
    expect(wrapper.text()).toContain(COPY.loadingQuestion)
    expect(wrapper.find('[data-test="loading-spinner"]').exists()).toBe(true)
  })

  it('Submit button disabled until input meets shape rules — open (FR-48)', async () => {
    const wrapper = mount(QuestionTurn, { props: { question: openQuestion } })
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.find('textarea[data-test="open-input"]').setValue('answer')
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('Submit button disabled until input meets shape rules — mcq (FR-48)', async () => {
    const wrapper = mount(QuestionTurn, { props: { question: mcqQuestion } })
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.findAll('button[data-test="mcq-option"]')[1].trigger('click')
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('Submit button disabled until input meets shape rules — spot_error (FR-48)', async () => {
    const wrapper = mount(QuestionTurn, { props: { question: spotErrorQuestion } })
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.find('textarea[data-test="correction-input"]').setValue('correct version')
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('Submit button disabled-on-click with 5s fallback re-enable (FR-49)', async () => {
    vi.useFakeTimers()
    const wrapper = mount(QuestionTurn, { props: { question: openQuestion } })
    await wrapper.find('textarea[data-test="open-input"]').setValue('x')
    await wrapper.find('button[data-test="submit"]').trigger('click')
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeDefined()
    vi.advanceTimersByTime(5000)
    await flushPromises()
    expect(wrapper.find('button[data-test="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('emits submit with shape-specific payload for open', async () => {
    const wrapper = mount(QuestionTurn, { props: { question: openQuestion } })
    await wrapper.find('textarea[data-test="open-input"]').setValue('my answer')
    await wrapper.find('button[data-test="submit"]').trigger('click')
    const events = wrapper.emitted('submit')
    expect(events).toBeTruthy()
    expect(events![0][0]).toMatchObject({ user_answer: 'my answer' })
  })

  it('emits submit with mcq selected option index', async () => {
    const wrapper = mount(QuestionTurn, { props: { question: mcqQuestion } })
    await wrapper.findAll('button[data-test="mcq-option"]')[2].trigger('click')
    await wrapper.find('button[data-test="submit"]').trigger('click')
    const events = wrapper.emitted('submit')
    expect(events).toBeTruthy()
    expect(events![0][0]).toMatchObject({ user_answer: 'C' })
  })
})
