<script setup lang="ts">
import type { Section } from '@/types'
import ContentToggle from './ContentToggle.vue'
import TOCDropdown from './TOCDropdown.vue'

defineProps<{
  bookTitle: string
  bookId: number
  sections: Section[]
  currentSectionId: number | null
  contentMode: 'original' | 'summary'
  hasSummary: boolean
  hasPrev: boolean
  hasNext: boolean
}>()

defineEmits<{
  toggleContent: []
  navigate: [direction: 'prev' | 'next']
}>()
</script>

<template>
  <div class="reader-header">
    <div class="reader-breadcrumb">
      <router-link to="/" class="breadcrumb-link">Library</router-link>
      <span class="breadcrumb-sep">/</span>
      <router-link :to="`/books/${bookId}`" class="breadcrumb-link">{{ bookTitle }}</router-link>
      <span class="breadcrumb-sep">/</span>
      <TOCDropdown
        :sections="sections"
        :current-section-id="currentSectionId"
        :book-id="bookId"
      />
    </div>
    <div class="reader-controls">
      <button
        class="nav-btn"
        :disabled="!hasPrev"
        @click="$emit('navigate', 'prev')"
        title="Previous section"
      >
        ←
      </button>
      <ContentToggle
        :mode="contentMode"
        :has-summary="hasSummary"
        @toggle="$emit('toggleContent')"
      />
      <button
        class="nav-btn"
        :disabled="!hasNext"
        @click="$emit('navigate', 'next')"
        title="Next section"
      >
        →
      </button>
    </div>
  </div>
</template>

<style scoped>
.reader-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  border-bottom: 1px solid var(--color-border);
  gap: 16px;
  flex-wrap: wrap;
}

.reader-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  min-width: 0;
}

.breadcrumb-link {
  color: var(--color-text-secondary);
  text-decoration: none;
  white-space: nowrap;
}

.breadcrumb-link:hover {
  color: var(--color-text-primary);
}

.breadcrumb-sep {
  color: var(--color-text-muted);
}

.reader-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.1s;
}

.nav-btn:hover:not(:disabled) {
  background: var(--color-bg-secondary);
}

.nav-btn:disabled {
  opacity: 0.3;
  cursor: default;
}
</style>
