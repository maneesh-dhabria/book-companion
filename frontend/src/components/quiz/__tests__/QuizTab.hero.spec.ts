import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import QuizTab from '../QuizTab.vue'

vi.mock('@/api/settings', () => ({
  getLlmStatus: vi.fn().mockResolvedValue({ preflight: { ok: true } }),
}))
vi.mock('@/api/readingState', () => ({
  getReadingStateByBook: vi.fn().mockResolvedValue({ most_recent_section_ids: [] }),
}))

describe('QuizTab hero copy (FR-20 / D14)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  async function mountTab() {
    const wrapper = mount(QuizTab, {
      props: { bookId: 1, hasSummaries: true, sections: [] },
      global: {
        stubs: {
          ResumeBanner: true,
          ActiveSession: true,
          ThemesCoveredPanel: true,
          PastQAPanel: true,
          InlineDiagnostic: true,
          ChapterMultiSelect: true,
          ThemeInput: true,
          BudgetBar: true,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  it('renders H2 "Test your retention" + paragraph with key cadence phrases', async () => {
    const wrapper = await mountTab()
    const h2 = wrapper.find('header.quiz-hero h2')
    expect(h2.exists()).toBe(true)
    expect(h2.text()).toBe('Test your retention')
    const p = wrapper.find('header.quiz-hero p')
    expect(p.text()).toContain('one question at a time')
    expect(p.text()).toContain('~10 sec')
    expect(p.text()).toContain('Got it / Partial / Missed')
  })

  it('microcopy near Start contains the cadence summary', async () => {
    const wrapper = await mountTab()
    const micro = wrapper.find('[data-test="quiz-microcopy"]')
    expect(micro.exists()).toBe(true)
    expect(micro.text()).toBe(
      'One question at a time · ~10 sec to generate · scored Got it / Partial / Missed',
    )
  })

  it('does not emit data-state="error" on confirming/toggled/recovered surfaces', async () => {
    const wrapper = await mountTab()
    const errorStates = wrapper.findAll('[data-state="error"]')
    expect(errorStates).toHaveLength(0)
  })
})
