<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const pageTitle = computed(() => {
  const name = route.name as string
  const titles: Record<string, string> = {
    library: 'Library',
    'book-detail': 'Reader',
    'section-detail': 'Reader',
    'eval-detail': 'Evaluation',
    'book-summary': 'Book Summary',
    search: 'Search',
    annotations: 'Annotations',
    concepts: 'Concepts',
    settings: 'Settings',
    upload: 'Upload',
  }
  return titles[name] || 'Book Companion'
})
</script>

<template>
  <header class="top-bar">
    <h1 class="top-bar-title">{{ pageTitle }}</h1>
    <div class="top-bar-actions">
      <input
        type="text"
        placeholder="Search..."
        class="top-bar-search"
        readonly
      />
      <router-link to="/upload" class="top-bar-upload">
        Upload
      </router-link>
    </div>
  </header>
</template>

<style scoped>
.top-bar {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-primary);
}

.top-bar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.top-bar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.top-bar-search {
  width: 240px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.top-bar-upload {
  height: 32px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  background: var(--color-accent);
  color: #fff;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: background 0.15s;
}

.top-bar-upload:hover {
  background: var(--color-accent-hover);
}
</style>
