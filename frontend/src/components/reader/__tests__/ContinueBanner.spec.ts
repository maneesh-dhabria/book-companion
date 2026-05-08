import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'

import ContinueBanner from '../ContinueBanner.vue'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/books/:id', component: { template: '<div/>' } },
      { path: '/books/:id/sections/:sectionId', component: { template: '<div/>' } },
    ],
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
})

describe('ContinueBanner — FR-B04 front-matter fallback', () => {
  it('falls back to firstChapter and renders "Start reading" when section_id points to front matter', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
      const u = String(url)
      if (u.includes('/reading-state/continue')) {
        return new Response(
          JSON.stringify({
            last_book_id: 7,
            last_section_id: 100, // front-matter
            last_viewed_at: '2026-05-08T10:00:00Z',
            book_title: 'Big Book',
            section_title: 'Copyright',
          }),
        )
      }
      if (u.endsWith('/books/7')) {
        return new Response(
          JSON.stringify({
            id: 7,
            title: 'Big Book',
            status: 'PARSED',
            sections: [
              { id: 100, title: 'Copyright', section_type: 'copyright' },
              { id: 101, title: 'Ch1', section_type: 'chapter' },
            ],
          }),
        )
      }
      return new Response('{}')
    })
    const router = makeRouter()
    const w = mount(ContinueBanner, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('Start reading')
    expect(w.text()).not.toMatch(/You were reading/)
    const btn = w.find('[data-testid="continue-banner-btn"]')
    await btn.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/books/7/sections/101')
  })

  it('uses Continue label and links to recorded section when section is a chapter', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
      const u = String(url)
      if (u.includes('/reading-state/continue')) {
        return new Response(
          JSON.stringify({
            last_book_id: 7,
            last_section_id: 101,
            last_viewed_at: '2026-05-08T10:00:00Z',
            book_title: 'Big Book',
            section_title: 'Ch1',
          }),
        )
      }
      if (u.endsWith('/books/7')) {
        return new Response(
          JSON.stringify({
            id: 7,
            title: 'Big Book',
            status: 'PARSED',
            sections: [
              { id: 100, title: 'Copyright', section_type: 'copyright' },
              { id: 101, title: 'Ch1', section_type: 'chapter' },
            ],
          }),
        )
      }
      return new Response('{}')
    })
    const router = makeRouter()
    const w = mount(ContinueBanner, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('You were reading')
    expect(w.text()).not.toContain('Start reading')
    await w.find('[data-testid="continue-banner-btn"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/books/7/sections/101')
  })

  it('renders nothing when no chapter exists at all', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
      const u = String(url)
      if (u.includes('/reading-state/continue')) {
        return new Response(
          JSON.stringify({
            last_book_id: 7,
            last_section_id: null,
            last_viewed_at: '2026-05-08T10:00:00Z',
            book_title: 'Front Matter Only',
            section_title: null,
          }),
        )
      }
      if (u.endsWith('/books/7')) {
        return new Response(
          JSON.stringify({
            id: 7,
            title: 'Front Matter Only',
            status: 'PARSING',
            sections: [{ id: 100, title: 'Copyright', section_type: 'copyright' }],
          }),
        )
      }
      return new Response('{}')
    })
    const router = makeRouter()
    const w = mount(ContinueBanner, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.find('[data-testid="continue-banner"]').exists()).toBe(false)
  })
})
