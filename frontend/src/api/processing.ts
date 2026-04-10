import type { ProcessingStatus } from '@/types'
import { apiClient } from './client'

export interface ProcessingOptions {
  preset_name?: string
  run_eval?: boolean
  auto_retry?: boolean
  skip_eval?: boolean
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

export interface SSEHandlers {
  onSectionStarted?: (data: { section_id: number; title: string; index: number; total: number }) => void
  onSectionCompleted?: (data: { section_id: number; title: string; index: number; total: number }) => void
  onProcessingCompleted?: (data: { book_id: number }) => void
  onProcessingFailed?: (data: { book_id: number; error: string }) => void
  onError?: (error: Event) => void
}

export function connectSSE(jobId: number, handlers: SSEHandlers): EventSource {
  const source = new EventSource(`/api/v1/processing/${jobId}/stream`)

  if (handlers.onSectionStarted) {
    source.addEventListener('section_started', (e) => {
      handlers.onSectionStarted!(JSON.parse(e.data))
    })
  }
  if (handlers.onSectionCompleted) {
    source.addEventListener('section_completed', (e) => {
      handlers.onSectionCompleted!(JSON.parse(e.data))
    })
  }
  if (handlers.onProcessingCompleted) {
    source.addEventListener('processing_completed', (e) => {
      handlers.onProcessingCompleted!(JSON.parse(e.data))
      source.close()
    })
  }
  if (handlers.onProcessingFailed) {
    source.addEventListener('processing_failed', (e) => {
      handlers.onProcessingFailed!(JSON.parse(e.data))
      source.close()
    })
  }
  if (handlers.onError) {
    source.onerror = handlers.onError
  }

  return source
}
