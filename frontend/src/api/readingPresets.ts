import { apiClient } from './client'
import type { ReadingPreset } from '@/types'

export interface ReadingPresetListResponse {
  items: ReadingPreset[]
}

export async function listPresets(): Promise<ReadingPresetListResponse> {
  return apiClient.get<ReadingPresetListResponse>('/reading-presets')
}
