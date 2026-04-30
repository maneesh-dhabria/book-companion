import type { ProcessingStatus } from '@/types'
import { apiClient } from './client'

export type ProcessingScope = 'all' | 'pending' | 'section' | 'failed'

export interface ProcessingOptions {
  preset_name?: string
  run_eval?: boolean
  auto_retry?: boolean
  skip_eval?: boolean
  force?: boolean
  scope?: ProcessingScope
  section_id?: number
}

export function startProcessing(bookId: number, options?: ProcessingOptions) {
  return apiClient.post<{ job_id: number }>(`/books/${bookId}/summarize`, options)
}

export function getProcessingStatus(jobId: number) {
  return apiClient.get<ProcessingStatus>(`/processing/${jobId}/status`)
}

export function cancelProcessing(jobId: number) {
  return apiClient.post<{ job_id: number; status: string; message: string }>(
    `/processing/${jobId}/cancel`,
  )
}

export interface ProcessingJobListItem {
  job_id: number
  book_id: number
  book_title: string
  status: string
  queue_position: number
  progress: unknown
  created_at: string | null
  started_at: string | null
  last_event_at: string | null
  cancel_requested: boolean
}

export function listProcessingJobs(statuses: string[] = ['PENDING', 'RUNNING']) {
  return apiClient.get<{ jobs: ProcessingJobListItem[] }>('/processing/jobs', {
    status: statuses.join(','),
  })
}

export interface ProcessingStartedPayload {
  book_id: number
  job_id: number
  scope: ProcessingScope
}

export interface SectionEventPayload {
  section_id: number
  title: string
  index: number
  total: number
}

export interface SectionCompletedPayload extends SectionEventPayload {
  elapsed_seconds?: number
}

export interface SectionFailedPayload extends SectionEventPayload {
  error: string
  error_type?: string
  error_message_truncated?: string | null
}

export interface SectionSkippedPayload extends SectionEventPayload {
  reason: string
}

export interface ProcessingCompletedPayload {
  book_id: number
  completed: number
  failed: number
  skipped: number
  /** T15 — set on book-level summary jobs, null otherwise. */
  book_summary_id?: number | null
  /** v1.5 T9b — AI tag suggestions produced by the book-summary job. */
  suggested_tags?: string[]
}

export interface ProcessingFailedPayload {
  book_id: number
  error: string
  /** v1.6: 'cancelled' | 'cli_disappeared' | 'error' */
  reason?: string
}

export interface JobQueuedPayload {
  job_id: number
  book_id: number
  last_event_at?: string
}

export interface JobPromotedPayload {
  job_id: number
  book_id: number
  last_event_at?: string
}

export interface JobCancellingPayload {
  job_id: number
  book_id?: number
  phase?: string
  last_event_at?: string
}

export interface SSEHandlers {
  onProcessingStarted?: (data: ProcessingStartedPayload) => void
  onSectionStarted?: (data: SectionEventPayload) => void
  onSectionCompleted?: (data: SectionCompletedPayload) => void
  onSectionFailed?: (data: SectionFailedPayload) => void
  onSectionSkipped?: (data: SectionSkippedPayload) => void
  onSectionRetrying?: (data: SectionEventPayload) => void
  onProcessingCompleted?: (data: ProcessingCompletedPayload) => void
  onProcessingFailed?: (data: ProcessingFailedPayload) => void
  onJobQueued?: (data: JobQueuedPayload) => void
  onJobPromoted?: (data: JobPromotedPayload) => void
  onJobCancelling?: (data: JobCancellingPayload) => void
  onError?: (error: Event) => void
}

export function connectSSE(jobId: number, handlers: SSEHandlers): EventSource {
  const source = new EventSource(`/api/v1/processing/${jobId}/stream`)

  const bind = (event: string, cb: ((d: unknown) => void) | undefined) => {
    if (!cb) return
    source.addEventListener(event, (e) => cb(JSON.parse((e as MessageEvent).data)))
  }

  bind('processing_started', handlers.onProcessingStarted as (d: unknown) => void)
  bind('section_started', handlers.onSectionStarted as (d: unknown) => void)
  bind('section_completed', handlers.onSectionCompleted as (d: unknown) => void)
  bind('section_failed', handlers.onSectionFailed as (d: unknown) => void)
  bind('section_skipped', handlers.onSectionSkipped as (d: unknown) => void)
  bind('section_retrying', handlers.onSectionRetrying as (d: unknown) => void)
  // v1.6 queue events (FR-F19, FR-F19a, FR-F19b)
  bind('job_queued', handlers.onJobQueued as (d: unknown) => void)
  bind('job_promoted', handlers.onJobPromoted as (d: unknown) => void)
  bind('job_cancelling', handlers.onJobCancelling as (d: unknown) => void)

  if (handlers.onProcessingCompleted) {
    source.addEventListener('processing_completed', (e) => {
      handlers.onProcessingCompleted!(JSON.parse((e as MessageEvent).data))
      source.close()
    })
  }
  if (handlers.onProcessingFailed) {
    source.addEventListener('processing_failed', (e) => {
      handlers.onProcessingFailed!(JSON.parse((e as MessageEvent).data))
      source.close()
    })
  }
  if (handlers.onError) {
    source.onerror = handlers.onError
  }

  return source
}
