import { getBook } from '@/api/books'
import { getSection } from '@/api/sections'
import {
  connectSSE,
  getProcessingStatus,
  startProcessing,
  type ProcessingOptions,
  type ProcessingScope,
  type SectionEventPayload,
  type SectionFailedPayload,
  type SectionSkippedPayload,
} from '@/api/processing'
import { useReaderStore } from '@/stores/reader'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const GRACE_MS = 30_000
const POLL_MS = 5_000

export const useSummarizationJobStore = defineStore('summarizationJob', () => {
  const bookId = ref<number | null>(null)
  const jobId = ref<number | null>(null)
  const activeJobSectionId = ref<number | null>(null)
  const scope = ref<ProcessingScope | null>(null)
  const failedSections = ref<Map<number, string>>(new Map())
  const source = ref<EventSource | null>(null)
  // NFR-10 / FR-A7.5 — idempotent per-event dedup. Section ids memoized
  // per-event so a replay of {section_completed, section_failed,
  // section_skipped} is a no-op.
  const _seenCompleted = ref<Set<number>>(new Set())
  const _seenFailed = ref<Set<number>>(new Set())
  const _seenSkipped = ref<Set<number>>(new Set())
  // Reconcile-only aggregate counters (populated by GET /processing/:id on
  // SSE error; stays 0/null otherwise so the UI reflects SSE-driven state).
  const reconciledCompleted = ref<number | null>(null)
  const reconciledFailed = ref<number | null>(null)
  const reconciledSkipped = ref<number | null>(null)

  // Generic last-event observation surface so child components (e.g.
  // SectionListTable) can react to SSE without each opening their own
  // EventSource. Set inside every on* handler below; consumers watch
  // this ref by reference identity (we always assign a new object).
  type LastJobEvent = {
    event:
      | 'section_started'
      | 'section_completed'
      | 'section_failed'
      | 'section_skipped'
      | 'section_retry'
      | 'processing_completed'
      | 'processing_failed'
    data: { section_id?: number; error?: string }
  }
  const lastEvent = ref<LastJobEvent | null>(null)

  let graceTimer: ReturnType<typeof setTimeout> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let sawAnyEvent = false

  const isActive = computed(() => jobId.value !== null)
  const completedCount = computed(() =>
    reconciledCompleted.value !== null
      ? reconciledCompleted.value
      : _seenCompleted.value.size,
  )
  const failedCount = computed(() =>
    reconciledFailed.value !== null
      ? reconciledFailed.value
      : _seenFailed.value.size,
  )
  const skippedCount = computed(() =>
    reconciledSkipped.value !== null
      ? reconciledSkipped.value
      : _seenSkipped.value.size,
  )
  const getFailedError = (id: number) => failedSections.value.get(id)

  function cancelGrace() {
    if (graceTimer) {
      clearTimeout(graceTimer)
      graceTimer = null
    }
  }

  function cancelPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function pollOnce() {
    if (!bookId.value) return
    try {
      const book = await getBook(bookId.value)
      useReaderStore().setBook(book)
      const sp = (
        book as { summary_progress?: { summarized: number; total: number } }
      ).summary_progress
      if (sp && sp.summarized >= sp.total) {
        reset(true)
      }
    } catch (e) {
      console.warn('summary_progress poll failed', e)
    }
  }

  function startGrace() {
    cancelGrace()
    graceTimer = setTimeout(() => {
      if (sawAnyEvent) return
      pollTimer = setInterval(pollOnce, POLL_MS)
    }, GRACE_MS)
  }

  function onSectionStarted(d: Pick<SectionEventPayload, 'section_id'>) {
    sawAnyEvent = true
    cancelGrace()
    activeJobSectionId.value = d.section_id
    lastEvent.value = { event: 'section_started', data: { section_id: d.section_id } }
  }

  async function onSectionCompleted(d: Pick<SectionEventPayload, 'section_id'>) {
    activeJobSectionId.value = null
    lastEvent.value = { event: 'section_completed', data: { section_id: d.section_id } }
    if (_seenCompleted.value.has(d.section_id)) return
    _seenCompleted.value.add(d.section_id)
    if (!bookId.value) return
    try {
      const fresh = await getSection(bookId.value, d.section_id)
      useReaderStore().updateSection(fresh)
    } catch (e) {
      console.warn(`refetch section ${d.section_id} failed`, e)
    }
    try {
      const book = await getBook(bookId.value)
      useReaderStore().setBook(book)
    } catch {
      // noop — next SSE event will retry progress
    }
  }

  function onSectionFailed(d: SectionFailedPayload) {
    activeJobSectionId.value = null
    lastEvent.value = { event: 'section_failed', data: { section_id: d.section_id, error: d.error } }
    if (_seenFailed.value.has(d.section_id)) return
    _seenFailed.value.add(d.section_id)
    failedSections.value.set(d.section_id, d.error)
  }

  function onSectionSkipped(d: SectionSkippedPayload) {
    lastEvent.value = { event: 'section_skipped', data: { section_id: d.section_id } }
    if (_seenSkipped.value.has(d.section_id)) return
    _seenSkipped.value.add(d.section_id)
  }

  function onSectionRetrying(d: Pick<SectionEventPayload, 'section_id'>) {
    activeJobSectionId.value = d.section_id
    lastEvent.value = { event: 'section_retry', data: { section_id: d.section_id } }
  }

  async function onSSEError() {
    activeJobSectionId.value = null
    if (!pollTimer) pollTimer = setInterval(pollOnce, POLL_MS)
    // FR-A7.5 — best-effort reconcile: read the authoritative counts from
    // the status endpoint so the UI can show "X of Y done" even after we
    // drop SSE events.
    if (jobId.value === null) return
    try {
      const status = await getProcessingStatus(jobId.value)
      const prog = (status as { progress?: { completed?: number; failed?: number; skipped?: number } }).progress
      if (prog) {
        if (typeof prog.completed === 'number') reconciledCompleted.value = prog.completed
        if (typeof prog.failed === 'number') reconciledFailed.value = prog.failed
        if (typeof prog.skipped === 'number') reconciledSkipped.value = prog.skipped
      }
    } catch (e) {
      console.warn('job reconcile failed', e)
    }
  }

  function onCompleted() {
    lastEvent.value = { event: 'processing_completed', data: {} }
    reset(false)
  }

  function onFailed(err: string) {
    // Error is surfaced per-section via onSectionFailed; the job-level
    // handler just clears the active state. Kept as a named param for
    // callers that pass the SSE error payload.
    lastEvent.value = { event: 'processing_failed', data: { error: err } }
    reset(false)
  }

  async function startJob(bookIdIn: number, opts: ProcessingOptions) {
    if (opts.scope === 'section' && opts.section_id !== undefined) {
      failedSections.value.delete(opts.section_id)
      _seenFailed.value.delete(opts.section_id)
      _seenCompleted.value.delete(opts.section_id)
    }
    // Starting a fresh run invalidates the reconciled-count cache.
    reconciledCompleted.value = null
    reconciledFailed.value = null
    reconciledSkipped.value = null
    const { job_id } = await startProcessing(bookIdIn, opts)
    bookId.value = bookIdIn
    jobId.value = job_id
    scope.value = opts.scope ?? 'all'
    sawAnyEvent = false
    startGrace()
    source.value = connectSSE(job_id, {
      onProcessingStarted: () => {
        sawAnyEvent = true
        cancelGrace()
      },
      onSectionStarted: (d) => {
        onSectionStarted(d)
      },
      onSectionCompleted: (d) => {
        sawAnyEvent = true
        void onSectionCompleted(d)
      },
      onSectionFailed: (d) => {
        sawAnyEvent = true
        onSectionFailed(d)
      },
      onSectionSkipped: (d) => {
        sawAnyEvent = true
        onSectionSkipped(d)
      },
      onSectionRetrying: (d) => {
        sawAnyEvent = true
        onSectionRetrying(d)
      },
      onProcessingCompleted: () => onCompleted(),
      onProcessingFailed: (d) => onFailed(d.error),
      onError: () => {
        void onSSEError()
      },
    })
  }

  function reset(closeSource = true) {
    cancelGrace()
    cancelPolling()
    if (closeSource && source.value) source.value.close()
    source.value = null
    jobId.value = null
    activeJobSectionId.value = null
    scope.value = null
    _seenCompleted.value.clear()
    _seenFailed.value.clear()
    _seenSkipped.value.clear()
    reconciledCompleted.value = null
    reconciledFailed.value = null
    reconciledSkipped.value = null
    // P14: bookId + failedSections preserved across job completion.
  }

  return {
    bookId,
    jobId,
    activeJobSectionId,
    scope,
    failedSections,
    lastEvent,
    isActive,
    completedCount,
    failedCount,
    skippedCount,
    getFailedError,
    startJob,
    reset,
    onSectionStarted,
    onSectionCompleted,
    onSectionFailed,
    onSectionSkipped,
    onSectionRetrying,
    onSSEError,
    onCompleted,
    onFailed,
  }
})
