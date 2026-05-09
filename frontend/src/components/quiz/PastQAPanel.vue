<template>
  <section data-test="past-qa-panel" class="past-qa-panel">
    <h3 class="title">Past Q&amp;A</h3>
    <div v-if="sortedSessions.length === 0" data-test="past-qa-empty" class="empty">
      No prior sessions yet.
    </div>
    <div v-else class="groups">
      <PastSessionGroup
        v-for="(s, idx) in sortedSessions"
        :key="s.id"
        :session="s"
        :default-expanded="idx === 0"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PastSessionGroup from './PastSessionGroup.vue'
import type { QuizSessionListItem } from '@/types'

const props = defineProps<{ sessions: QuizSessionListItem[] }>()

// Most-recent first (D23) — sort by created_at descending.
const sortedSessions = computed(() =>
  [...props.sessions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  ),
)
</script>

<style scoped>
.past-qa-panel {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
}
.empty {
  font-size: 0.85rem;
  color: #6b7280;
  font-style: italic;
}
.groups {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>
