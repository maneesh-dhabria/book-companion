import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SectionListTable from '../SectionListTable.vue'
import { useSummarizationJobStore } from '@/stores/summarizationJob'

const sections = [
  {
    id: 1,
    title: 'Copyright',
    order_index: 0,
    section_type: 'copyright',
    content_char_count: 1000,
    has_summary: false,
  },
  {
    id: 2,
    title: 'Chapter 1',
    order_index: 1,
    section_type: 'chapter',
    content_char_count: 22000,
    has_summary: true,
    default_summary: { summary_char_count: 800 },
  },
  {
    id: 3,
    title: 'Chapter 2',
    order_index: 2,
    section_type: 'chapter',
    content_char_count: 22000,
    has_summary: false,
  },
  {
    id: 4,
    title: 'Chapter 3',
    order_index: 3,
    section_type: 'chapter',
    content_char_count: 22000,
    has_summary: true,
    default_summary: { summary_char_count: 1000 },
  },
  {
    id: 5,
    title: 'Glossary',
    order_index: 4,
    section_type: 'glossary',
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

describe('SectionListTable (FR-C13..C16)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders the 4-column header set: # / Title / Read time / Summary', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    const headers = w.findAll('thead:first-of-type th').map((h) => h.text())
    expect(headers).toEqual(['#', 'Title', 'Read time', 'Summary'])
  })

  it('renders three group separators with correct labels', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    expect(w.find('[data-group="front"]').text()).toContain('Front matter')
    expect(w.find('[data-group="chapters"]').text()).toContain('Chapters')
    expect(w.find('[data-group="back"]').text()).toContain('Back matter')
  })

  it('chapters group expanded by default; front and back collapsed', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    expect(w.find('[data-group-body="chapters"]').exists()).toBe(true)
    expect(w.find('[data-group-body="front"]').exists()).toBe(false)
    expect(w.find('[data-group-body="back"]').exists()).toBe(false)
  })

  it('clicking a group separator toggles its expand state', async () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    await w.find('[data-group="front"]').trigger('click')
    expect(w.find('[data-group-body="front"]').exists()).toBe(true)
    await w.find('[data-group="front"]').trigger('click')
    expect(w.find('[data-group-body="front"]').exists()).toBe(false)
  })

  it('persists expand state via localStorage keyed on bookId', async () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 7, compact: false },
      global: { plugins: [makeRouter()] },
    })
    await w.find('[data-group="back"]').trigger('click')
    const saved = JSON.parse(localStorage.getItem('bc.sections.expand.7') ?? '{}')
    expect(saved.back).toBe(true)
    expect(saved.front).toBe(false)
    expect(saved.chapters).toBe(true)
  })

  it('renders read time using formatReadTime', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    // chapters group is expanded; 22000 chars / 1100 cpm = 20 min
    expect(w.find('[data-group-body="chapters"]').text()).toContain('20 min')
  })

  it('Summary cell shows ✓ when has_summary, ✕ otherwise', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    const rows = w.findAll('[data-group-body="chapters"] tr[role="link"]')
    expect(rows[0].text()).toContain('✓')
    expect(rows[1].text()).toContain('✕')
    expect(rows[2].text()).toContain('✓')
  })

  it('compact mode renders flat list (no group separators)', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true },
      global: { plugins: [makeRouter()] },
    })
    expect(w.findAll('[data-group]')).toHaveLength(0)
    expect(w.findAll('tbody tr[role="link"]')).toHaveLength(5)
  })

  it('row click navigates to section detail', async () => {
    const router = makeRouter()
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [router] },
    })
    const firstChapterRow = w.findAll('[data-group-body="chapters"] tr[role="link"]')[0]
    await firstChapterRow.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/books/1/sections/2')
  })

  it('preserves ?tab when called from reader-TOC context (currentSectionId set)', async () => {
    const router = makeRouter()
    await router.push({ path: '/books/1/sections/2', query: { tab: 'summary' } })
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true, currentSectionId: 2 },
      global: { plugins: [router] },
    })
    const rows = w.findAll('tbody tr[role="link"]')
    await rows[2].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toContain('tab=summary')
  })

  it('flips Summary cell to ✓ on section_completed event in non-compact mode', async () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: false },
      global: { plugins: [makeRouter()] },
    })
    const jobStore = useSummarizationJobStore()
    jobStore.lastEvent = {
      event: 'section_completed',
      data: { section_id: 3 },
    }
    await w.vm.$nextTick()
    const rows = w.findAll('[data-group-body="chapters"] tr[role="link"]')
    expect(rows[1].html()).toContain('✓')
  })

  it('compact mode does NOT subscribe to SSE updates', async () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true },
      global: { plugins: [makeRouter()] },
    })
    const jobStore = useSummarizationJobStore()
    jobStore.lastEvent = {
      event: 'section_completed',
      data: { section_id: 3 },
    }
    await w.vm.$nextTick()
    const rows = w.findAll('tbody tr[role="link"]')
    expect(rows[2].text()).toContain('✕')
  })
})
