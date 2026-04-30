import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { useBufferedJobStream, type JobState } from '../useBufferedJobStream'

class MockEventSource {
  public onmessage: ((m: { data: string }) => void) | null = null
  public onerror: (() => void) | null = null
  public closed = false
  close() {
    this.closed = true
  }
  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }
  fail() {
    this.onerror?.()
  }
}

function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((r, j) => {
    resolve = r
    reject = j
  })
  return { promise, resolve, reject }
}

const baseSeed = (overrides: Partial<JobState> = {}): JobState => ({
  id: 42,
  book_id: 1,
  book_title: 'B',
  status: 'RUNNING',
  scope: 'all',
  section_id: null,
  progress: { current: 5, total: 10, current_section_title: 'Five', eta_seconds: 60 },
  started_at: '2026-04-30T10:00:00Z',
  completed_at: null,
  error_message: null,
  last_event_at: '2026-04-30T10:00:01.500Z',
  ...overrides,
})

describe('useBufferedJobStream', () => {
  it('buffered events newer than GET timestamp are applied', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state, isLoading } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    es.emit({ event: 'section_completed', data: { last_event_at: '2026-04-30T10:00:01.000Z', section_id: 6 } })
    es.emit({ event: 'section_completed', data: { last_event_at: '2026-04-30T10:00:02.000Z', section_id: 7 } })
    d.resolve(baseSeed())
    await flushPromises()
    expect(isLoading.value).toBe(false)
    // 10:00:01.000 < 10:00:01.500 (seed) — discarded.
    // 10:00:02.000 > 10:00:01.500 — applied. current goes 5 -> 6.
    expect(state.value!.progress.current).toBe(6)
  })

  it('section_started updates current_section_title', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed())
    await flushPromises()
    es.emit({ event: 'section_started', data: { last_event_at: '2026-04-30T10:00:03Z', section_title: 'Six' } })
    await flushPromises()
    expect(state.value!.progress.current_section_title).toBe('Six')
  })

  it('section_completed increments progress.current', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed({ progress: { current: 5, total: 10, current_section_title: '', eta_seconds: 60 } }))
    await flushPromises()
    es.emit({ event: 'section_completed', data: { last_event_at: '2026-04-30T10:00:03Z', section_id: 6 } })
    await flushPromises()
    expect(state.value!.progress.current).toBe(6)
  })

  it('section_failed increments failure counter', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed())
    await flushPromises()
    es.emit({ event: 'section_failed', data: { last_event_at: '2026-04-30T10:00:03Z', section_id: 6, error: 'boom' } })
    await flushPromises()
    expect(state.value!.failures).toBe(1)
  })

  it('section_retry surfaces retrying indicator', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed())
    await flushPromises()
    es.emit({ event: 'section_retry', data: { last_event_at: '2026-04-30T10:00:03Z', section_id: 6 } })
    await flushPromises()
    expect(state.value!.retrying_section_id).toBe(6)
  })

  it('processing_completed transitions status to COMPLETED and closes ES', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed())
    await flushPromises()
    es.emit({ event: 'processing_completed', data: { last_event_at: '2026-04-30T10:00:03Z' } })
    await flushPromises()
    expect(state.value!.status).toBe('COMPLETED')
    expect(es.closed).toBe(true)
  })

  it('processing_failed transitions status to FAILED', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed())
    await flushPromises()
    es.emit({ event: 'processing_failed', data: { last_event_at: '2026-04-30T10:00:03Z', error_message: 'boom' } })
    await flushPromises()
    expect(state.value!.status).toBe('FAILED')
    expect(state.value!.error_message).toBe('boom')
    expect(es.closed).toBe(true)
  })

  it('job_cancelling shows cancelling state', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed())
    await flushPromises()
    es.emit({ event: 'job_cancelling', data: { last_event_at: '2026-04-30T10:00:03Z' } })
    await flushPromises()
    expect(state.value!.cancelling).toBe(true)
  })

  it('terminal seed closes ES immediately', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.resolve(baseSeed({ status: 'COMPLETED', completed_at: '2026-04-30T10:01:00Z' }))
    await flushPromises()
    expect(es.closed).toBe(true)
  })

  it('404 surfaces error.kind = "404"', async () => {
    const es = new MockEventSource()
    const d = deferred<JobState>()
    const { error, isLoading } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher: () => d.promise,
    })
    d.reject({ kind: '404' })
    await flushPromises()
    expect(error.value?.kind).toBe('404')
    expect(isLoading.value).toBe(false)
  })
})
