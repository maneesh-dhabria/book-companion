<script setup lang="ts">
import type { Section } from '@/types'
import { computed, ref } from 'vue'
import SectionListTable from '@/components/book/SectionListTable.vue'

const props = defineProps<{
  sections: Section[]
  currentSectionId: number | null
  bookId: number
}>()

const isOpen = ref(false)
const searchQuery = ref('')

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) searchQuery.value = ''
}

// FR-33 / NFR-07 — TOC dropdown reuses the shared SectionListTable in
// compact mode so book-detail and reader-TOC stay structurally aligned.
const filteredSections = computed(() => {
  if (!searchQuery.value) return props.sections
  const q = searchQuery.value.toLowerCase()
  return props.sections.filter((s) => s.title.toLowerCase().includes(q))
})
</script>

<template>
  <div class="toc-dropdown" v-click-outside="() => (isOpen = false)">
    <button class="toc-trigger" @click="toggle">
      {{ sections.find((s) => s.id === currentSectionId)?.title || 'Select Section' }}
      <span class="toc-arrow">{{ isOpen ? '▲' : '▼' }}</span>
    </button>
    <div v-if="isOpen" class="toc-panel">
      <input v-model="searchQuery" placeholder="Search sections..." class="toc-search" />
      <div class="toc-list" @click="isOpen = false">
        <SectionListTable
          :sections="filteredSections"
          :book-id="bookId"
          :current-section-id="currentSectionId"
          :compact="true"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.toc-dropdown {
  position: relative;
}

.toc-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: 13px;
  cursor: pointer;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toc-arrow {
  font-size: 10px;
  color: var(--color-text-muted);
}

.toc-panel {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  width: 360px;
  max-height: 400px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 100;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.toc-search {
  padding: 8px 12px;
  border: none;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  outline: none;
  background: transparent;
  color: var(--color-text-primary);
}

.toc-list {
  overflow-y: auto;
  max-height: 340px;
}

.toc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  text-decoration: none;
  color: var(--color-text-primary);
  font-size: 13px;
  transition: background 0.1s;
}

.toc-item:hover {
  background: var(--color-bg-secondary);
}

.toc-item.active {
  background: rgba(79, 70, 229, 0.08);
  color: var(--color-accent);
}

.toc-index {
  color: var(--color-text-muted);
  font-size: 11px;
  min-width: 20px;
}

.toc-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toc-summarized {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--color-bg-tertiary);
  color: var(--color-text-accent);
  font-weight: 600;
}

.toc-frontmatter > summary {
  padding: 8px 12px;
  cursor: pointer;
  color: var(--color-text-muted);
  font-size: 12px;
  user-select: none;
}
</style>
