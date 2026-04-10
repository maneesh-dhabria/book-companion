<script setup lang="ts">
import { useBooksStore } from '@/stores/books'

const store = useBooksStore()

const sortOptions = [
  { label: 'Recent', field: 'updated_at', order: 'desc' },
  { label: 'Title A-Z', field: 'title', order: 'asc' },
  { label: 'Date Added', field: 'created_at', order: 'desc' },
]

const statusOptions = ['', 'parsed', 'summarizing', 'completed']
const formatOptions = ['', 'epub', 'pdf', 'mobi']

function onStatusChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  store.updateFilters({ ...store.filters, status: val || undefined })
}

function onFormatChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  store.updateFilters({ ...store.filters, format: val || undefined })
}

function onSortChange(e: Event) {
  const idx = parseInt((e.target as HTMLSelectElement).value)
  const opt = sortOptions[idx]
  store.setSort(opt.field, opt.order)
}

function onDisplayMode(mode: 'grid' | 'list' | 'table') {
  store.setDisplayMode(mode)
}
</script>

<template>
  <div class="filter-row">
    <div class="filter-controls">
      <select class="filter-select" @change="onStatusChange">
        <option value="">All Statuses</option>
        <option v-for="s in statusOptions.slice(1)" :key="s" :value="s">{{ s }}</option>
      </select>
      <select class="filter-select" @change="onFormatChange">
        <option value="">All Formats</option>
        <option v-for="f in formatOptions.slice(1)" :key="f" :value="f">{{ f.toUpperCase() }}</option>
      </select>
      <select class="filter-select" @change="onSortChange">
        <option v-for="(opt, idx) in sortOptions" :key="idx" :value="idx">
          {{ opt.label }}
        </option>
      </select>
    </div>
    <div class="display-modes">
      <button
        class="mode-btn"
        :class="{ active: store.displayMode === 'grid' }"
        @click="onDisplayMode('grid')"
        title="Grid view"
      >
        ▦
      </button>
      <button
        class="mode-btn"
        :class="{ active: store.displayMode === 'list' }"
        @click="onDisplayMode('list')"
        title="List view"
      >
        ☰
      </button>
      <button
        class="mode-btn"
        :class="{ active: store.displayMode === 'table' }"
        @click="onDisplayMode('table')"
        title="Table view"
      >
        ▤
      </button>
    </div>
  </div>
</template>

<style scoped>
.filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-controls {
  display: flex;
  gap: 8px;
}

.filter-select {
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}

.display-modes {
  display: flex;
  gap: 2px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
}

.mode-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--color-bg-primary);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 16px;
  transition: all 0.1s;
}

.mode-btn:hover {
  background: var(--color-bg-secondary);
}

.mode-btn.active {
  background: var(--color-accent);
  color: #fff;
}
</style>
