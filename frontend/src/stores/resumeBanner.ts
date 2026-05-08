import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { AudioContentType } from '@/api/audio'

export type ResumeChoice = 'reading' | 'listening' | null

export const useResumeBannerStore = defineStore('resumeBanner', () => {
  // Reading branch
  const lastBookId = ref<number | null>(null)
  const lastSectionId = ref<number | null>(null)
  const lastBookTitle = ref<string | null>(null)
  const lastSectionTitle = ref<string | null>(null)
  const lastViewedAt = ref<string | null>(null)

  // Audio branch
  const lastAudioContentType = ref<AudioContentType | null>(null)
  const lastAudioContentId = ref<number | null>(null)
  const lastAudioBookId = ref<number | null>(null)
  const lastAudioBookTitle = ref<string | null>(null)
  const lastAudioSectionTitle = ref<string | null>(null)
  const lastAudioAt = ref<string | null>(null)
  const lastAudioTotalSentences = ref<number | null>(null)

  const loaded = ref(false)

  const chosen = computed<ResumeChoice>(() => {
    const r = lastViewedAt.value
    const a = lastAudioAt.value
    if (!r && !a) return null
    if (r && !a) return 'reading'
    if (a && !r) return 'listening'
    // Both present — tie-break: reading wins on equal timestamps (FR-B06).
    if (a! > r!) return 'listening'
    return 'reading'
  })

  function reset() {
    lastBookId.value = null
    lastSectionId.value = null
    lastBookTitle.value = null
    lastSectionTitle.value = null
    lastViewedAt.value = null
    lastAudioContentType.value = null
    lastAudioContentId.value = null
    lastAudioBookId.value = null
    lastAudioBookTitle.value = null
    lastAudioSectionTitle.value = null
    lastAudioAt.value = null
    lastAudioTotalSentences.value = null
  }

  async function load(): Promise<void> {
    try {
      const res = await fetch('/api/v1/reading-state/resume-banner')
      if (!res.ok) {
        // Treat any non-2xx as "no banner"; do not toast.
        reset()
        loaded.value = true
        return
      }
      const body = (await res.json()) as Record<string, unknown> | null
      const b = body ?? {}
      lastBookId.value = (b.last_book_id as number | null) ?? null
      lastSectionId.value = (b.last_section_id as number | null) ?? null
      lastBookTitle.value = (b.last_book_title as string | null) ?? null
      lastSectionTitle.value = (b.last_section_title as string | null) ?? null
      lastViewedAt.value = (b.last_viewed_at as string | null) ?? null
      lastAudioContentType.value =
        (b.last_audio_content_type as AudioContentType | null) ?? null
      lastAudioContentId.value = (b.last_audio_content_id as number | null) ?? null
      lastAudioBookId.value = (b.last_audio_book_id as number | null) ?? null
      lastAudioBookTitle.value = (b.last_audio_book_title as string | null) ?? null
      lastAudioSectionTitle.value =
        (b.last_audio_section_title as string | null) ?? null
      lastAudioAt.value = (b.last_audio_at as string | null) ?? null
      lastAudioTotalSentences.value =
        (b.last_audio_total_sentences as number | null) ?? null
      loaded.value = true
    } catch (err) {
      console.warn('resume-banner-fetch-failed', err)
      reset()
      loaded.value = true
    }
  }

  return {
    lastBookId,
    lastSectionId,
    lastBookTitle,
    lastSectionTitle,
    lastViewedAt,
    lastAudioContentType,
    lastAudioContentId,
    lastAudioBookId,
    lastAudioBookTitle,
    lastAudioSectionTitle,
    lastAudioAt,
    lastAudioTotalSentences,
    loaded,
    chosen,
    load,
  }
})
