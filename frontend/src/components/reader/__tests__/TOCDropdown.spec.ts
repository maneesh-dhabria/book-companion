import type { Section } from '@/types'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TOCDropdown from '../TOCDropdown.vue'

const mkSections = (): Section[] =>
  [
    {
      id: 1,
      order_index: 0,
      title: 'Copyright',
      section_type: 'copyright',
      has_summary: false,
    },
    {
      id: 2,
      order_index: 1,
      title: 'Acknowledgments',
      section_type: 'acknowledgments',
      has_summary: false,
    },
    {
      id: 3,
      order_index: 2,
      title: 'Chapter 1',
      section_type: 'chapter',
      has_summary: true,
    },
    {
      id: 4,
      order_index: 3,
      title: 'Chapter 2',
      section_type: 'chapter',
      has_summary: false,
    },
    {
      id: 5,
      order_index: 4,
      title: 'Glossary',
      section_type: 'glossary',
      has_summary: false,
    },
  ] as unknown as Section[]

const makeOptions = () => ({
  global: {
    stubs: { 'router-link': { template: '<a><slot /></a>' } },
    directives: { 'click-outside': () => {} },
  },
})

describe('TOCDropdown Front Matter accordion', () => {
  it('renders front-matter inside <details>', async () => {
    const wrapper = mount(TOCDropdown, {
      props: { sections: mkSections(), currentSectionId: 3, bookId: 1 },
      ...makeOptions(),
    })
    await wrapper.find('.toc-trigger').trigger('click')
    const details = wrapper.find('details')
    expect(details.exists()).toBe(true)
    expect(details.find('summary').text()).toMatch(/Front Matter \(2\)/)
    expect(details.attributes('open')).toBeUndefined()
  })

  it('places glossary (late) outside Front Matter bucket', async () => {
    const wrapper = mount(TOCDropdown, {
      props: { sections: mkSections(), currentSectionId: 3, bookId: 1 },
      ...makeOptions(),
    })
    await wrapper.find('.toc-trigger').trigger('click')
    const bodyItems = wrapper.findAll('.toc-list > .toc-item')
    const bodyTitles = bodyItems.map((i) => i.find('.toc-title').text())
    expect(bodyTitles).toContain('Glossary')
    expect(bodyTitles).not.toContain('Copyright')
  })
})
