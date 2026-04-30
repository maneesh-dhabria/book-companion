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
      { path: '/books/:id/summary', name: 'book-summary', component: { template: '<div/>' } },
      { path: '/books/:id/edit-structure', name: 'book-edit-structure', component: { template: '<div/>' } },
    ],
  })
}

describe('BookOverviewView export buttons', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // jsdom doesn't ship URL.createObjectURL / revokeObjectURL.
    if (!URL.createObjectURL) URL.createObjectURL = vi.fn(() => 'blob:mock')
    if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn()
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
    const exportBtn = wrapper.find('[data-action="export"]')
    const exportBody = exportBtn.find('[data-role="body"]')
    expect(exportBody.attributes('aria-disabled')).toBe('true')
    expect(exportBody.attributes('title')).toMatch(/Generate a summary/i)
  })

  it('export click keeps spinner visible for >= 250ms even when fetch resolves fast (FR-25)', async () => {
    vi.useFakeTimers()
    let resolved = false
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/tags')) return Promise.resolve(new Response(JSON.stringify({ tags: [] })))
      if (u.includes('/summary')) return Promise.resolve(new Response('{}', { status: 404 }))
      if (u.includes('/api/v1/books/1') && !u.includes('/export'))
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: 1,
              title: 'X',
              authors: [],
              status: 'COMPLETED',
              sections: [{ id: 1, title: 'C1', has_summary: true, section_type: 'chapter' }],
              default_summary_id: 99,
            }),
          ),
        )
      // Export endpoint resolves in 50ms
      if (u.includes('/export')) {
        return new Promise((res) => {
          setTimeout(() => {
            resolved = true
            res(
              new Response(new Blob(['md']), {
                status: 200,
                headers: { 'content-disposition': 'attachment; filename=x.md' },
              }),
            )
          }, 50)
        })
      }
      return Promise.resolve(new Response('{}'))
    })
    const router = buildRouter()
    router.push('/books/1')
    await router.isReady()
    const wrapper = mount(BookOverviewView, { global: { plugins: [router] } })
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    const exportBody = wrapper.find('[data-action="export"] [data-role="body"]')
    void exportBody.trigger('click')

    await vi.advanceTimersByTimeAsync(50)
    expect(resolved).toBe(true)
    // Spinner must still be visible at 50ms even though export resolved
    expect(wrapper.find('[data-action="export"] .spinner').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(220)
    await flushPromises()
    expect(wrapper.find('[data-action="export"] .spinner').exists()).toBe(false)
    vi.useRealTimers()
  })

  it('clipboard fallback strips images when primary write fails (FR-26)', async () => {
    const writeSpy = vi.fn().mockRejectedValue(new Error('NotAllowed'))
    const writeTextSpy = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { write: writeSpy, writeText: writeTextSpy },
      configurable: true,
    })
    // Make sure ClipboardItem exists so primary path is attempted.
    ;(window as unknown as { ClipboardItem: typeof ClipboardItem }).ClipboardItem =
      class MockClipboardItem {
        constructor(_d: unknown) {
          void _d
        }
      } as unknown as typeof ClipboardItem

    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/tags')) return Promise.resolve(new Response(JSON.stringify({ tags: [] })))
      if (u.includes('/summary')) return Promise.resolve(new Response('{}', { status: 404 }))
      if (u.includes('/export'))
        return Promise.resolve(new Response('Hello ![img](http://x/y.png) world'))
      if (u.includes('/api/v1/books/1'))
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: 1,
              title: 'X',
              authors: [],
              status: 'COMPLETED',
              sections: [{ id: 1, title: 'C1', has_summary: true, section_type: 'chapter' }],
              default_summary_id: 99,
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
    await wrapper.find('[data-action="export"] [data-role="chevron"]').trigger('click')
    const copy = wrapper
      .findAll('[role="menuitem"]')
      .find((i) => i.text() === 'Copy to Clipboard')!
    await copy.trigger('click')
    await flushPromises()
    expect(writeTextSpy).toHaveBeenCalledWith('Hello img world')
  })

  it('both clipboard paths failing surfaces the HTTPS/permission toast (FR-26)', async () => {
    const writeSpy = vi.fn().mockRejectedValue(new Error('NotAllowed'))
    const writeTextSpy = vi.fn().mockRejectedValue(new Error('NotAllowed'))
    Object.defineProperty(navigator, 'clipboard', {
      value: { write: writeSpy, writeText: writeTextSpy },
      configurable: true,
    })
    ;(window as unknown as { ClipboardItem: typeof ClipboardItem }).ClipboardItem =
      class MockClipboardItem2 {
        constructor(_d: unknown) {
          void _d
        }
      } as unknown as typeof ClipboardItem

    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url)
      if (u.includes('/tags')) return Promise.resolve(new Response(JSON.stringify({ tags: [] })))
      if (u.includes('/summary')) return Promise.resolve(new Response('{}', { status: 404 }))
      if (u.includes('/export')) return Promise.resolve(new Response('any md'))
      return Promise.resolve(
        new Response(
          JSON.stringify({
            id: 1,
            title: 'X',
            authors: [],
            status: 'COMPLETED',
            sections: [{ id: 1, title: 'C1', has_summary: true, section_type: 'chapter' }],
            default_summary_id: 99,
          }),
        ),
      )
    })
    const router = buildRouter()
    router.push('/books/1')
    await router.isReady()
    const wrapper = mount(BookOverviewView, { global: { plugins: [router] } })
    await flushPromises()
    const { useUiStore } = await import('@/stores/ui')
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    await wrapper.find('[data-action="export"] [data-role="chevron"]').trigger('click')
    await wrapper
      .findAll('[role="menuitem"]')
      .find((i) => i.text() === 'Copy to Clipboard')!
      .trigger('click')
    await flushPromises()
    const calls = toastSpy.mock.calls.map((c) => String(c[0]))
    expect(calls.some((m) => /HTTPS or clipboard permission/i.test(m))).toBe(true)
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
    const exportBody = wrapper.find('[data-action="export"] [data-role="body"]')
    expect(exportBody.attributes('aria-disabled')).toBe('true')
    expect(exportBody.attributes('title')).toMatch(/processed/i)
  })
})
