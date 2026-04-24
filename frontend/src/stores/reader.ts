import { getBook } from '@/api/books'
import { getSection, listSections } from '@/api/sections'
import type { Book, Section } from '@/types'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

// Mirrors backend/app/services/parser/section_classifier.py:FRONT_MATTER_TYPES
// and :SUMMARIZABLE_TYPES. A backend contract test enforces equality.
export const FRONT_MATTER_TYPES: ReadonlySet<string> = new Set([
  'copyright',
  'acknowledgments',
  'dedication',
  'title_page',
  'table_of_contents',
  'colophon',
  'cover',
  'part_header',
  'license',
])

export const SUMMARIZABLE_TYPES: ReadonlySet<string> = new Set([
  'chapter',
  'introduction',
  'preface',
  'foreword',
  'epilogue',
  'conclusion',
])

export const useReaderStore = defineStore('reader', () => {
  const book = ref<Book | null>(null)
  const sections = ref<Section[]>([])
  const currentSection = ref<Section | null>(null)
  const contentMode = ref<'original' | 'summary'>('original')
  const loading = ref(false)

  const hasSummary = computed(() => currentSection.value?.has_summary ?? false)
  const currentIndex = computed(() => {
    if (!currentSection.value) return -1
    return sections.value.findIndex((s) => s.id === currentSection.value!.id)
  })
  const hasNext = computed(() => currentIndex.value < sections.value.length - 1)
  const hasPrev = computed(() => currentIndex.value > 0)

  async function loadBook(
    bookId: number,
    opts?: { routeSectionId?: number; savedSectionId?: number },
  ) {
    loading.value = true
    try {
      book.value = await getBook(bookId)
      sections.value = await listSections(bookId)

      const target =
        (opts?.routeSectionId && sections.value.find((s) => s.id === opts.routeSectionId)) ||
        (opts?.savedSectionId && sections.value.find((s) => s.id === opts.savedSectionId)) ||
        sections.value.find((s) => SUMMARIZABLE_TYPES.has(s.section_type)) ||
        sections.value[0] ||
        null

      if (target) {
        await loadSection(bookId, target.id)
      }
    } finally {
      loading.value = false
    }
  }

  function updateSection(updated: Section) {
    const idx = sections.value.findIndex((s) => s.id === updated.id)
    if (idx === -1) {
      console.warn(`updateSection: id ${updated.id} not found in book ${book.value?.id ?? '?'}`)
      return
    }
    sections.value[idx] = updated
    if (currentSection.value?.id === updated.id) {
      currentSection.value = updated
    }
  }

  function setBook(b: Book) {
    book.value = b
  }

  async function loadSection(bookId: number, sectionId: number) {
    loading.value = true
    try {
      currentSection.value = await getSection(bookId, sectionId)
      if (currentSection.value.has_summary) {
        contentMode.value = 'summary'
      } else {
        contentMode.value = 'original'
      }
    } finally {
      loading.value = false
    }
  }

  async function navigateSection(direction: 'prev' | 'next') {
    if (!book.value) return
    const idx = currentIndex.value
    const newIdx = direction === 'next' ? idx + 1 : idx - 1
    if (newIdx >= 0 && newIdx < sections.value.length) {
      const newSection = sections.value[newIdx]
      // FR-D2 — push the route so back/forward + deep-link work correctly.
      try {
        const router = (await import('@/router')).default
        await router.push({
          name: 'book-section',
          params: { bookId: String(book.value.id), sectionId: String(newSection.id) },
        })
      } catch {
        // Fall back to direct load if router import fails (e.g., tests).
        loadSection(book.value.id, newSection.id)
      }
    }
  }

  function toggleContent() {
    contentMode.value = contentMode.value === 'original' ? 'summary' : 'original'
  }

  return {
    book,
    sections,
    currentSection,
    contentMode,
    loading,
    hasSummary,
    currentIndex,
    hasNext,
    hasPrev,
    loadBook,
    loadSection,
    navigateSection,
    toggleContent,
    updateSection,
    setBook,
  }
})
