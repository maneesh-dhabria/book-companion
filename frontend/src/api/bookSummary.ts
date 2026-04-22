import { apiClient } from './client'

export interface StartBookSummaryBody {
  preset_name: string
  skip_eval?: boolean
  no_retry?: boolean
}

export function startBookSummary(bookId: number, body: StartBookSummaryBody) {
  return apiClient.post<{ job_id: number }>(`/books/${bookId}/book-summary`, body)
}
