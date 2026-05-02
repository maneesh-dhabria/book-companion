import { describe, expect, it, vi } from 'vitest'
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

const seed = (last_event_at: string, current: number = 5): JobState => ({
  id: 42,
  book_id: 1,
  book_title: 'B',
  status: 'RUNNING',
  scope: 'all',
  section_id: null,
  progress: { current, total: 10, current_section_title: '', eta_seconds: null },
  started_at: '2026-04-30T10:00:00Z',
  completed_at: null,
  error_message: null,
  last_event_at,
})

describe('useBufferedJobStream — 5-step contract on reconnect', () => {
  it('initial connect: subscribe → buffer → fetch → reconcile → live', async () => {
    const es = new MockEventSource()
    const fetcher = vi.fn(async () => seed('2026-04-30T10:00:01.500Z'))
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher,
    })
    // Subscribe before fetch resolves; buffer events
    es.emit({
      event: 'section_completed',
      data: { last_event_at: '2026-04-30T10:00:01.000Z', section_id: 6 },
    })
    es.emit({
      event: 'section_completed',
      data: { last_event_at: '2026-04-30T10:00:02.000Z', section_id: 7 },
    })
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(1)
    // Pre-snapshot event dropped; post-snapshot event applied.
    expect(state.value!.progress.current).toBe(6)
  })

  it('reconnect: re-runs fetch when EventSource errors', async () => {
    const es = new MockEventSource()
    const fetcher = vi.fn(async () => seed('2026-04-30T10:00:01.500Z'))
    useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher,
    })
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(1)
    es.fail()
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('drops events with last_event_at <= snapshot.last_event_at', async () => {
    const es = new MockEventSource()
    const fetcher = vi.fn(async () => seed('2026-04-30T10:00:05.000Z', 5))
    const { state } = useBufferedJobStream(42, {
      eventSourceFactory: () => es as unknown as EventSource,
      fetcher,
    })
    es.emit({
      event: 'section_completed',
      data: { last_event_at: '2026-04-30T10:00:04.000Z' },
    })
    es.emit({
      event: 'section_completed',
      data: { last_event_at: '2026-04-30T10:00:05.000Z' },
    })
    await flushPromises()
    // Both buffered events <= snapshot.last_event_at — neither applied.
    expect(state.value!.progress.current).toBe(5)
  })
})
