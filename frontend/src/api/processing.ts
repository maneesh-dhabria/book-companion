import type { ProcessingStatus } from '@/types'
import { apiClient } from './client'

export type ProcessingScope = 'all' | 'pending' | 'section'

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
}

export interface ProcessingFailedPayload {
  book_id: number
  error: string
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
