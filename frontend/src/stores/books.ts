import { listBooks, type ListBooksParams } from '@/api/books'
import { listViews, createView, updateView, deleteView } from '@/api/views'
import type { BookListItem, LibraryView } from '@/types'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useBooksStore = defineStore('books', () => {
  const books = ref<BookListItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(20)
  const pages = ref(0)
  const loading = ref(false)

  const filters = ref<{ status?: string; format?: string }>({})
  const sort = ref<{ field: string; order: string }>({ field: 'updated_at', order: 'desc' })
  const displayMode = ref<'grid' | 'list' | 'table'>('grid')
  const selectedIds = ref<number[]>([])

  // Views
  const views = ref<LibraryView[]>([])
  const currentViewId = ref<number | null>(null)

  const isEmpty = computed(() => books.value.length === 0 && !loading.value)
  const hasActiveFilters = computed(() => Object.values(filters.value).some((v) => v !== undefined))
  const activeView = computed(() => views.value.find((v) => v.id === currentViewId.value) || null)

  async function fetchBooks() {
    loading.value = true
    try {
      const params: ListBooksParams = {
        page: page.value,
        per_page: perPage.value,
        sort_field: sort.value.field,
        sort_direction: sort.value.order,
        ...filters.value,
      }
      const result = await listBooks(params)
      books.value = result.items
      total.value = result.total
      pages.value = result.pages
    } finally {
      loading.value = false
    }
  }

  function updateFilters(newFilters: typeof filters.value) {
    filters.value = { ...newFilters }
    page.value = 1
    fetchBooks()
  }

  function setSort(field: string, order: string) {
    sort.value = { field, order }
    page.value = 1
    fetchBooks()
  }

  function setDisplayMode(mode: 'grid' | 'list' | 'table') {
    displayMode.value = mode
  }

  function setPage(p: number) {
    page.value = p
    fetchBooks()
  }

  function toggleSelection(id: number) {
    const idx = selectedIds.value.indexOf(id)
    if (idx >= 0) {
      selectedIds.value.splice(idx, 1)
    } else {
      selectedIds.value.push(id)
    }
  }

  function selectAll() {
    selectedIds.value = books.value.map((b) => b.id)
  }

  function clearSelection() {
    selectedIds.value = []
  }

  // View management
  async function loadViews() {
    views.value = await listViews()
    if (!currentViewId.value && views.value.length > 0) {
      currentViewId.value = views.value[0].id
    }
  }

  async function createViewFromCurrent(name: string) {
    const view = await createView({
      name,
      display_mode: displayMode.value,
      sort_field: sort.value.field,
      sort_direction: sort.value.order,
      filters: filters.value,
    })
    views.value.push(view)
    currentViewId.value = view.id
  }

  async function deleteViewById(id: number) {
    await deleteView(id)
    views.value = views.value.filter((v) => v.id !== id)
    if (currentViewId.value === id) {
      currentViewId.value = views.value[0]?.id || null
    }
  }

  function switchView(viewId: number) {
    const view = views.value.find((v) => v.id === viewId)
    if (!view) return
    currentViewId.value = viewId
    displayMode.value = view.display_mode as 'grid' | 'list' | 'table'
    sort.value = { field: view.sort_field, order: view.sort_direction }
    filters.value = (view.filters as typeof filters.value) || {}
    fetchBooks()
  }

  return {
    books,
    total,
    page,
    perPage,
    pages,
    loading,
    filters,
    sort,
    displayMode,
    selectedIds,
    views,
    currentViewId,
    isEmpty,
    hasActiveFilters,
    activeView,
    fetchBooks,
    updateFilters,
    setSort,
    setDisplayMode,
    setPage,
    toggleSelection,
    selectAll,
    clearSelection,
    loadViews,
    createViewFromCurrent,
    deleteViewById,
    switchView,
  }
})
