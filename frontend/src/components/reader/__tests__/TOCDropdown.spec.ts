import type { Section } from '@/types'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import TOCDropdown from '../TOCDropdown.vue'

const mkSections = (): Section[] =>
  [
    { id: 1, order_index: 0, title: 'Copyright', section_type: 'copyright', has_summary: false },
    {
      id: 2,
      order_index: 1,
      title: 'Acknowledgments',
      section_type: 'acknowledgments',
      has_summary: false,
    },
    { id: 3, order_index: 2, title: 'Chapter 1', section_type: 'chapter', has_summary: true },
    { id: 4, order_index: 3, title: 'Chapter 2', section_type: 'chapter', has_summary: false },
    { id: 5, order_index: 4, title: 'Glossary', section_type: 'glossary', has_summary: false },
  ] as unknown as Section[]

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/books/:id/sections/:sectionId', name: 'section-detail', component: { template: '<div/>' } },
    ],
  })
}

const makeOptions = () => ({
  global: {
    plugins: [createPinia(), makeRouter()],
    directives: { 'click-outside': () => {} },
  },
})

describe('TOCDropdown', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('uses SectionListTable in compact mode', async () => {
    const wrapper = mount(TOCDropdown, {
      props: { sections: mkSections(), currentSectionId: 3, bookId: 1 },
      ...makeOptions(),
    })
    await wrapper.find('.toc-trigger').trigger('click')
    const table = wrapper.findComponent({ name: 'SectionListTable' })
    expect(table.exists()).toBe(true)
    expect(table.props('compact')).toBe(true)
    expect(table.props('currentSectionId')).toBe(3)
  })

  it('renders read time (not raw char count) for non-empty sections in compact mode', async () => {
    const sections = [
      {
        id: 1,
        order_index: 0,
        title: 'Ch 1',
        section_type: 'chapter',
        has_summary: false,
        content_char_count: 1234,
      },
      {
        id: 2,
        order_index: 1,
        title: 'Ch 2',
        section_type: 'chapter',
        has_summary: false,
        content_char_count: 5678,
      },
    ] as unknown as Section[]
    const wrapper = mount(TOCDropdown, {
      props: { sections, currentSectionId: 1, bookId: 1 },
      ...makeOptions(),
    })
    await wrapper.find('.toc-trigger').trigger('click')
    const text = wrapper.text()
    // T18: content_char_count column was replaced with formatReadTime.
    // 1234 / 1100 cpm = 2 min (ceil); 5678 / 1100 = 6 min (ceil).
    expect(text).toContain('2 min')
    expect(text).toContain('6 min')
  })

  it('search input filters the list passed to SectionListTable', async () => {
    const wrapper = mount(TOCDropdown, {
      props: { sections: mkSections(), currentSectionId: 3, bookId: 1 },
      ...makeOptions(),
    })
    await wrapper.find('.toc-trigger').trigger('click')
    await wrapper.find('.toc-search').setValue('Glossary')
    const table = wrapper.findComponent({ name: 'SectionListTable' })
    const filtered = table.props('sections') as Section[]
    expect(filtered.map((s) => s.title)).toEqual(['Glossary'])
  })
})
