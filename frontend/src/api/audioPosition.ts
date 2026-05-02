import { apiClient, ApiError } from '@/api/client'

import type { AudioContentType } from '@/api/audio'

export interface AudioPosition {
  sentence_index: number
  updated_at: string
  has_other_browser: boolean
  other_browser_updated_at?: string | null
}

export const audioPositionApi = {
  async get(params: {
    content_type: AudioContentType
    content_id: number
    browser_id: string
  }): Promise<AudioPosition | null> {
    try {
      return await apiClient.get<AudioPosition>('/audio_position', params)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }
  },

  put(body: {
    content_type: AudioContentType
    content_id: number
    browser_id: string
    sentence_index: number
  }): Promise<{ landed: boolean }> {
    return apiClient.put<{ landed: boolean }>('/audio_position', body)
  },
}

const BROWSER_ID_KEY = 'bookcompanion.browser-id'

export function getBrowserId(): string {
  if (typeof window === 'undefined' || !window.localStorage) {
    return 'fallback'
  }
  let id = window.localStorage.getItem(BROWSER_ID_KEY)
  if (!id) {
    id =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `b-${Date.now()}-${Math.random().toString(36).slice(2)}`
    window.localStorage.setItem(BROWSER_ID_KEY, id)
  }
  return id
}
