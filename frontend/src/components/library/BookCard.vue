<script setup lang="ts">
import CoverFallback from '@/components/common/CoverFallback.vue'
import TagChip from '@/components/common/TagChip.vue'
import type { BookListItem } from '@/types'

defineProps<{
  book: BookListItem
  selected: boolean
}>()

defineEmits<{
  toggleSelect: [id: number]
}>()

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <router-link :to="`/books/${book.id}`" class="book-card" :class="{ selected }">
    <div class="book-card-cover">
      <img v-if="book.cover_url" :src="book.cover_url" :alt="book.title" class="cover-img" />
      <CoverFallback v-else :title="book.title" :width="180" :height="240" />
    </div>
    <div class="book-card-info">
      <h3 class="book-card-title">{{ book.title }}</h3>
      <p class="book-card-author">
        {{ book.authors.map(a => a.name).join(', ') || 'Unknown Author' }}
      </p>
      <div class="book-card-meta">
        <span class="book-card-badge" :class="book.status">{{ book.status }}</span>
        <span class="book-card-sections">{{ book.section_count }} sections</span>
        <span v-if="book.eval_passed !== null" class="book-card-eval">
          {{ book.eval_passed }}/{{ book.eval_total }}
        </span>
      </div>
      <div v-if="book.tags && book.tags.length" class="book-card-tags">
        <TagChip
          v-for="t in book.tags"
          :key="t.id"
          :label="t.name"
          :color="t.color"
          clickable
          @click.prevent="$router.push({ path: '/', query: { tag: t.name } })"
        />
      </div>
    </div>
    <div class="book-card-select" @click.prevent="$emit('toggleSelect', book.id)">
      <input type="checkbox" :checked="selected" tabindex="-1" />
    </div>
  </router-link>
</template>

<style scoped>
.book-card {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--color-bg-primary);
  text-decoration: none;
  color: inherit;
  transition: box-shadow 0.15s, border-color 0.15s;
  position: relative;
}

.book-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--color-border-strong);
}

.book-card.selected {
  border-color: var(--color-accent);
}

.book-card-cover {
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background: var(--color-bg-tertiary);
}

.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cover-format {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text-muted);
  opacity: 0.5;
}

.book-card-info {
  padding: 12px;
}

.book-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.book-card-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 4px;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-card-author {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.book-card-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
  background: var(--color-bg-tertiary);
}

.book-card-badge.completed { color: var(--color-success); }
.book-card-badge.parsed { color: var(--color-text-accent); }
.book-card-badge.summarizing { color: var(--color-warning); }

.book-card-select {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.15s;
}

.book-card:hover .book-card-select,
.book-card.selected .book-card-select {
  opacity: 1;
}
</style>
