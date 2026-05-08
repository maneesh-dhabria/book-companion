import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ name: 'home', meta: {}, params: {} }),
  RouterLink: { template: '<a><slot /></a>' },
}))

import TopBar from '@/components/app/TopBar.vue'
import ReaderHeader from '@/components/reader/ReaderHeader.vue'
import type { Section } from '@/types'

const stubs = { 'router-link': { template: '<a><slot /></a>' } }

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('h1 hierarchy (FR-B08, FR-B09, FR-B10)', () => {
  it('TopBar renders zero h1 elements (demoted to span)', () => {
    const wrapper = mount(TopBar, {
      global: { stubs },
    })
    expect(wrapper.findAll('h1')).toHaveLength(0)
    expect(wrapper.find('span.top-bar-title').exists()).toBe(true)
  })

  it('ReaderHeader renders exactly one h1 with the current section title', () => {
    const sections: Section[] = [
      // @ts-expect-error — minimal Section shape for the test
      { id: 1, title: 'Intro', section_type: 'introduction', order_index: 0 },
      // @ts-expect-error
      { id: 2, title: 'Chapter One', section_type: 'chapter', order_index: 1 },
    ]
    const wrapper = mount(ReaderHeader, {
      global: { stubs: { ...stubs, ContentToggle: true, SectionTagRow: true, TOCDropdown: true } },
      props: {
        bookTitle: 'Test Book',
        bookId: 1,
        sections,
        currentSectionId: 2,
        contentMode: 'original',
        hasSummary: false,
        hasPrev: true,
        hasNext: false,
      },
    })
    const h1s = wrapper.findAll('h1')
    expect(h1s).toHaveLength(1)
    expect(h1s[0].text()).toBe('Chapter One')
    expect(h1s[0].classes()).toContain('reader-h1')
  })

  it('ReaderHeader renders zero h1 when no current section is selected', () => {
    const wrapper = mount(ReaderHeader, {
      global: { stubs: { ...stubs, ContentToggle: true, SectionTagRow: true, TOCDropdown: true } },
      props: {
        bookTitle: 'Test Book',
        bookId: 1,
        sections: [],
        currentSectionId: null,
        contentMode: 'original',
        hasSummary: false,
        hasPrev: false,
        hasNext: false,
      },
    })
    expect(wrapper.findAll('h1')).toHaveLength(0)
  })
})
