<script setup lang="ts">
defineProps<{
  bookId: number
  prev: { id: number; title: string } | null
  next: { id: number; title: string } | null
  currentTab: 'summary' | 'original'
}>()
</script>

<template>
  <footer v-if="prev || next" class="reading-area__footer-nav">
    <router-link
      v-if="prev"
      :to="{ path: `/books/${bookId}/sections/${prev.id}`, query: { tab: currentTab } }"
      class="footer-nav__prev"
    >
      ← Previous: {{ prev.title }}
    </router-link>
    <span v-else />
    <router-link
      v-if="next"
      :to="{ path: `/books/${bookId}/sections/${next.id}`, query: { tab: currentTab } }"
      class="footer-nav__next"
    >
      Next: {{ next.title }} →
    </router-link>
    <span v-else />
  </footer>
</template>

<style scoped>
.reading-area__footer-nav {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  opacity: 0.85;
  font-size: 0.95em;
}
.reading-area__footer-nav a {
  color: inherit;
  text-decoration: none;
}
.reading-area__footer-nav a:hover {
  text-decoration: underline;
  opacity: 1;
}
</style>
