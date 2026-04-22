import { apiClient } from './client'

export interface SummarizerPreset {
  id: string
  label: string
  description: string
  facets: Record<string, string>
  system: boolean
}

export interface SummarizerPresetListResponse {
  presets: SummarizerPreset[]
  default_id: string | null
}

export function listSummarizerPresets() {
  return apiClient.get<SummarizerPresetListResponse>('/summarize/presets')
}
