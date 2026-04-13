import { apiClient } from './client'
import type { ReadingPreset } from '@/types'

export interface ReadingPresetListResponse {
  items: ReadingPreset[]
  default_id: number | null
}

export async function listPresets(): Promise<ReadingPresetListResponse> {
  return apiClient.get<ReadingPresetListResponse>('/reading-presets')
}

export async function createPreset(
  data: Omit<ReadingPreset, 'id' | 'is_system' | 'is_active' | 'created_at'>,
): Promise<ReadingPreset> {
  return apiClient.post<ReadingPreset>('/reading-presets', data)
}

export async function updatePreset(
  id: number,
  data: Partial<Omit<ReadingPreset, 'id' | 'is_system' | 'is_active' | 'created_at'>>,
): Promise<ReadingPreset> {
  return apiClient.patch<ReadingPreset>(`/reading-presets/${id}`, data)
}

export async function deletePreset(id: number): Promise<void> {
  return apiClient.delete(`/reading-presets/${id}`)
}

export async function activatePreset(id: number): Promise<ReadingPreset> {
  return apiClient.post<ReadingPreset>(`/reading-presets/${id}/activate`)
}
