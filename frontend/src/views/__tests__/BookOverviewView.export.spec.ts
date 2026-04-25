import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import BookOverviewView from '@/views/BookOverviewView.vue'

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/books/:id', name: 'book-overview', component: BookOverviewView },
      { path: '/books/:id/sections/:sectionId', name: 'section-detail', component: { template: '<div/>' } },
    ],
  })
}

describe('BookOverviewView export buttons', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('disables Export and Copy when book has no summaries', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/api/v1/books/1/tags'))
        return Promise.resolve(new Response(JSON.stringify({ tags: [] })))
      if (u.includes('/api/v1/books/1/summary'))
        return Promise.resolve(new Response('{}', { status: 404 }))
      if (u.includes('/api/v1/books/1'))
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: 1,
              title: 'X',
              authors: [],
              status: 'COMPLETED',
              sections: [
                { id: 1, title: 'C1', has_summary: false, section_type: 'chapter' },
              ],
              default_summary_id: null,
            }),
          ),
        )
      return Promise.resolve(new Response('{}'))
    })
    const router = buildRouter()
    router.push('/books/1')
    await router.isReady()
    const wrapper = mount(BookOverviewView, { global: { plugins: [router] } })
    await flushPromises()
    const btnExport = wrapper.find('[data-testid="export-summary-btn"]')
    const btnCopy = wrapper.find('[data-testid="copy-markdown-btn"]')
    expect(btnExport.attributes('disabled')).toBeDefined()
    expect(btnCopy.attributes('disabled')).toBeDefined()
    expect(btnExport.attributes('title')).toMatch(/Generate a summary/i)
  })

  it('disables all three when book is UPLOADING', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/tags'))
        return Promise.resolve(new Response(JSON.stringify({ tags: [] })))
      if (u.includes('/summary'))
        return Promise.resolve(new Response('{}', { status: 404 }))
      return Promise.resolve(
        new Response(
          JSON.stringify({
            id: 1,
            title: 'X',
            authors: [],
            status: 'UPLOADING',
            sections: [],
            default_summary_id: null,
          }),
        ),
      )
    })
    const router = buildRouter()
    router.push('/books/1')
    await router.isReady()
    const wrapper = mount(BookOverviewView, { global: { plugins: [router] } })
    await flushPromises()
    const btnExport = wrapper.find('[data-testid="export-summary-btn"]')
    expect(btnExport.attributes('disabled')).toBeDefined()
    expect(btnExport.attributes('title')).toMatch(/processed/i)
  })
})
