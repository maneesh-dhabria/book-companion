import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SummaryEmptyState from '../SummaryEmptyState.vue'

const chapter = { id: 5, title: 'Chapter 1', section_type: 'chapter' }
const copyright = { id: 6, title: 'Copyright', section_type: 'copyright' }

describe('SummaryEmptyState', () => {
  it('front-matter renders "not applicable"', () => {
    const w = mount(SummaryEmptyState, {
      props: { section: copyright, activeJobSectionId: null, failedError: null },
    })
    expect(w.text()).toMatch(/Summary not applicable for Copyright/)
    expect(w.find('button').exists()).toBe(false)
  })

  it('summarizable without summary renders CTA', () => {
    const w = mount(SummaryEmptyState, {
      props: { section: chapter, activeJobSectionId: null, failedError: null },
    })
    expect(w.text()).toMatch(/Not yet summarized/)
    const btn = w.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toMatch(/Summarize this section/)
  })

  it('renders generating state when activeJobSectionId matches', () => {
    const w = mount(SummaryEmptyState, {
      props: { section: chapter, activeJobSectionId: 5, failedError: null },
    })
    expect(w.text()).toMatch(/Generating summary/)
    expect(w.find('button').exists()).toBe(false)
  })

  it('renders failure + Retry button when failedError present', () => {
    const w = mount(SummaryEmptyState, {
      props: {
        section: chapter,
        activeJobSectionId: null,
        failedError: 'LLM timeout',
      },
    })
    expect(w.text()).toMatch(/Summary generation failed: LLM timeout/)
    expect(w.find('button').text()).toMatch(/Retry/)
  })

  it('generating takes precedence over failure', () => {
    const w = mount(SummaryEmptyState, {
      props: {
        section: chapter,
        activeJobSectionId: 5,
        failedError: 'old error',
      },
    })
    expect(w.text()).toMatch(/Generating summary/)
  })

  it('CTA click emits summarize', async () => {
    const w = mount(SummaryEmptyState, {
      props: { section: chapter, activeJobSectionId: null, failedError: null },
    })
    await w.find('button').trigger('click')
    expect(w.emitted('summarize')).toBeTruthy()
  })
})
