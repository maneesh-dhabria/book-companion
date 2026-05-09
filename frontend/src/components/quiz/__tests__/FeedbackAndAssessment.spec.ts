import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import FeedbackPanel from '@/components/quiz/FeedbackPanel.vue'
import SelfAssessmentButtons from '@/components/quiz/SelfAssessmentButtons.vue'
import OverrideAffordance from '@/components/quiz/OverrideAffordance.vue'
import FatiguePromptBanner from '@/components/quiz/FatiguePromptBanner.vue'
import { COPY } from '@/components/quiz/copy'
import { useQuizSessionsStore } from '@/stores/quizSessions'

vi.mock('@/api/quizSessions', () => ({
  recordSelfAssessment: vi.fn(),
  overrideQuestion: vi.fn(),
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('FeedbackPanel', () => {
  it('renders 3 distinct sections (correct / missing / actual)', () => {
    const wrapper = mount(FeedbackPanel, {
      props: { feedback: { correct: 'A', missing: 'B', actual: 'C' } },
    })
    const fields = wrapper.findAll('[data-test="feedback-field"]')
    expect(fields.length).toBe(3)
    expect(wrapper.text()).toContain('A')
    expect(wrapper.text()).toContain('B')
    expect(wrapper.text()).toContain('C')
  })

  it('hides when feedback is null', () => {
    const wrapper = mount(FeedbackPanel, { props: { feedback: null } })
    expect(wrapper.find('[data-test="feedback-panel"]').exists()).toBe(false)
  })
})

describe('SelfAssessmentButtons', () => {
  it('calls store.recordSelfAssessment on click', async () => {
    const store = useQuizSessionsStore()
    const spy = vi.spyOn(store, 'recordSelfAssessment').mockResolvedValue()
    const wrapper = mount(SelfAssessmentButtons, {
      props: { bookId: 1, disabled: false, isFirstSession: true },
    })
    await wrapper.find('button[data-test="sa-got_it"]').trigger('click')
    expect(spy).toHaveBeenCalledWith(1, 'got_it')
  })

  it('renders microcopy on first session', () => {
    const wrapper = mount(SelfAssessmentButtons, {
      props: { bookId: 1, disabled: false, isFirstSession: true },
    })
    expect(wrapper.text()).toContain(COPY.selfAssessmentMicrocopy)
  })

  it('hides microcopy after first session', () => {
    const wrapper = mount(SelfAssessmentButtons, {
      props: { bookId: 1, disabled: false, isFirstSession: false },
    })
    expect(wrapper.text()).not.toContain(COPY.selfAssessmentMicrocopy)
  })

  it('renders three buttons in order: Got it / Partial / Missed', () => {
    const wrapper = mount(SelfAssessmentButtons, {
      props: { bookId: 1, disabled: false, isFirstSession: false },
    })
    const labels = wrapper
      .findAll('button[data-test^="sa-"]')
      .map((b) => b.text())
    expect(labels).toEqual(['Got it', 'Partial', 'Missed'])
  })

  it('disables all buttons when disabled prop is true', () => {
    const wrapper = mount(SelfAssessmentButtons, {
      props: { bookId: 1, disabled: true, isFirstSession: false },
    })
    wrapper.findAll('button[data-test^="sa-"]').forEach((b) => {
      expect(b.attributes('disabled')).toBeDefined()
    })
  })
})

describe('OverrideAffordance', () => {
  it('clamps text at 500 chars (E23)', async () => {
    const wrapper = mount(OverrideAffordance, {
      props: { sessionId: 1, questionId: 1 },
    })
    await wrapper.find('button[data-test="override-toggle"]').trigger('click')
    const ta = wrapper.find('textarea[data-test="override-textarea"]')
    const longInput = 'x'.repeat(600)
    await ta.setValue(longInput)
    expect((ta.element as HTMLTextAreaElement).value.length).toBeLessThanOrEqual(500)
  })

  it('exposes character counter (FR-54 / E23 visual cue)', async () => {
    const wrapper = mount(OverrideAffordance, {
      props: { sessionId: 1, questionId: 1 },
    })
    await wrapper.find('button[data-test="override-toggle"]').trigger('click')
    await wrapper.find('textarea[data-test="override-textarea"]').setValue('hello')
    expect(wrapper.find('[data-test="override-counter"]').text()).toContain('5 / 500')
  })

  it('does NOT alter self_assessment when saved (FR-54 / E13)', async () => {
    const store = useQuizSessionsStore()
    const saSpy = vi.spyOn(store, 'recordSelfAssessment').mockResolvedValue()
    const api = await import('@/api/quizSessions')
    vi.mocked(api.overrideQuestion).mockResolvedValue({
      id: 1,
      session_id: 1,
      book_id: 1,
      stem: 's',
      concept_label: 'c',
      citation: { section_id: 1, section_title: 't', snippet: 'x' },
      shape: 'open',
      bloom_level: 'understand',
      mcq_options: null,
      intended_error: null,
      error_explanation: null,
      user_answer: null,
      feedback: null,
      self_assessment: null,
      override_note: 'note',
      explain_history: [],
      skip_count: 0,
      discarded: false,
      warm_up: false,
      is_pregen: false,
      is_stale: false,
      created_at: 'now',
    })
    const wrapper = mount(OverrideAffordance, {
      props: { sessionId: 1, questionId: 1 },
    })
    await wrapper.find('button[data-test="override-toggle"]').trigger('click')
    await wrapper.find('textarea[data-test="override-textarea"]').setValue('agent was wrong')
    await wrapper.find('button[data-test="override-save"]').trigger('click')
    await flushPromises()
    expect(api.overrideQuestion).toHaveBeenCalledWith(1, 1, 'agent was wrong')
    expect(saSpy).not.toHaveBeenCalled()
  })
})

describe('FatiguePromptBanner', () => {
  it('appears when feedback.actual contains the verbatim clause', () => {
    const fb = {
      correct: 'x',
      missing: 'y',
      actual: 'Per Ch 1, ... Want to keep going or wrap up here?',
    }
    const wrapper = mount(FatiguePromptBanner, { props: { feedback: fb } })
    expect(wrapper.find('[data-test="fatigue-banner"]').exists()).toBe(true)
  })

  it('is hidden when clause absent', () => {
    const fb = { correct: 'x', missing: 'y', actual: 'no clause here' }
    const wrapper = mount(FatiguePromptBanner, { props: { feedback: fb } })
    expect(wrapper.find('[data-test="fatigue-banner"]').exists()).toBe(false)
  })

  it('is hidden when feedback is null', () => {
    const wrapper = mount(FatiguePromptBanner, { props: { feedback: null } })
    expect(wrapper.find('[data-test="fatigue-banner"]').exists()).toBe(false)
  })
})
