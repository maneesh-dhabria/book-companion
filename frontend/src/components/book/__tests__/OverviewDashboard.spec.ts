import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'

import OverviewDashboard from '../OverviewDashboard.vue'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/books/:id', component: { template: '<div/>' } },
      { path: '/books/:id/sections/:sectionId', name: 'section-detail', component: { template: '<div/>' } },
      { path: '/concepts', component: { template: '<div/>' } },
    ],
  })
}

const BOOK = ({
  id: 1,
  title: 'Test Book',
  status: 'PARSED',
  default_summary: { summary_md: '# Body', generated_at: '2026-05-01T00:00:00Z', preset: 'practitioner_bullets' },
  sections: [
    { id: 10, title: 'Copyright', section_type: 'copyright', order_index: 0, content_char_count: 1000 },
    { id: 11, title: 'Chapter 1', section_type: 'chapter', order_index: 1, content_char_count: 22000 },
    { id: 12, title: 'Chapter 2', section_type: 'chapter', order_index: 2, content_char_count: 22000 },
  ],
} as never)

beforeEach(() => {
  vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
    const u = String(url)
    if (u.includes('/concepts')) {
      return new Response(
        JSON.stringify({
          items: [
            { id: 1, term: 'Stratagem', book_id: 1, created_at: '2026-04-01T00:00:00Z' },
            { id: 2, term: 'Terrain', book_id: 1, created_at: '2026-04-02T00:00:00Z' },
            { id: 3, term: 'Spies', book_id: 1, created_at: '2026-04-03T00:00:00Z' },
          ],
          total: 3,
        }),
      )
    }
    if (u.includes('/reading-state/by-book/')) {
      return new Response(
        JSON.stringify({
          last_book_id: 1,
          last_section_id: 11,
          section_title: 'Chapter 1',
          last_viewed_at: '2026-05-08T00:00:00Z',
        }),
      )
    }
    return new Response('{}')
  })
})

describe('OverviewDashboard (FR-C01..C05)', () => {
  it('renders exactly 4 tiles by data-testid', async () => {
    const router = makeRouter()
    const w = mount(OverviewDashboard, {
      props: { book: BOOK },
      global: { plugins: [router] },
    })
    await flushPromises()
    expect(w.find('[data-testid="tile-continue"]').exists()).toBe(true)
    expect(w.find('[data-testid="tile-summary"]').exists()).toBe(true)
    expect(w.find('[data-testid="tile-concepts"]').exists()).toBe(true)
    expect(w.find('[data-testid="tile-sections"]').exists()).toBe(true)
  })

  it('Continue tile uses firstChapter (skips copyright) and labels "Continue reading" when reader_position exists', async () => {
    const router = makeRouter()
    const w = mount(OverviewDashboard, {
      props: { book: BOOK },
      global: { plugins: [router] },
    })
    await flushPromises()
    const tile = w.find('[data-testid="tile-continue"]')
    expect(tile.text()).toContain('Continue reading')
    // When reader_position exists, the by-book endpoint says last_section_id=11,
    // but the tile still routes to firstChapter for consistency with FR-B02.
    expect(tile.attributes('href')).toBe('/books/1/sections/11')
    expect(tile.text()).toContain('Chapter 1')
  })

  it('Continue tile shows "Start reading" when no reader_position exists', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
      const u = String(url)
      if (u.includes('/concepts')) return new Response(JSON.stringify({ items: [] }))
      if (u.includes('/reading-state/by-book/')) {
        return new Response(JSON.stringify({ last_book_id: null, last_section_id: null }))
      }
      return new Response('{}')
    })
    const router = makeRouter()
    const w = mount(OverviewDashboard, {
      props: { book: BOOK },
      global: { plugins: [router] },
    })
    await flushPromises()
    expect(w.find('[data-testid="tile-continue"]').text()).toContain('Start reading')
  })

  it('Sections tile renders formatReadTimeSum of section char counts', async () => {
    const router = makeRouter()
    const w = mount(OverviewDashboard, {
      props: { book: BOOK },
      global: { plugins: [router] },
    })
    await flushPromises()
    const tile = w.find('[data-testid="tile-sections"]')
    // 1000 + 22000 + 22000 = 45000 chars / 1100 cpm = 41 min (ceil)
    expect(tile.text()).toContain('41 min')
    expect(tile.text()).toContain('3 sections')
  })

  it('Top concepts tile renders concepts as chips sorted by created_at ASC', async () => {
    const router = makeRouter()
    const w = mount(OverviewDashboard, {
      props: { book: BOOK },
      global: { plugins: [router] },
    })
    await flushPromises()
    const tile = w.find('[data-testid="tile-concepts"]')
    const chipText = tile.text()
    const i1 = chipText.indexOf('Stratagem')
    const i2 = chipText.indexOf('Terrain')
    const i3 = chipText.indexOf('Spies')
    expect(i1).toBeGreaterThanOrEqual(0)
    expect(i2).toBeGreaterThan(i1)
    expect(i3).toBeGreaterThan(i2)
  })

  it('shows skeleton blocks while concepts are loading', async () => {
    let resolveConcepts: ((r: Response) => void) | null = null
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/concepts')) {
        return new Promise<Response>((resolve) => {
          resolveConcepts = resolve
        })
      }
      if (u.includes('/reading-state/by-book/')) {
        return Promise.resolve(
          new Response(JSON.stringify({ last_book_id: null, last_section_id: null })),
        )
      }
      return Promise.resolve(new Response('{}'))
    })
    const router = makeRouter()
    const w = mount(OverviewDashboard, {
      props: { book: BOOK },
      global: { plugins: [router] },
    })
    await flushPromises()
    expect(w.find('[data-testid="tile-concepts"] .skeleton').exists()).toBe(true)
    if (resolveConcepts) {
      const fn = resolveConcepts as (r: Response) => void
      fn(new Response(JSON.stringify({ items: [] })))
    }
    await flushPromises()
    expect(w.find('[data-testid="tile-concepts"] .skeleton').exists()).toBe(false)
  })
})
