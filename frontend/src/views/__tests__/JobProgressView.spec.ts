import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import JobProgressView from '@/views/JobProgressView.vue'
import type { JobState } from '@/composables/useBufferedJobStream'

class MockEventSource {
  public onmessage: ((m: { data: string }) => void) | null = null
  public onerror: (() => void) | null = null
  public closed = false
  close() {
    this.closed = true
  }
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'library', component: { template: '<div/>' } },
      { path: '/books/:id', name: 'book-overview', component: { template: '<div/>' } },
      { path: '/jobs/:id', name: 'job-detail', component: JobProgressView, props: true },
    ],
  })
}

const seed = (overrides: Partial<JobState> = {}): JobState => ({
  id: 7,
  book_id: 1,
  book_title: 'Art of War',
  status: 'RUNNING',
  scope: 'all',
  section_id: null,
  progress: { current: 3, total: 10, current_section_title: 'Chapter 3', eta_seconds: 120 },
  started_at: '2026-04-30T10:00:00Z',
  completed_at: null,
  error_message: null,
  last_event_at: '2026-04-30T10:00:01Z',
  ...overrides,
})

describe('JobProgressView', () => {
  it('renders skeleton while loading', async () => {
    const es = new MockEventSource()
    // Stub the global EventSource so the composable doesn't throw.
    ;(globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource
    // Pending fetch — never resolves
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}))
    const router = makeRouter()
    await router.push('/jobs/7')
    await router.isReady()
    const wrapper = mount(JobProgressView, {
      props: { id: '7' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('[data-testid="job-skeleton"]').exists()).toBe(true)
    void es
  })

  it('renders running state with progress', async () => {
    ;(globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify(seed()))),
    )
    const router = makeRouter()
    await router.push('/jobs/7')
    await router.isReady()
    const wrapper = mount(JobProgressView, {
      props: { id: '7' },
      global: { plugins: [router] },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="job-running"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Art of War')
    expect(wrapper.text()).toContain('3 of 10')
    expect(wrapper.text()).toContain('Chapter 3')
  })

  it('renders 404 not-found state', async () => {
    ;(globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(new Response('{}', { status: 404 })),
    )
    const router = makeRouter()
    await router.push('/jobs/7')
    await router.isReady()
    const wrapper = mount(JobProgressView, {
      props: { id: '7' },
      global: { plugins: [router] },
    })
    await flushPromises()
    expect(wrapper.text()).toMatch(/Job not found/i)
  })

  it('renders terminal completed state', async () => {
    ;(globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            seed({ status: 'COMPLETED', completed_at: '2026-04-30T10:01:00Z', progress: { current: 10, total: 10, current_section_title: '', eta_seconds: 0 } }),
          ),
        ),
      ),
    )
    const router = makeRouter()
    await router.push('/jobs/7')
    await router.isReady()
    const wrapper = mount(JobProgressView, {
      props: { id: '7' },
      global: { plugins: [router] },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="job-terminal"]').exists()).toBe(true)
    expect(wrapper.text()).toMatch(/Summary complete/i)
  })

  it('cancel button posts to /cancel endpoint', async () => {
    ;(globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource
    const fetchSpy = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve(new Response('{}'))
      return Promise.resolve(new Response(JSON.stringify(seed())))
    })
    vi.spyOn(globalThis, 'fetch').mockImplementation(fetchSpy as never)
    const router = makeRouter()
    await router.push('/jobs/7')
    await router.isReady()
    const wrapper = mount(JobProgressView, {
      props: { id: '7' },
      global: { plugins: [router] },
    })
    await flushPromises()
    await wrapper.find('[data-testid="job-cancel"]').trigger('click')
    await flushPromises()
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/processing/7/cancel',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
