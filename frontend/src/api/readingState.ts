import { apiClient } from './client'

export interface ReadingStateResponse {
  last_book_id: number | null
  last_section_id: number | null
  last_viewed_at: string | null
  book_title: string | null
  section_title: string | null
}

export function updateReadingState(bookId: number, sectionId?: number) {
  return apiClient.put<ReadingStateResponse>('/reading-state', {
    book_id: bookId,
    section_id: sectionId ?? null,
  })
}

export function getContinueReading() {
  return apiClient.get<ReadingStateResponse>('/reading-state/continue')
}
