import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import SectionListTable from '../SectionListTable.vue'
import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { audioApi } from '@/api/audio'
import { _resetBookAudioMapCache } from '@/composables/useBookAudioMap'

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
    default_summary_id: 200,
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
    default_summary_id: 201,
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

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  _resetBookAudioMapCache()
  // By default mock the audio map endpoint to return an empty map. Tests
  // that need MP3 hits stub it explicitly.
  vi.spyOn(audioApi, 'sectionsByBook').mockResolvedValue({
    book_id: 1,
    sections: [],
  })
})

describe('SectionListTable (FR-C13..C20) — div-grid stack mode', () => {
  it('renders the 4-column header set: # / Title / Read time / Summary', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    expect(w.find('.section-list-header').text()).toContain('#')
    expect(w.find('.section-list-header').text()).toContain('Title')
    expect(w.find('.section-list-header').text()).toContain('Read time')
    expect(w.find('.section-list-header').text()).toContain('Summary')
  })

  it('renders three group separators with correct labels', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    expect(w.find('[data-group="front"]').text()).toContain('Front matter')
    expect(w.find('[data-group="chapters"]').text()).toContain('Chapters')
    expect(w.find('[data-group="back"]').text()).toContain('Back matter')
  })

  it('chapters group expanded by default; front and back collapsed', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    expect(w.find('[data-group-body="chapters"]').exists()).toBe(true)
    expect(w.find('[data-group-body="front"]').exists()).toBe(false)
    expect(w.find('[data-group-body="back"]').exists()).toBe(false)
  })

  it('clicking a group separator toggles expand and persists to localStorage', async () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 7 },
      global: { plugins: [makeRouter()] },
    })
    await w.find('[data-group="back"]').trigger('click')
    expect(w.find('[data-group-body="back"]').exists()).toBe(true)
    const saved = JSON.parse(localStorage.getItem('bc.sections.expand.7') ?? '{}')
    expect(saved.back).toBe(true)
  })

  it('rows are <div role="button"> with aria-label for screen readers', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    const rows = w.findAll('[data-row][role="button"]')
    expect(rows.length).toBeGreaterThan(0)
    expect(rows[0].attributes('aria-label')).toMatch(/Open summary of /)
    // Not anchor tags — preserves valid HTML for nested action buttons.
    expect(rows[0].element.tagName).toBe('DIV')
  })

  it('row click navigates with ?tab=summary by default (FR-C17)', async () => {
    const router = makeRouter()
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [router] },
    })
    const firstChapterRow = w.findAll('[data-group-body="chapters"] [data-row]')[0]
    await firstChapterRow.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/books/1/sections/2')
    expect(router.currentRoute.value.query.tab).toBe('summary')
  })

  it('inner Read button routes WITHOUT ?tab=summary (FR-C18)', async () => {
    const router = makeRouter()
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [router] },
    })
    const row = w.findAll('[data-group-body="chapters"] [data-row]')[0]
    const readBtn = row.find('[data-action="read"]')
    await readBtn.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/books/1/sections/2')
    expect(router.currentRoute.value.query.tab).toBeUndefined()
  })

  it('inner Listen button does NOT navigate (FR-C18)', async () => {
    const router = makeRouter()
    await router.push('/books/1/sections/0')
    const startPath = router.currentRoute.value.fullPath
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [router] },
    })
    await flushPromises()
    const row = w.findAll('[data-group-body="chapters"] [data-row]')[0]
    const listenBtn = row.find('[data-action="listen"]')
    await listenBtn.trigger('click')
    await flushPromises()
    // Route unchanged because the button stops propagation and doesn't navigate.
    expect(router.currentRoute.value.fullPath).toBe(startPath)
  })

  it('Listen disabled when section has no summary AND no MP3 (FR-C20)', async () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    await flushPromises()
    const rows = w.findAll('[data-group-body="chapters"] [data-row]')
    // Chapter 2 (id:3) has no summary and (per default mock) no MP3.
    expect(rows[1].find('[data-action="listen"]').attributes('disabled')).toBeDefined()
    // Chapter 1 (id:2) has a summary → enabled.
    expect(rows[0].find('[data-action="listen"]').attributes('disabled')).toBeUndefined()
  })

  it('Listen enabled when audio batch lookup reports has_mp3 (FR-C20)', async () => {
    vi.spyOn(audioApi, 'sectionsByBook').mockResolvedValue({
      book_id: 1,
      sections: [{ section_id: 3, has_mp3: true, engine: 'kokoro' }],
    })
    _resetBookAudioMapCache()
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    await flushPromises()
    const rows = w.findAll('[data-group-body="chapters"] [data-row]')
    // Chapter 2 (id:3) — no summary but has MP3 → Listen enabled.
    expect(rows[1].find('[data-action="listen"]').attributes('disabled')).toBeUndefined()
  })

  it('every row renders a trailing chevron (FR-C19)', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    const rows = w.findAll('[data-group-body="chapters"] [data-row]')
    for (const r of rows) {
      expect(r.find('.row-chev').exists()).toBe(true)
    }
  })

  it('cmd-click opens in a new tab (FR-C17a)', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    const router = makeRouter()
    await router.push('/books/1/sections/0')
    const startPath = router.currentRoute.value.fullPath
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [router] },
    })
    const row = w.findAll('[data-group-body="chapters"] [data-row]')[0]
    await row.trigger('click', { metaKey: true })
    await flushPromises()
    expect(openSpy).toHaveBeenCalledTimes(1)
    expect(openSpy.mock.calls[0][1]).toBe('_blank')
    // Active route did not change.
    expect(router.currentRoute.value.fullPath).toBe(startPath)
  })

  it('Summary cell shows ✓ when has_summary, ✕ otherwise', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    const rows = w.findAll('[data-group-body="chapters"] [data-row]')
    expect(rows[0].text()).toContain('✓')
    expect(rows[1].text()).toContain('✕')
    expect(rows[2].text()).toContain('✓')
  })

  it('flips Summary cell to ✓ on section_completed event', async () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1 },
      global: { plugins: [makeRouter()] },
    })
    const jobStore = useSummarizationJobStore()
    jobStore.lastEvent = {
      event: 'section_completed',
      data: { section_id: 3 },
    }
    await w.vm.$nextTick()
    const rows = w.findAll('[data-group-body="chapters"] [data-row]')
    expect(rows[1].html()).toContain('✓')
  })
})

describe('SectionListTable (compact / reader-TOC dropdown)', () => {
  it('compact mode renders flat list (no group separators), as a table', () => {
    const w = mount(SectionListTable, {
      props: { sections, bookId: 1, compact: true },
      global: { plugins: [makeRouter()] },
    })
    expect(w.findAll('[data-group]')).toHaveLength(0)
    expect(w.findAll('tbody tr[role="link"]')).toHaveLength(5)
  })

  it('preserves ?tab when called from reader-TOC context', async () => {
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
