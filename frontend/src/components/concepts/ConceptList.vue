<script setup lang="ts">
import { useConceptsStore } from '@/stores/concepts'
import { computed, onMounted, ref } from 'vue'

const props = defineProps<{
  bookId?: number
}>()

const store = useConceptsStore()
const searchFilter = ref('')
const sortBy = ref<'term' | 'updated_at'>('term')

onMounted(() => store.loadConcepts({ book_id: props.bookId, sort: sortBy.value }))

const filteredConcepts = computed(() => {
  if (!searchFilter.value) return store.concepts
  const q = searchFilter.value.toLowerCase()
  return store.concepts.filter((c) => c.term.toLowerCase().includes(q) || c.definition.toLowerCase().includes(q))
})

function changeSort(sort: 'term' | 'updated_at') {
  sortBy.value = sort
  store.loadConcepts({ book_id: props.bookId, sort })
}
</script>

<template>
  <div class="concept-list">
    <div class="list-header">
      <input v-model="searchFilter" placeholder="Filter concepts..." class="filter-input" />
      <div class="sort-controls">
        <button :class="{ active: sortBy === 'term' }" @click="changeSort('term')">A-Z</button>
        <button :class="{ active: sortBy === 'updated_at' }" @click="changeSort('updated_at')">Recent</button>
      </div>
    </div>
    <div v-if="store.loading" class="loading">Loading concepts...</div>
    <div v-else class="concepts">
      <button
        v-for="concept in filteredConcepts"
        :key="concept.id"
        class="concept-item"
        :class="{ selected: store.selectedConcept?.id === concept.id, edited: concept.user_edited }"
        @click="store.selectConcept(concept.id)"
      >
        <span class="concept-term">{{ concept.term }}</span>
        <span v-if="concept.user_edited" class="edited-badge">edited</span>
      </button>
    </div>
    <div class="list-footer">{{ store.total }} concepts</div>
  </div>
</template>

<style scoped>
.concept-list { display: flex; flex-direction: column; height: 100%; border-right: 1px solid var(--color-border, #e0e0e0); }
.list-header { padding: 0.75rem; border-bottom: 1px solid var(--color-border, #e0e0e0); display: flex; flex-direction: column; gap: 0.5rem; }
.filter-input { width: 100%; padding: 0.375rem 0.5rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; font-size: 0.85rem; }
.sort-controls { display: flex; gap: 0.25rem; }
.sort-controls button { padding: 0.25rem 0.5rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.25rem; background: none; cursor: pointer; font-size: 0.75rem; }
.sort-controls button.active { background: var(--color-primary, #3b82f6); color: #fff; border-color: var(--color-primary, #3b82f6); }
.loading { padding: 2rem; text-align: center; color: var(--color-text-secondary, #888); }
.concepts { flex: 1; overflow-y: auto; }
.concept-item { width: 100%; display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; border: none; border-bottom: 1px solid var(--color-border, #f0f0f0); background: transparent; cursor: pointer; text-align: left; }
.concept-item:hover { background: var(--color-bg-hover, #f9fafb); }
.concept-item.selected { background: var(--color-primary-light, #eff6ff); }
.concept-term { font-size: 0.85rem; font-weight: 500; }
.edited-badge { font-size: 0.65rem; color: var(--color-primary, #3b82f6); background: var(--color-primary-light, #eff6ff); padding: 0.125rem 0.25rem; border-radius: 0.25rem; }
.list-footer { padding: 0.5rem 0.75rem; border-top: 1px solid var(--color-border, #e0e0e0); font-size: 0.75rem; color: var(--color-text-secondary, #888); }
</style>
