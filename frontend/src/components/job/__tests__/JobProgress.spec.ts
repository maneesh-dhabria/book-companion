import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import JobProgress from '../JobProgress.vue'

vi.mock('@/api/processing', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@/api/processing')
  return {
    ...actual,
    listProcessingJobs: vi.fn(async () => ({ jobs: [] })),
    cancelProcessing: vi.fn(async () => ({})),
    connectSSE: vi.fn(() => ({ close: vi.fn() }) as unknown as EventSource),
  }
})

describe('JobProgress', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders pending state by default', async () => {
    const w = mount(JobProgress, {
      props: { jobId: 1, bookId: 99 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    expect(w.attributes('data-phase')).toBe('pending')
    expect(w.text()).toContain('Queued')
  })

  it('transitions to running on processing_started SSE event', async () => {
    const { connectSSE } = await import('@/api/processing')
    type Handlers = Parameters<typeof connectSSE>[1]
    let capturedHandlers: Handlers = {}
    vi.mocked(connectSSE).mockImplementation((_jobId, handlers) => {
      capturedHandlers = handlers
      return { close: vi.fn() } as unknown as EventSource
    })

    const w = mount(JobProgress, {
      props: { jobId: 2, bookId: 99 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    capturedHandlers.onProcessingStarted?.({ book_id: 99, job_id: 2, scope: 'all' })
    await flushPromises()
    expect(w.attributes('data-phase')).toBe('running')
  })

  it('renders completed card after processing_completed', async () => {
    const { connectSSE } = await import('@/api/processing')
    type Handlers = Parameters<typeof connectSSE>[1]
    let capturedHandlers: Handlers = {}
    vi.mocked(connectSSE).mockImplementation((_jobId, handlers) => {
      capturedHandlers = handlers
      return { close: vi.fn() } as unknown as EventSource
    })

    const w = mount(JobProgress, {
      props: { jobId: 3, bookId: 99 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    capturedHandlers.onProcessingCompleted?.({
      book_id: 99,
      completed: 7,
      failed: 0,
      skipped: 1,
    })
    await flushPromises()
    expect(w.attributes('data-phase')).toBe('completed')
    expect(w.text()).toContain('7 sections')
  })

  it('renders cancelled copy when reason="cancelled"', async () => {
    const { connectSSE } = await import('@/api/processing')
    type Handlers = Parameters<typeof connectSSE>[1]
    let capturedHandlers: Handlers = {}
    vi.mocked(connectSSE).mockImplementation((_jobId, handlers) => {
      capturedHandlers = handlers
      return { close: vi.fn() } as unknown as EventSource
    })

    const w = mount(JobProgress, {
      props: { jobId: 4, bookId: 99 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    capturedHandlers.onProcessingFailed?.({
      book_id: 99,
      error: 'cancelled',
      reason: 'cancelled',
    })
    await flushPromises()
    expect(w.attributes('data-phase')).toBe('failed')
    expect(w.text()).toContain('Cancelled')
  })

  it('renders cli_disappeared specific copy', async () => {
    const { connectSSE } = await import('@/api/processing')
    type Handlers = Parameters<typeof connectSSE>[1]
    let capturedHandlers: Handlers = {}
    vi.mocked(connectSSE).mockImplementation((_jobId, handlers) => {
      capturedHandlers = handlers
      return { close: vi.fn() } as unknown as EventSource
    })

    const w = mount(JobProgress, {
      props: { jobId: 5, bookId: 99 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    capturedHandlers.onProcessingFailed?.({
      book_id: 99,
      error: 'binary missing',
      reason: 'cli_disappeared',
    })
    await flushPromises()
    expect(w.text()).toContain('LLM CLI became unavailable')
  })
})
