import type { BookEvalResult, EvalResult } from '@/types'
import { apiClient } from './client'

export function getSectionEval(sectionId: number) {
  return apiClient.get<EvalResult>(`/eval/section/${sectionId}`)
}

export function getBookEval(bookId: number) {
  return apiClient.get<BookEvalResult>(`/eval/book/${bookId}`)
}
