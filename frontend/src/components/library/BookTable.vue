<script setup lang="ts">
import type { BookListItem } from '@/types'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'

defineProps<{
  books: BookListItem[]
  loading: boolean
  selectedIds: number[]
}>()

defineEmits<{
  toggleSelect: [id: number]
  selectAll: []
}>()

const columns = [
  { key: 'title', label: 'Title', sticky: true },
  { key: 'author', label: 'Author' },
  { key: 'status', label: 'Status' },
  { key: 'format', label: 'Format' },
  { key: 'sections', label: 'Sections' },
  { key: 'eval', label: 'Eval' },
  { key: 'updated', label: 'Updated' },
]

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString()
}
</script>

<template>
  <div v-if="loading">
    <SkeletonLoader type="table-row" :count="6" />
  </div>
  <div v-else class="table-wrapper">
    <table class="book-table">
      <thead>
        <tr>
          <th class="col-checkbox">
            <input
              type="checkbox"
              :checked="selectedIds.length === books.length && books.length > 0"
              @change="$emit('selectAll')"
            />
          </th>
          <th
            v-for="col in columns"
            :key="col.key"
            class="col-header"
            :class="{ sticky: col.sticky }"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="book in books"
          :key="book.id"
          class="table-row"
          :class="{ selected: selectedIds.includes(book.id) }"
        >
          <td class="col-checkbox" @click.stop>
            <input
              type="checkbox"
              :checked="selectedIds.includes(book.id)"
              @change="$emit('toggleSelect', book.id)"
            />
          </td>
          <td class="col-title sticky">
            <router-link :to="`/books/${book.id}`" class="title-link">
              {{ book.title }}
            </router-link>
          </td>
          <td>{{ book.authors.map(a => a.name).join(', ') || '-' }}</td>
          <td>
            <span class="status-badge" :class="book.status">{{ book.status }}</span>
          </td>
          <td>{{ book.file_format.toUpperCase() }}</td>
          <td>{{ book.section_count }}</td>
          <td>
            <span v-if="book.eval_passed !== null">{{ book.eval_passed }}/{{ book.eval_total }}</span>
            <span v-else class="text-muted">-</span>
          </td>
          <td>{{ formatDate(book.updated_at) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.book-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.book-table th,
.book-table td {
  padding: 8px 12px;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid var(--color-border);
}

.book-table thead {
  background: var(--color-bg-secondary);
}

.col-checkbox {
  width: 36px;
  text-align: center;
}

.col-header {
  font-weight: 600;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sticky {
  position: sticky;
  left: 36px;
  background: inherit;
  z-index: 1;
}

thead .sticky {
  background: var(--color-bg-secondary);
}

.table-row:hover {
  background: var(--color-bg-secondary);
}

.table-row.selected {
  background: rgba(79, 70, 229, 0.05);
}

.title-link {
  color: var(--color-text-primary);
  font-weight: 500;
  text-decoration: none;
}

.title-link:hover {
  color: var(--color-accent);
}

.status-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: var(--color-bg-tertiary);
}

.status-badge.completed { color: var(--color-success); }
.status-badge.parsed { color: var(--color-text-accent); }
.status-badge.summarizing { color: var(--color-warning); }

.text-muted { color: var(--color-text-muted); }
</style>
