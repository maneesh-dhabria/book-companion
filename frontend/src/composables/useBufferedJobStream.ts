import { getCurrentInstance, onUnmounted, ref, type Ref } from 'vue'

export interface JobProgress {
  current: number
  total: number
  current_section_title: string
  eta_seconds: number | null
}

export interface JobState {
  id: number
  book_id: number
  book_title: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  scope: string
  section_id: number | null
  progress: JobProgress
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  last_event_at: string | null
  failures?: number
  retrying_section_id?: number | null
  cancelling?: boolean
}

export interface SseEvent {
  event:
    | 'section_started'
    | 'section_completed'
    | 'section_failed'
    | 'section_skipped'
    | 'section_retry'
    | 'section_audio_completed'
    | 'section_audio_failed'
    | 'section_audio_already_stale'
    | 'processing_completed'
    | 'processing_failed'
    | 'job_cancelling'
    | 'job_queued'
    | 'job_promoted'
    | 'close'
  data: {
    last_event_at?: string
    section_id?: number
    section_title?: string
    error?: string
    error_message?: string
  }
}

export interface JobError {
  kind: '404' | 'network'
  message?: string
}

export interface UseBufferedJobStreamOptions {
  eventSourceFactory?: () => EventSource
  fetcher?: () => Promise<JobState>
}

export interface UseBufferedJobStreamReturn {
  state: Ref<JobState | null>
  error: Ref<JobError | null>
  isLoading: Ref<boolean>
}

/**
 * Deep-link job stream — opens an EventSource and a GET in parallel.
 * SSE events that arrive before the GET response are buffered, then
 * drained against the seed's `last_event_at` timestamp so we never
 * double-count a transition.
 *
 * Decision Log P9: this composable is the unit of test for FR-12 / E14.
 */
export function useBufferedJobStream(
  jobId: number,
  opts: UseBufferedJobStreamOptions = {},
): UseBufferedJobStreamReturn {
  const state = ref<JobState | null>(null)
  const error = ref<JobError | null>(null)
  const isLoading = ref(true)

  let buffer: SseEvent[] = []
  let mode: 'buffer' | 'live' = 'buffer'
  let lastAppliedAt: string | null = null
  let es: EventSource | null = null
  let closed = false

  function applyEvent(ev: SseEvent) {
    if (!state.value) return
    const s = state.value
    switch (ev.event) {
      case 'section_started':
        s.progress.current_section_title =
          ev.data.section_title ?? s.progress.current_section_title
        break
      case 'section_completed':
        s.progress.current = (s.progress.current ?? 0) + 1
        break
      case 'section_failed':
        s.failures = (s.failures ?? 0) + 1
        break
      // Audio-job events (Phase B) — same shape as section_completed, different name.
      case 'section_audio_completed':
        s.progress.current = (s.progress.current ?? 0) + 1
        break
      case 'section_audio_failed':
        s.failures = (s.failures ?? 0) + 1
        break
      case 'section_audio_already_stale':
        s.progress.current = (s.progress.current ?? 0) + 1
        break
      case 'section_retry':
        s.retrying_section_id = ev.data.section_id ?? null
        break
      case 'processing_completed':
        s.status = 'COMPLETED'
        if (ev.data.last_event_at) s.completed_at = ev.data.last_event_at
        closeStream()
        break
      case 'processing_failed':
        s.status = 'FAILED'
        s.error_message = ev.data.error_message ?? s.error_message
        if (ev.data.last_event_at) s.completed_at = ev.data.last_event_at
        closeStream()
        break
      case 'job_cancelling':
        s.cancelling = true
        break
      case 'close':
        closeStream()
        break
      // 'job_queued' / 'job_promoted' intentionally not consumed.
    }
  }

  function closeStream() {
    if (closed) return
    closed = true
    es?.close()
  }

  function start() {
    const esFactory =
      opts.eventSourceFactory ??
      (() => new EventSource(`/api/v1/processing/${jobId}/stream`))
    es = esFactory()
    es.onmessage = (m: MessageEvent) => {
      let ev: SseEvent
      try {
        ev = JSON.parse(m.data) as SseEvent
      } catch {
        return
      }
      if (mode === 'buffer') {
        buffer.push(ev)
        return
      }
      const ts = ev.data?.last_event_at
      if (!ts || !lastAppliedAt || ts > lastAppliedAt) {
        applyEvent(ev)
        if (ts) lastAppliedAt = ts
      }
    }
    es.onerror = () => {
      // Reconnect path: drop back into buffer mode and re-seed via GET.
      // The next message that arrives after the seed will rebuild state.
      if (closed) return
      mode = 'buffer'
      buffer = []
      const fetcher2 =
        opts.fetcher ??
        (() =>
          fetch(`/api/v1/processing/${jobId}`).then((r) =>
            r.status === 404 ? Promise.reject({ kind: '404' }) : r.json(),
          ))
      fetcher2()
        .then((seed) => {
          if (seed.status) {
            seed.status = String(seed.status).toUpperCase() as JobState['status']
          }
          if (!seed.progress) {
            seed.progress = { current: 0, total: 0, current_section_title: '', eta_seconds: null }
          }
          state.value = seed
          lastAppliedAt = seed.last_event_at
          mode = 'live'
        })
        .catch(() => {
          // Stay in degraded state; UI surfaces the cached state.
        })
    }

    const fetcher =
      opts.fetcher ??
      (() =>
        fetch(`/api/v1/processing/${jobId}`).then((r) =>
          r.status === 404 ? Promise.reject({ kind: '404' }) : r.json(),
        ))
    fetcher()
      .then((seed: JobState) => {
        // Backend ProcessingJobStatus enum serializes lowercase ("running",
        // "completed", ...). The view's v-if branches compare against the
        // uppercase literals from the type contract, so normalize here.
        if (seed.status) {
          seed.status = String(seed.status).toUpperCase() as JobState['status']
        }
        // Likewise tolerate `progress: null` from the API (no progress yet
        // recorded) — the view destructures `state.progress.current`.
        if (!seed.progress) {
          seed.progress = { current: 0, total: 0, current_section_title: '', eta_seconds: null }
        }
        state.value = seed
        lastAppliedAt = seed.last_event_at
        // Drain buffer
        for (const ev of buffer) {
          const ts = ev.data?.last_event_at
          if (!ts || !lastAppliedAt || ts > lastAppliedAt) {
            applyEvent(ev)
            if (ts) lastAppliedAt = ts
          }
        }
        buffer = []
        mode = 'live'
        isLoading.value = false
        if (seed.status === 'COMPLETED' || seed.status === 'FAILED') closeStream()
      })
      .catch((e: { kind?: string; message?: string }) => {
        error.value = { kind: e?.kind === '404' ? '404' : 'network', message: e?.message }
        isLoading.value = false
      })
  }

  // Only register lifecycle hook when called from inside a component
  // setup; tests call this composable directly.
  if (getCurrentInstance()) {
    onUnmounted(() => closeStream())
  }
  start()
  return { state, error, isLoading }
}
