import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createWebHistory, type Router } from 'vue-router'

import BookOverviewView from '../BookOverviewView.vue'

const BOOK = {
  id: 3,
  title: 'Test Book',
  authors: [],
  sections: [{ id: 11, title: 'Ch1', section_type: 'chapter', has_summary: false }],
  summary_progress: { summarizable: 1, summarized: 0, failed_and_pending: 0, pending: 1 },
}

function mockFetch() {
  vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
    const u = String(url)
    if (u.endsWith('/books/3')) return new Response(JSON.stringify(BOOK))
    if (u.includes('/books/3/tags')) return new Response(JSON.stringify({ tags: [] }))
    return new Response('{"tags":[],"summary_md":null}')
  })
}

function makeRouter(): Router {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/:id', name: 'book-overview', component: BookOverviewView },
      { path: '/:id/sections/:sectionId', name: 'section-detail', component: { template: '<div/>' } },
      { path: '/:id/summary', name: 'book-summary', component: { template: '<div/>' } },
      { path: '/:id/edit-structure', name: 'book-edit-structure', component: { template: '<div/>' } },
    ],
  })
}

async function mountAt(path: string) {
  const router = makeRouter()
  router.push(path)
  await router.isReady()
  const wrapper = mount(BookOverviewView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('BookOverviewView tab strip', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockFetch()
  })

  it('renders five tab buttons: Overview, Summary, Sections, Audio, Annotations', async () => {
    const { wrapper } = await mountAt('/3')
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(5)
    expect(tabs.map((t) => t.text())).toEqual([
      'Overview',
      'Summary',
      'Sections',
      'Audio',
      'Annotations',
    ])
  })

  it('clicking Audio tab activates it', async () => {
    const { wrapper, router } = await mountAt('/3')
    const replaceSpy = vi.spyOn(router, 'replace')
    await wrapper.findAll('[role="tab"]')[3].trigger('click')
    const arg = replaceSpy.mock.calls[0][0] as { query?: { tab?: string } }
    expect(arg.query?.tab).toBe('audio')
  })

  it('clicking Annotations tab activates it', async () => {
    const { wrapper, router } = await mountAt('/3')
    const replaceSpy = vi.spyOn(router, 'replace')
    await wrapper.findAll('[role="tab"]')[4].trigger('click')
    const arg = replaceSpy.mock.calls[0][0] as { query?: { tab?: string } }
    expect(arg.query?.tab).toBe('annotations')
  })

  it('?tab=audio activates audio tab', async () => {
    const { wrapper } = await mountAt('/3?tab=audio')
    const active = wrapper.find('[role="tab"][aria-selected="true"]')
    expect(active.text()).toBe('Audio')
  })

  it('defaults to overview tab when ?tab= is absent', async () => {
    const { wrapper } = await mountAt('/3')
    const active = wrapper.find('[role="tab"][aria-selected="true"]')
    expect(active.text()).toBe('Overview')
  })

  it('respects ?tab=summary on initial mount', async () => {
    const { wrapper } = await mountAt('/3?tab=summary')
    const active = wrapper.find('[role="tab"][aria-selected="true"]')
    expect(active.text()).toBe('Summary')
  })

  it('updates URL via router.replace when a tab is clicked', async () => {
    const { wrapper, router } = await mountAt('/3')
    const replaceSpy = vi.spyOn(router, 'replace')
    await wrapper.findAll('[role="tab"]')[1].trigger('click')
    expect(replaceSpy).toHaveBeenCalled()
    const arg = replaceSpy.mock.calls[0][0] as { query?: { tab?: string } }
    expect(arg.query?.tab).toBe('summary')
  })
})
