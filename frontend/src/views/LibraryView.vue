<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBooksStore } from '@/stores/books'
import { useDebounceFn } from '@/composables/useDebounceFn'
import EmptyState from '@/components/common/EmptyState.vue'
import FilterRow from '@/components/library/FilterRow.vue'
import BookGrid from '@/components/library/BookGrid.vue'
import BookList from '@/components/library/BookList.vue'
import BookTable from '@/components/library/BookTable.vue'
import ViewTabs from '@/components/library/ViewTabs.vue'
import BulkToolbar from '@/components/library/BulkToolbar.vue'
import ContinueBanner from '@/components/reader/ContinueBanner.vue'

const store = useBooksStore()
const route = useRoute()
const router = useRouter()

const searchInput = ref<string>(String(route.query.q ?? ''))
const activeTag = ref<string | undefined>(
  typeof route.query.tag === 'string' ? route.query.tag : undefined,
)

// FR-G3.1 — debounce search to 250ms, minimum 2 chars. AbortController
// upstream in the store cancels stale requests.
const debouncedSearch = useDebounceFn((q: string) => {
  const trimmed = q.trim()
  if (trimmed && trimmed.length < 2) return
  store.setSearch(trimmed || undefined)
  router.replace({ query: { ...route.query, q: trimmed || undefined } })
}, 250)

watch(searchInput, (v) => debouncedSearch(v))

// Read ?tag= from the URL on mount + whenever the route changes so a
// tag-chip click on BookCard activates the filter immediately.
watch(
  () => route.query.tag,
  (v) => {
    const tag = typeof v === 'string' && v.length ? v : undefined
    activeTag.value = tag
    store.setTag(tag)
  },
  { immediate: false },
)

function clearTag() {
  activeTag.value = undefined
  router.replace({ query: { ...route.query, tag: undefined } })
  store.setTag(undefined)
}

onMounted(() => {
  if (activeTag.value) store.setTag(activeTag.value)
  if (searchInput.value) store.setSearch(searchInput.value)
  if (!activeTag.value && !searchInput.value) store.fetchBooks()
  store.loadViews()
})
</script>

<template>
  <div class="library-page">
    <ContinueBanner />
    <ViewTabs />
    <div class="library-search-row">
      <input
        v-model="searchInput"
        class="library-search"
        type="search"
        placeholder="Search titles (2+ chars)…"
        aria-label="Search library by title"
      />
      <div v-if="activeTag" class="active-tag">
        <span>Tag: <strong>{{ activeTag }}</strong></span>
        <button type="button" class="clear-tag" @click="clearTag">
          Clear
        </button>
      </div>
    </div>
    <FilterRow />

    <template v-if="store.isEmpty && !store.hasActiveFilters">
      <EmptyState
        icon="📚"
        title="Welcome to Book Companion"
        description="Upload your first book to get started with AI-powered summarization and knowledge extraction."
        action-label="Upload a Book"
        action-to="/upload"
      />
    </template>

    <template v-else-if="store.isEmpty && store.hasActiveFilters">
      <EmptyState
        icon="🔍"
        title="No matches"
        description="No books match your current filters. Try adjusting your criteria."
      />
    </template>

    <template v-else>
      <BookGrid
        v-if="store.displayMode === 'grid'"
        :books="store.books"
        :loading="store.loading"
        :selected-ids="store.selectedIds"
        @toggle-select="store.toggleSelection"
      />
      <BookList
        v-else-if="store.displayMode === 'list'"
        :books="store.books"
        :loading="store.loading"
        :selected-ids="store.selectedIds"
        @toggle-select="store.toggleSelection"
      />
      <BookTable
        v-else
        :books="store.books"
        :loading="store.loading"
        :selected-ids="store.selectedIds"
        @toggle-select="store.toggleSelection"
        @select-all="store.selectAll"
      />
    </template>

    <BulkToolbar />

    <div v-if="store.pages > 1" class="pagination">
      <button
        class="page-btn"
        :disabled="store.page <= 1"
        @click="store.setPage(store.page - 1)"
      >
        Prev
      </button>
      <span class="page-info">Page {{ store.page }} of {{ store.pages }}</span>
      <button
        class="page-btn"
        :disabled="store.page >= store.pages"
        @click="store.setPage(store.page + 1)"
      >
        Next
      </button>
    </div>
  </div>
</template>

<style scoped>
.library-page {
  padding: 0 24px 24px;
}

.library-search-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  flex-wrap: wrap;
}

.library-search {
  flex: 1 1 260px;
  min-width: 200px;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}

.active-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(79, 70, 229, 0.08);
  border: 1px solid rgba(79, 70, 229, 0.25);
  border-radius: 999px;
  font-size: 12px;
}

.clear-tag {
  background: transparent;
  border: 0;
  color: #4f46e5;
  cursor: pointer;
  font-size: 12px;
  text-decoration: underline;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 24px 0;
}

.page-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: 13px;
  cursor: pointer;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.page-info {
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
