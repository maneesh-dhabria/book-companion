import { apiClient } from './client'
import type { Concept, ConceptDetail, PaginatedResponse } from '@/types'

export async function listConcepts(params?: {
  book_id?: number
  user_edited?: boolean
  sort?: string
  page?: number
  per_page?: number
}): Promise<PaginatedResponse<Concept>> {
  return apiClient.get<PaginatedResponse<Concept>>('/concepts', params)
}

export async function getConcept(id: number): Promise<ConceptDetail> {
  return apiClient.get<ConceptDetail>(`/concepts/${id}`)
}

export async function updateConcept(
  id: number,
  data: { term?: string; definition?: string },
): Promise<Concept> {
  return apiClient.patch<Concept>(`/concepts/${id}`, data)
}

export async function resetConcept(id: number): Promise<Concept> {
  return apiClient.post<Concept>(`/concepts/${id}/reset`)
}

export async function deleteConcept(id: number): Promise<void> {
  return apiClient.delete(`/concepts/${id}`)
}
