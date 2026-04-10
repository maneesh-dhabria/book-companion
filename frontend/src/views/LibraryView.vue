<script setup lang="ts">
import { onMounted } from 'vue'
import { useBooksStore } from '@/stores/books'
import EmptyState from '@/components/common/EmptyState.vue'
import FilterRow from '@/components/library/FilterRow.vue'
import BookGrid from '@/components/library/BookGrid.vue'
import BookList from '@/components/library/BookList.vue'

const store = useBooksStore()

onMounted(() => {
  store.fetchBooks()
  store.loadViews()
})
</script>

<template>
  <div class="library-page">
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
      <div v-else>
        <p style="text-align: center; padding: 32px; color: var(--color-text-muted)">
          Table view coming in T13b
        </p>
      </div>
    </template>

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
