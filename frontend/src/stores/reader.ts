import { getBook } from '@/api/books'
import { getSection, listSections } from '@/api/sections'
import type { Book, Section } from '@/types'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

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

  async function loadBook(bookId: number) {
    loading.value = true
    try {
      book.value = await getBook(bookId)
      sections.value = await listSections(bookId)
    } finally {
      loading.value = false
    }
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

  function navigateSection(direction: 'prev' | 'next') {
    if (!book.value) return
    const idx = currentIndex.value
    const newIdx = direction === 'next' ? idx + 1 : idx - 1
    if (newIdx >= 0 && newIdx < sections.value.length) {
      const newSection = sections.value[newIdx]
      loadSection(book.value.id, newSection.id)
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
  }
})
