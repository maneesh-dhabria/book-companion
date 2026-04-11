import { apiClient } from './client'
import type { QuickSearchResponse, RecentSearch, SearchResultItem } from '@/types'

export async function quickSearch(
  q: string,
  limit: number = 12,
  bookId?: number,
): Promise<QuickSearchResponse> {
  return apiClient.get<QuickSearchResponse>('/search/quick', {
    q,
    limit,
    book_id: bookId,
  })
}

export async function fullSearch(params: {
  q: string
  source_type?: string
  book_id?: number
  tag?: string
  page?: number
  per_page?: number
}): Promise<{ items: SearchResultItem[]; total: number; page: number; per_page: number }> {
  return apiClient.get('/search', params)
}

export async function getRecentSearches(): Promise<RecentSearch[]> {
  return apiClient.get<RecentSearch[]>('/search/recent')
}

export async function clearRecentSearches(): Promise<void> {
  return apiClient.delete('/search/recent')
}
