import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as readingStateApi from '@/api/readingState'
import { FRONT_MATTER_TYPES } from '@/stores/reader'

export interface ContinueReading {
  bookId: number
  sectionId: number | null
  bookTitle: string
  sectionTitle: string | null
  lastViewedAt: string
}

export const useReadingStateStore = defineStore('readingState', () => {
  const continueReading = ref<ContinueReading | null>(null)
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function trackPosition(
    bookId: number,
    sectionId?: number,
    sectionType?: string,
  ) {
    // FR-E2.3 — don't persist a front-matter section as the last-read
    // position; the continue banner would land the user on the cover page
    // or TOC instead of the last real chapter they were reading.
    if (sectionType && FRONT_MATTER_TYPES.has(sectionType)) {
      return
    }
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(async () => {
      try {
        await readingStateApi.updateReadingState(bookId, sectionId)
      } catch {
        // Silent fail — position tracking is best-effort
      }
    }, 5000)
  }

  async function fetchContinueReading() {
    try {
      const data = await readingStateApi.getContinueReading()
      if (data.last_book_id && data.book_title) {
        continueReading.value = {
          bookId: data.last_book_id,
          sectionId: data.last_section_id,
          bookTitle: data.book_title,
          sectionTitle: data.section_title,
          lastViewedAt: data.last_viewed_at ?? '',
        }
      } else {
        continueReading.value = null
      }
    } catch {
      continueReading.value = null
    }
  }

  function dismiss() {
    continueReading.value = null
    sessionStorage.setItem('continue-banner-dismissed', 'true')
  }

  function isDismissed(): boolean {
    return sessionStorage.getItem('continue-banner-dismissed') === 'true'
  }

  return {
    continueReading,
    trackPosition,
    fetchContinueReading,
    dismiss,
    isDismissed,
  }
})
