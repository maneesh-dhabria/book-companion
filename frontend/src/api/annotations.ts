import { apiClient } from './client'
import type { Annotation, PaginatedResponse } from '@/types'

export async function listAnnotations(params?: {
  content_type?: string
  content_id?: number
  book_id?: number
  type?: string
  page?: number
  per_page?: number
}): Promise<PaginatedResponse<Annotation>> {
  return apiClient.get<PaginatedResponse<Annotation>>('/annotations', params)
}

export async function getAnnotation(id: number): Promise<Annotation> {
  return apiClient.get<Annotation>(`/annotations/${id}`)
}

export async function createAnnotation(data: {
  content_type: string
  content_id: number
  type: string
  selected_text?: string | null
  text_start?: number | null
  text_end?: number | null
  note?: string | null
}): Promise<Annotation> {
  return apiClient.post<Annotation>('/annotations', data)
}

export async function updateAnnotation(
  id: number,
  data: { note?: string | null; type?: string },
): Promise<Annotation> {
  return apiClient.patch<Annotation>(`/annotations/${id}`, data)
}

export async function deleteAnnotation(id: number): Promise<void> {
  return apiClient.delete(`/annotations/${id}`)
}

export async function linkAnnotation(id: number, targetId: number): Promise<Annotation> {
  return apiClient.post<Annotation>(`/annotations/${id}/link`, { target_annotation_id: targetId })
}

export async function unlinkAnnotation(id: number): Promise<Annotation> {
  return apiClient.delete(`/annotations/${id}/link`) as unknown as Promise<Annotation>
}

export function exportAnnotationsUrl(format: 'markdown' | 'json' | 'csv', bookId?: number): string {
  const params = new URLSearchParams({ format })
  if (bookId) params.set('book_id', String(bookId))
  return `/api/v1/annotations/export?${params}`
}
