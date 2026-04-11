<script setup lang="ts">
import AnnotationCard from '@/components/sidebar/AnnotationCard.vue'
import { exportAnnotationsUrl } from '@/api/annotations'
import { useAnnotationsStore } from '@/stores/annotations'
import { onMounted, ref } from 'vue'

const store = useAnnotationsStore()
const filterType = ref<string | undefined>(undefined)
const exportFormat = ref<'markdown' | 'json' | 'csv'>('markdown')

onMounted(() => store.loadAnnotations())

function applyTypeFilter(type: string | undefined) {
  filterType.value = type
  store.loadAnnotations({ type })
}
</script>

<template>
  <div class="annotations-page">
    <div class="page-header">
      <h1>Annotations</h1>
      <div class="header-actions">
        <div class="filter-group">
          <button :class="{ active: !filterType }" @click="applyTypeFilter(undefined)">All</button>
          <button :class="{ active: filterType === 'highlight' }" @click="applyTypeFilter('highlight')">Highlights</button>
          <button :class="{ active: filterType === 'note' }" @click="applyTypeFilter('note')">Notes</button>
        </div>
        <a :href="exportAnnotationsUrl(exportFormat)" class="export-btn" download>
          Export {{ exportFormat.toUpperCase() }}
        </a>
      </div>
    </div>

    <div v-if="store.loading" class="loading">Loading...</div>
    <div v-else-if="store.annotations.length === 0" class="empty">
      <p>No annotations yet. Highlight text while reading to create annotations.</p>
    </div>
    <div v-else class="annotation-grid">
      <AnnotationCard
        v-for="annotation in store.annotations"
        :key="annotation.id"
        :annotation="annotation"
        @delete="store.removeAnnotation(annotation.id)"
      />
    </div>

    <div class="page-footer">
      {{ store.total }} annotations
    </div>
  </div>
</template>

<style scoped>
.annotations-page { padding: 1.5rem; max-width: 800px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
h1 { font-size: 1.5rem; font-weight: 600; }
.header-actions { display: flex; gap: 0.75rem; align-items: center; }
.filter-group { display: flex; gap: 0.25rem; }
.filter-group button { padding: 0.375rem 0.75rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; background: none; cursor: pointer; font-size: 0.8rem; }
.filter-group button.active { background: var(--color-primary, #3b82f6); color: #fff; border-color: var(--color-primary, #3b82f6); }
.export-btn { padding: 0.375rem 0.75rem; border: 1px solid var(--color-border, #ddd); border-radius: 0.375rem; font-size: 0.8rem; color: inherit; text-decoration: none; }
.loading { text-align: center; padding: 3rem; color: var(--color-text-secondary, #888); }
.empty { text-align: center; padding: 3rem; color: var(--color-text-secondary, #888); }
.annotation-grid { display: flex; flex-direction: column; gap: 0.75rem; }
.page-footer { margin-top: 1.5rem; text-align: center; font-size: 0.8rem; color: var(--color-text-secondary, #888); }
</style>
