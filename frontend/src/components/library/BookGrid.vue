<script setup lang="ts">
import type { BookListItem } from '@/types'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import BookCard from './BookCard.vue'

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
  <div v-if="loading" class="book-grid">
    <SkeletonLoader type="card" :count="8" />
  </div>
  <div v-else class="book-grid">
    <BookCard
      v-for="book in books"
      :key="book.id"
      :book="book"
      :selected="selectedIds.includes(book.id)"
      @toggle-select="$emit('toggleSelect', $event)"
    />
  </div>
</template>

<style scoped>
.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  padding: 16px 0;
}
</style>
