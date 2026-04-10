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
