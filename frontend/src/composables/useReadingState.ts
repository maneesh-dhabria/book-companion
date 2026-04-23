import { onMounted, watch } from 'vue'
import { useReadingStateStore } from '@/stores/readingState'

/**
 * Track reading position for the current book/section.
 * Call in BookDetailView — debounces to avoid excessive API calls.
 */
export function useReadingState(
  bookId: () => number | undefined,
  sectionId: () => number | undefined,
  sectionType: () => string | undefined = () => undefined,
) {
  const store = useReadingStateStore()

  onMounted(() => {
    const bid = bookId()
    if (bid) {
      store.trackPosition(bid, sectionId(), sectionType())
    }
  })

  watch(
    [bookId, sectionId, sectionType],
    ([newBookId, newSectionId, newSectionType]) => {
      if (newBookId) {
        store.trackPosition(newBookId, newSectionId, newSectionType)
      }
    },
  )
}
