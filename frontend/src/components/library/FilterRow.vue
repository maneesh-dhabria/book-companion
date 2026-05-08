<script setup lang="ts">
import { LayoutGrid, List, Rows3, CheckSquare } from 'lucide-vue-next'

import { useBooksStore } from '@/stores/books'
import { useUiStore } from '@/stores/ui'

const store = useBooksStore()
const ui = useUiStore()

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

function onToggleSelect() {
  ui.toggleBulkSelect()
  if (!ui.bulkSelectMode) store.clearSelection?.()
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
        aria-label="Grid view"
        title="Grid view"
        @click="onDisplayMode('grid')"
      >
        <LayoutGrid :size="16" />
        <span class="mode-btn__label">Grid</span>
      </button>
      <button
        class="mode-btn"
        :class="{ active: store.displayMode === 'list' }"
        aria-label="List view"
        title="List view"
        @click="onDisplayMode('list')"
      >
        <List :size="16" />
        <span class="mode-btn__label">List</span>
      </button>
      <button
        class="mode-btn"
        :class="{ active: store.displayMode === 'table' }"
        aria-label="Table view"
        title="Table view"
        @click="onDisplayMode('table')"
      >
        <Rows3 :size="16" />
        <span class="mode-btn__label">Table</span>
      </button>
      <button
        class="mode-btn"
        :class="{ active: ui.bulkSelectMode }"
        data-testid="bulk-select-toggle"
        :aria-pressed="ui.bulkSelectMode"
        :aria-label="ui.bulkSelectMode ? 'Exit select mode' : 'Enter select mode'"
        :title="ui.bulkSelectMode ? 'Exit select mode' : 'Select books'"
        @click="onToggleSelect"
      >
        <CheckSquare :size="16" />
        <span class="mode-btn__label">Select</span>
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
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  border: none;
  background: var(--color-bg-primary);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.1s;
}

.mode-btn__label {
  display: none;
}

@media (min-width: 768px) {
  .mode-btn__label {
    display: inline;
  }
}

.mode-btn:hover {
  background: var(--color-bg-secondary);
}

.mode-btn.active {
  background: var(--color-accent);
  color: #fff;
}
</style>
