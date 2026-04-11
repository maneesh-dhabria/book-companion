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
}>()
</script>

<template>
  <div v-if="loading">
    <SkeletonLoader type="list-item" :count="6" />
  </div>
  <div v-else class="book-list">
    <router-link
      v-for="book in books"
      :key="book.id"
      :to="`/books/${book.id}`"
      class="book-list-item"
      :class="{ selected: selectedIds.includes(book.id) }"
    >
      <div class="book-list-cover">
        <img v-if="book.cover_url" :src="book.cover_url" :alt="book.title" />
        <div v-else class="cover-placeholder-sm">{{ book.file_format.toUpperCase() }}</div>
      </div>
      <div class="book-list-info">
        <h3 class="book-list-title">{{ book.title }}</h3>
        <p class="book-list-author">{{ book.authors.map(a => a.name).join(', ') || 'Unknown' }}</p>
      </div>
      <span class="book-list-badge" :class="book.status">{{ book.status }}</span>
      <span class="book-list-sections">{{ book.section_count }} sections</span>
      <span v-if="book.eval_passed !== null" class="book-list-eval">
        {{ book.eval_passed }}/{{ book.eval_total }}
      </span>
    </router-link>
  </div>
</template>

<style scoped>
.book-list {
  display: flex;
  flex-direction: column;
}

.book-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
  text-decoration: none;
  color: inherit;
  transition: background 0.1s;
}

.book-list-item:hover {
  background: var(--color-bg-secondary);
}

.book-list-item.selected {
  background: rgba(79, 70, 229, 0.05);
}

.book-list-cover {
  width: 36px;
  height: 50px;
  border-radius: 4px;
  overflow: hidden;
  background: var(--color-bg-tertiary);
  flex-shrink: 0;
}

.book-list-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder-sm {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-muted);
}

.book-list-info {
  flex: 1;
  min-width: 0;
}

.book-list-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-list-author {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 2px 0 0;
}

.book-list-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--color-bg-tertiary);
}

.book-list-badge.completed { color: var(--color-success); }
.book-list-badge.parsed { color: var(--color-text-accent); }

.book-list-sections,
.book-list-eval {
  font-size: 12px;
  color: var(--color-text-muted);
  white-space: nowrap;
}
</style>
