<script setup lang="ts">
import { useBooksStore } from '@/stores/books'
import { deleteBook } from '@/api/books'

const store = useBooksStore()

async function bulkDelete() {
  if (!confirm(`Delete ${store.selectedIds.length} book(s)? This cannot be undone.`)) return
  for (const id of store.selectedIds) {
    await deleteBook(id)
  }
  store.clearSelection()
  store.fetchBooks()
}
</script>

<template>
  <div v-if="store.selectedIds.length > 0" class="bulk-toolbar">
    <span class="bulk-count">{{ store.selectedIds.length }} selected</span>
    <button class="bulk-btn" @click="bulkDelete">Delete</button>
    <button class="bulk-btn clear" @click="store.clearSelection()">Clear</button>
  </div>
</template>

<style scoped>
.bulk-toolbar {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 20px;
  background: var(--color-sidebar-bg);
  color: var(--color-sidebar-text);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  z-index: 100;
  font-size: 13px;
}

.bulk-count {
  font-weight: 500;
}

.bulk-btn {
  padding: 4px 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
}

.bulk-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.bulk-btn.clear {
  border: none;
  opacity: 0.7;
}
</style>
