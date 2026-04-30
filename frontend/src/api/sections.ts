import type { Section } from '@/types'
import { apiClient } from './client'

export function listSections(bookId: number) {
  return apiClient.get<Section[]>(`/books/${bookId}/sections`)
}

export function getSection(bookId: number, sectionId: number) {
  return apiClient.get<Section>(`/books/${bookId}/sections/${sectionId}`)
}

export function mergeSections(bookId: number, sectionIds: number[], title: string) {
  return apiClient.post<Section>(`/books/${bookId}/sections/merge`, { section_ids: sectionIds, title })
}

export function splitSection(bookId: number, sectionId: number, mode: string, positions?: number[]) {
  return apiClient.post<Section[]>(`/books/${bookId}/sections/${sectionId}/split`, { mode, positions })
}

export function deleteSection(bookId: number, sectionId: number) {
  return apiClient.delete(`/books/${bookId}/sections/${sectionId}`)
}

export function patchSection(
  bookId: number,
  sectionId: number,
  payload: { title?: string; section_type?: string },
) {
  return apiClient.patch<Section>(`/books/${bookId}/sections/${sectionId}`, payload)
}

export function reorderSections(bookId: number, sectionIds: number[]) {
  return apiClient.post<Section[]>(`/books/${bookId}/sections/reorder`, {
    section_ids: sectionIds,
  })
}

export interface EditImpactResponse {
  summaries_to_invalidate: number[]
  invalidate_book_summary: boolean
  summarized_section_count: number
}

export function getEditImpact(bookId: number, sectionIds: number[]) {
  return apiClient.get<EditImpactResponse>(`/books/${bookId}/sections/edit-impact`, {
    section_ids: sectionIds.join(','),
  })
}

export interface SplitPreviewCandidate {
  title: string
  char_count: number
  first_line: string
  start: number
  end: number
}

export function getSplitPreview(
  bookId: number,
  sectionId: number,
  mode: 'heading' | 'paragraph' | 'char',
  position?: number,
) {
  const params: Record<string, string | number> = { mode }
  if (position !== undefined) params.position = position
  return apiClient.get<{ candidates: SplitPreviewCandidate[]; mode: string }>(
    `/books/${bookId}/sections/${sectionId}/split-preview`,
    params,
  )
}
