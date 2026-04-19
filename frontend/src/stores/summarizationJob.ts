import { getBook } from '@/api/books'
import { getSection } from '@/api/sections'
import {
  connectSSE,
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
  let graceTimer: ReturnType<typeof setTimeout> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let sawAnyEvent = false

  const isActive = computed(() => jobId.value !== null)
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
  }

  async function onSectionCompleted(d: Pick<SectionEventPayload, 'section_id'>) {
    activeJobSectionId.value = null
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
    failedSections.value.set(d.section_id, d.error)
    activeJobSectionId.value = null
  }

  function onSectionSkipped(_d: SectionSkippedPayload) {
    // progress refreshes on subsequent onSectionCompleted
  }

  function onSectionRetrying(d: Pick<SectionEventPayload, 'section_id'>) {
    activeJobSectionId.value = d.section_id
  }

  function onCompleted() {
    reset(false)
  }

  function onFailed(_err: string) {
    reset(false)
  }

  async function startJob(bookIdIn: number, opts: ProcessingOptions) {
    if (opts.scope === 'section' && opts.section_id !== undefined) {
      failedSections.value.delete(opts.section_id)
    }
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
        activeJobSectionId.value = null
        if (!pollTimer) pollTimer = setInterval(pollOnce, POLL_MS)
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
    // P14: bookId + failedSections preserved across job completion.
  }

  return {
    bookId,
    jobId,
    activeJobSectionId,
    scope,
    failedSections,
    isActive,
    getFailedError,
    startJob,
    reset,
    onSectionStarted,
    onSectionCompleted,
    onSectionFailed,
    onSectionSkipped,
    onSectionRetrying,
    onCompleted,
    onFailed,
  }
})
