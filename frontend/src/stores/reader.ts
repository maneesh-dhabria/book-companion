import { getBook } from '@/api/books'
import { getSection, listSections } from '@/api/sections'
import type { Book, Section } from '@/types'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Router } from 'vue-router'

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

// Test-only seam — overrides the dynamic `@/router` import resolution
// so unit tests can wire in a memory-history router. Production code
// path is unaffected because this stays null.
let _routerOverride: Router | null = null
export function _setRouterForTests(r: Router | null) {
  _routerOverride = r
}
async function getRouter(): Promise<Router | null> {
  if (_routerOverride) return _routerOverride
  try {
    const mod = (await import('@/router')) as { default?: Router }
    return mod.default ?? null
  } catch {
    return null
  }
}

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

  // Dedupe in-flight loadSection calls so the BookDetailView route watcher
  // and direct calls (navigateSection, programmatic) don't double-fetch the
  // same section. Returns the in-flight promise when the (bookId, sectionId)
  // matches an already-running call.
  let _inFlight: { key: string; promise: Promise<void> } | null = null

  async function loadSection(bookId: number, sectionId: number) {
    const key = `${bookId}:${sectionId}`
    if (_inFlight && _inFlight.key === key) {
      return _inFlight.promise
    }
    const promise = _loadSectionImpl(bookId, sectionId)
    _inFlight = { key, promise }
    try {
      await promise
    } finally {
      if (_inFlight && _inFlight.key === key) _inFlight = null
    }
  }

  async function _loadSectionImpl(bookId: number, sectionId: number) {
    loading.value = true
    try {
      currentSection.value = await getSection(bookId, sectionId)
      // FR-14 / FR-15 / FR-16 / FR-17 — sync content tab to ?tab= URL query.
      const routerInstance = await getRouter()
      const requestedTab = routerInstance?.currentRoute.value.query.tab
      const hasSummary = currentSection.value.has_summary
      if (requestedTab === 'summary' && hasSummary) {
        contentMode.value = 'summary'
      } else if (requestedTab === 'original') {
        contentMode.value = 'original'
      } else if (hasSummary) {
        contentMode.value = 'summary'
      } else {
        contentMode.value = 'original'
      }
      // FR-17: when URL says summary but section has none, rewrite to original.
      if (
        routerInstance &&
        requestedTab === 'summary' &&
        !hasSummary
      ) {
        await routerInstance.replace({
          query: { ...routerInstance.currentRoute.value.query, tab: 'original' },
        })
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
      // FR-16: carry the current tab forward; loadSection on the destination
      // route handles the FR-17 no-summary rewrite.
      const router = await getRouter()
      if (router) {
        await router.push({
          name: 'section-detail',
          params: { id: String(book.value.id), sectionId: String(newSection.id) },
          query: { tab: contentMode.value },
        })
      }
      // BookDetailView's route watcher normally re-runs loadSection on
      // route change; calling it here too is idempotent and ensures the
      // FR-17 rewrite + tab resolution fire even when the watcher isn't
      // mounted (unit tests, programmatic navigation outside the view).
      await loadSection(book.value.id, newSection.id)
    }
  }

  async function toggleContent() {
    contentMode.value = contentMode.value === 'original' ? 'summary' : 'original'
    const routerInstance = await getRouter()
    if (routerInstance) {
      await routerInstance.replace({
        query: { ...routerInstance.currentRoute.value.query, tab: contentMode.value },
      })
    }
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
