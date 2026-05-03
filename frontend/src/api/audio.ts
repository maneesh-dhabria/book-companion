import { apiClient } from '@/api/client'

/**
 * Persistable content types — the subset accepted by the backend's
 * `ContentType` enum and audio_files / audio_positions CHECK constraints.
 * Use this for any API call that persists audio (lookup, inventory, position).
 *
 * The wider runtime union `TtsContentType` (in `@/stores/ttsPlayer`) adds
 * `'annotation'` for engine routing only — that never round-trips to the
 * backend (single-annotation playback is Web Speech only and not persisted).
 */
export type AudioContentType =
  | 'section_summary'
  | 'book_summary'
  | 'section_content'
  | 'annotations_playlist'

export interface AudioLookupResponse {
  pregenerated: boolean
  url?: string | null
  voice?: string | null
  engine?: string | null
  duration_seconds?: number | null
  sentence_offsets_seconds?: number[] | null
  sentence_offsets_chars: number[]
  sanitized_text: string
  stale?: { reason: 'source_changed' | 'sanitizer_upgraded' | 'segmenter_drift' } | null
  source_hash?: string | null
}

export interface AudioInventoryItem {
  content_type: AudioContentType
  content_id: number
  voice: string
  engine: string
  url: string
  size_bytes: number
  duration_seconds: number
  sentence_count: number
  source_hash: string
  generated_at: string
}

export interface AudioInventoryResponse {
  book_id: number
  files: AudioInventoryItem[]
  coverage: { total: number; generated: number }
}

export interface AudioJobResponse {
  job_id: number
  scope: string
  total_units: number
}

export interface AudioJobRequest {
  scope: 'book' | 'sections' | 'all'
  section_ids?: number[]
  voice: string
  engine: 'kokoro'
}

export const audioApi = {
  lookup(params: {
    book_id: number
    content_type: AudioContentType
    content_id: number
    voice?: string
  }): Promise<AudioLookupResponse> {
    return apiClient.get<AudioLookupResponse>('/audio/lookup', params)
  },

  inventory(bookId: number): Promise<AudioInventoryResponse> {
    return apiClient.get<AudioInventoryResponse>(`/books/${bookId}/audio`)
  },

  start(bookId: number, body: AudioJobRequest): Promise<AudioJobResponse> {
    return apiClient.post<AudioJobResponse>(`/books/${bookId}/audio`, body)
  },

  deleteAll(bookId: number): Promise<void> {
    return apiClient.delete(`/books/${bookId}/audio`)
  },

  deleteOne(bookId: number, contentType: AudioContentType, contentId: number): Promise<void> {
    return apiClient.delete(`/books/${bookId}/audio/${contentType}/${contentId}`)
  },

  mp3Url(bookId: number, contentType: AudioContentType, contentId: number): string {
    return `/api/v1/books/${bookId}/audio/${contentType}/${contentId}.mp3`
  },
}
