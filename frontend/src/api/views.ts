import type { LibraryView } from '@/types'
import { apiClient } from './client'

export function listViews() {
  return apiClient.get<LibraryView[]>('/views')
}

export function createView(data: {
  name: string
  display_mode?: string
  sort_field?: string
  sort_direction?: string
  filters?: Record<string, unknown>
  table_columns?: Record<string, unknown>
}) {
  return apiClient.post<LibraryView>('/views', data)
}

export function updateView(id: number, data: Partial<Omit<LibraryView, 'id' | 'created_at' | 'updated_at'>>) {
  return apiClient.patch<LibraryView>(`/views/${id}`, data)
}

export function deleteView(id: number) {
  return apiClient.delete(`/views/${id}`)
}

export function reorderViews(ids: number[]) {
  return apiClient.post<LibraryView[]>('/views/reorder', { view_ids: ids })
}
