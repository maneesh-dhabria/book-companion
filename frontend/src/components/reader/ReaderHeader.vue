<script setup lang="ts">
import { computed } from 'vue'
import type { Section } from '@/types'
import ContentToggle from './ContentToggle.vue'
import SectionTagRow from './SectionTagRow.vue'
import TOCDropdown from './TOCDropdown.vue'

const props = defineProps<{
  bookTitle: string
  bookId: number
  sections: Section[]
  currentSectionId: number | null
  contentMode: 'original' | 'summary'
  hasSummary: boolean
  hasPrev: boolean
  hasNext: boolean
}>()

const orderedSections = computed(() =>
  [...props.sections].sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0)),
)

const currentIndex = computed(() => {
  if (props.currentSectionId == null) return -1
  return orderedSections.value.findIndex((s) => s.id === props.currentSectionId)
})

const currentSectionTitle = computed(() => {
  const i = currentIndex.value
  return i >= 0 ? (orderedSections.value[i]?.title ?? '') : ''
})

const prevSectionTitle = computed(() => {
  const i = currentIndex.value
  if (i <= 0) return ''
  return orderedSections.value[i - 1]?.title ?? ''
})

const nextSectionTitle = computed(() => {
  const i = currentIndex.value
  if (i < 0 || i >= orderedSections.value.length - 1) return ''
  return orderedSections.value[i + 1]?.title ?? ''
})

const prevAriaLabel = computed(() =>
  prevSectionTitle.value ? `Previous section: ${prevSectionTitle.value}` : 'Previous section',
)
const nextAriaLabel = computed(() =>
  nextSectionTitle.value ? `Next section: ${nextSectionTitle.value}` : 'Next section',
)

defineEmits<{
  toggleContent: []
  navigate: [direction: 'prev' | 'next']
}>()
</script>

<template>
  <div class="reader-header">
    <h1 v-if="currentSectionTitle" class="reader-h1">{{ currentSectionTitle }}</h1>
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
      <SectionTagRow :section-id="currentSectionId" />
    </div>
    <div class="reader-controls">
      <div class="cluster" data-cluster="nav" role="group" aria-label="Section navigation">
        <button
          class="nav-btn"
          data-action="prev"
          :disabled="!hasPrev"
          :aria-label="prevAriaLabel"
          :title="prevAriaLabel"
          @click="$emit('navigate', 'prev')"
        >
          ←
        </button>
        <button
          class="nav-btn"
          data-action="next"
          :disabled="!hasNext"
          :aria-label="nextAriaLabel"
          :title="nextAriaLabel"
          @click="$emit('navigate', 'next')"
        >
          →
        </button>
      </div>
      <div class="cluster cluster--divided" data-cluster="mode" role="group" aria-label="Reading mode">
        <ContentToggle
          :mode="contentMode"
          :has-summary="hasSummary"
          @toggle="$emit('toggleContent')"
        />
      </div>
      <div class="cluster cluster--divided" data-cluster="actions" role="group" aria-label="Actions">
        <slot name="actions" />
      </div>
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

.reader-h1 {
  font-size: 1.4rem;
  margin: 0 0 0.25rem 0;
  flex-basis: 100%;
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

.cluster {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cluster--divided {
  border-left: 1px solid var(--color-border);
  padding-left: 8px;
  margin-left: 4px;
}

.nav-btn {
  min-width: 40px;
  min-height: 40px;
  width: 40px;
  height: 40px;
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
