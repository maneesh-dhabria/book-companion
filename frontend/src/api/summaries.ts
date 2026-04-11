import type { Summary, SummaryComparison } from '@/types'
import { apiClient } from './client'

export function listSummaries(bookId: number) {
  return apiClient.get<Summary[]>(`/books/${bookId}/summaries`)
}

export function compareSummaries(id1: number, id2: number) {
  return apiClient.get<SummaryComparison>('/summaries/compare', { id1, id2 })
}

export function setDefault(summaryId: number) {
  return apiClient.post<Summary>(`/summaries/${summaryId}/set-default`)
}
