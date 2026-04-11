<script setup lang="ts">
import { useSearchStore } from '@/stores/search'
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const store = useSearchStore()

onMounted(() => {
  const q = route.query.q as string
  if (q) store.doFullSearch({ q })
})

function navigateToResult(item: { source_type: string; source_id: number; book_id: number }) {
  if (item.source_type === 'section') {
    router.push(`/books/${item.book_id}/sections/${item.source_id}`)
  } else if (item.source_type === 'concept') {
    router.push(`/concepts?id=${item.source_id}`)
  } else {
    router.push(`/books/${item.book_id}`)
  }
}
</script>

<template>
  <div class="search-results-page">
    <h1>Search Results</h1>
    <p v-if="store.query" class="query-info">
      Results for "{{ store.query }}" ({{ store.fullTotal }} found)
    </p>

    <div v-if="store.loading" class="loading">Searching...</div>
    <div v-else-if="store.fullResults.length === 0" class="empty">
      No results found.
    </div>
    <div v-else class="results-list">
      <button
        v-for="(item, index) in store.fullResults"
        :key="index"
        class="result-card"
        @click="navigateToResult(item)"
      >
        <div class="result-header">
          <span class="source-badge">{{ item.source_type }}</span>
          <span class="book-title">{{ item.book_title }}</span>
        </div>
        <div v-if="item.section_title" class="section-title">{{ item.section_title }}</div>
        <div class="snippet" v-html="item.highlight || item.snippet" />
        <div class="score">Score: {{ item.score.toFixed(3) }}</div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.search-results-page { padding: 1.5rem; max-width: 800px; margin: 0 auto; }
h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 0.25rem; }
.query-info { color: var(--color-text-secondary, #888); margin-bottom: 1.5rem; }
.loading, .empty { text-align: center; padding: 3rem; color: var(--color-text-secondary, #888); }
.results-list { display: flex; flex-direction: column; gap: 0.75rem; }
.result-card { display: flex; flex-direction: column; gap: 0.375rem; padding: 0.875rem; border: 1px solid var(--color-border, #e0e0e0); border-radius: 0.5rem; background: var(--color-bg, #fff); cursor: pointer; text-align: left; width: 100%; }
.result-card:hover { border-color: var(--color-primary, #3b82f6); }
.result-header { display: flex; gap: 0.5rem; align-items: center; }
.source-badge { font-size: 0.7rem; text-transform: uppercase; padding: 0.125rem 0.375rem; background: var(--color-bg-secondary, #f3f4f6); border-radius: 0.25rem; }
.book-title { font-size: 0.8rem; color: var(--color-text-secondary, #666); }
.section-title { font-size: 0.9rem; font-weight: 500; }
.snippet { font-size: 0.85rem; color: var(--color-text-secondary, #555); line-height: 1.4; }
.snippet :deep(mark) { background: #fef08a; padding: 0 0.125rem; border-radius: 0.125rem; }
.score { font-size: 0.7rem; color: var(--color-text-secondary, #aaa); }
</style>
