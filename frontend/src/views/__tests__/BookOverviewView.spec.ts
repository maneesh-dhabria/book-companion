import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createWebHistory, type Router } from 'vue-router'

import BookOverviewView from '../BookOverviewView.vue'

const BOOK = {
  id: 1,
  title: 'Art of War',
  authors: [],
  sections: [{ id: 11, title: 'Ch1', section_type: 'chapter', has_summary: false }],
  summary_progress: { summarizable: 17, summarized: 7, failed_and_pending: 3, pending: 7 },
}

function makeRouter(): Router {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/:id', name: 'book-overview', component: BookOverviewView },
      { path: '/:id/sections/:sectionId', name: 'section-detail', component: { template: '<div/>' } },
    ],
  })
}

describe('BookOverviewView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('mounts SummarizationProgress with correct props from summary_progress', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
      const u = String(url)
      if (u.endsWith('/books/1')) return new Response(JSON.stringify(BOOK))
      if (u.includes('/books/1/tags')) return new Response(JSON.stringify({ tags: [] }))
      if (u.includes('/books/1/summary')) return new Response(JSON.stringify({ summary_md: null }))
      return new Response('{}')
    })
    const router = makeRouter()
    router.push('/1')
    await router.isReady()
    const w = mount(BookOverviewView, { global: { plugins: [router] } })
    await flushPromises()
    const progress = w.findComponent({ name: 'SummarizationProgress' })
    expect(progress.exists()).toBe(true)
    expect(progress.props('bookId')).toBe(1)
    expect(progress.props('summarized')).toBe(7)
    expect(progress.props('total')).toBe(17)
    expect(progress.props('failedAndPending')).toBe(3)
  })

  it('omits SummarizationProgress when summarizable is 0', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
      const u = String(url)
      if (u.endsWith('/books/1')) {
        return new Response(
          JSON.stringify({
            ...BOOK,
            summary_progress: {
              summarizable: 0,
              summarized: 0,
              failed_and_pending: 0,
              pending: 0,
            },
          }),
        )
      }
      return new Response('{"tags":[],"summary_md":null}')
    })
    const router = makeRouter()
    router.push('/1')
    await router.isReady()
    const w = mount(BookOverviewView, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.findComponent({ name: 'SummarizationProgress' }).exists()).toBe(false)
  })
})
