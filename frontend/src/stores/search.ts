import { clearRecentSearches, fullSearch, getRecentSearches, quickSearch } from '@/api/search'
import type { QuickSearchResults, RecentSearch, SearchResultItem } from '@/types'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSearchStore = defineStore('search', () => {
  const query = ref('')
  const quickResults = ref<QuickSearchResults | null>(null)
  const fullResults = ref<SearchResultItem[]>([])
  const fullTotal = ref(0)
  const fullPage = ref(1)
  const fullPerPage = ref(20)
  const recentSearches = ref<RecentSearch[]>([])
  const loading = ref(false)
  const quickLoading = ref(false)

  let abortController: AbortController | null = null

  async function doQuickSearch(q: string, bookId?: number) {
    query.value = q
    if (!q.trim()) {
      quickResults.value = null
      return
    }

    // Cancel previous request
    if (abortController) abortController.abort()
    abortController = new AbortController()

    quickLoading.value = true
    try {
      const resp = await quickSearch(q, 12, bookId)
      quickResults.value = resp.results
    } catch {
      // Aborted or network error — ignore
    } finally {
      quickLoading.value = false
    }
  }

  async function doFullSearch(params: {
    q: string
    source_type?: string
    book_id?: number
    page?: number
  }) {
    loading.value = true
    query.value = params.q
    fullPage.value = params.page ?? 1
    try {
      const resp = await fullSearch({
        q: params.q,
        source_type: params.source_type,
        book_id: params.book_id,
        page: fullPage.value,
        per_page: fullPerPage.value,
      })
      fullResults.value = resp.items
      fullTotal.value = resp.total
    } finally {
      loading.value = false
    }
  }

  async function loadRecentSearches() {
    recentSearches.value = await getRecentSearches()
  }

  async function clearRecent() {
    await clearRecentSearches()
    recentSearches.value = []
  }

  return {
    query,
    quickResults,
    fullResults,
    fullTotal,
    fullPage,
    fullPerPage,
    recentSearches,
    loading,
    quickLoading,
    doQuickSearch,
    doFullSearch,
    loadRecentSearches,
    clearRecent,
  }
})
