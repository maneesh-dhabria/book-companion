import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SectionListTable from '../SectionListTable.vue'
import { useSummarizationJobStore } from '@/stores/summarizationJob'

const sections = [
  {
    id: 1,
    title: 'Intro',
    order_index: 0,
    section_type: 'frontmatter',
    content_char_count: 1000,
    has_summary: true,
    default_summary: { summary_char_count: 200 },
  },
  {
    id: 2,
    title: 'Chapter 1',
    order_index: 1,
    section_type: 'chapter',
    content_char_count: 5000,
    has_summary: true,
    default_summary: { summary_char_count: 800 },
  },
  {
    id: 3,
    title: 'Chapter 2',
    order_index: 2,
    section_type: 'chapter',
    content_char_count: 4000,
    has_summary: false,
  },
]

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/books/:id/sections/:sectionId',
        name: 'section-detail',
        component: { template: '<div/>' },
      },
    ],
  })
}

describe('SectionListTable', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders all 6 columns in default mode', () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    const headers = wrapper.findAll('th').map((h) => h.text())
    expect(headers).toEqual(['#', 'Title', 'Type', 'Chars', 'Summary', 'Compression'])
  })

  it('hides Type and Compression in compact mode', () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true },
      global: { plugins: [makeRouter()] },
    })
    const headers = wrapper.findAll('th').map((h) => h.text())
    expect(headers).not.toContain('Type')
    expect(headers).not.toContain('Compression')
    expect(headers).toContain('Title')
  })

  it('formats compression as ~N% rounded to 5 (FR-05)', () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    expect(wrapper.html()).toContain('~15%')
  })

  it('shows em-dash when no summary', () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    const rows = wrapper.findAll('tbody tr[role="link"]')
    expect(rows[2].text()).toMatch(/—/)
  })

  it('shows em-dash when content_char_count is 0', () => {
    const wrapper = mount(SectionListTable, {
      props: {
        sections: [
          {
            id: 4,
            title: 'Empty',
            order_index: 0,
            section_type: 'chapter',
            content_char_count: 0,
            has_summary: true,
            default_summary: { summary_char_count: 100 },
          },
        ],
        bookId: 1,
        compact: false,
      },
      global: { plugins: [makeRouter()] },
    })
    expect(wrapper.text()).toContain('—')
  })

  it('renders separator row between section_type changes', () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    expect(wrapper.findAll('tr.section-type-separator').length).toBe(1)
  })

  it('keyboard nav: focusing first row + ArrowDown moves to next', async () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      attachTo: document.body,
      global: { plugins: [makeRouter()] },
    })
    const rows = wrapper.findAll('tr[role="link"]')
    ;(rows[0].element as HTMLElement).focus()
    await rows[0].trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(rows[1].element)
    wrapper.unmount()
  })

  it('row click navigates with ?tab preserved when called from reader-TOC context', async () => {
    const router = makeRouter()
    await router.push({ path: '/books/1/sections/1', query: { tab: 'summary' } })
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true, currentSectionId: 1 },
      global: { plugins: [router] },
    })
    const rows = wrapper.findAll('tr[role="link"]')
    await rows[1].trigger('click')
    expect(router.currentRoute.value.fullPath).toContain('tab=summary')
  })

  it('flips Summary cell to ✓ on section_completed event in non-compact mode', async () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    const jobStore = useSummarizationJobStore()
    jobStore.lastEvent = {
      event: 'section_completed',
      data: { section_id: 3 },
    }
    await wrapper.vm.$nextTick()
    const row = wrapper.findAll('tbody tr[role="link"]').at(2)!
    expect(row.html()).toContain('✓')
  })

  it('compact mode does NOT subscribe to SSE updates', async () => {
    const wrapper = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true },
      global: { plugins: [makeRouter()] },
    })
    const jobStore = useSummarizationJobStore()
    jobStore.lastEvent = {
      event: 'section_completed',
      data: { section_id: 3 },
    }
    await wrapper.vm.$nextTick()
    const row = wrapper.findAll('tbody tr[role="link"]').at(2)!
    expect(row.text()).toContain('—')
  })
})
