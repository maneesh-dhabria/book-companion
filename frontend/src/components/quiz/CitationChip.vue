<template>
  <a
    data-test="citation-chip"
    class="citation-chip"
    :href="`/books/${citation.section_id ? bookId : bookId}/sections/${citation.section_id}`"
    target="_blank"
    rel="noopener"
    :title="citation.snippet"
  >
    <span class="label">{{ citation.section_title }}</span>
  </a>
</template>

<script setup lang="ts">
import type { QuizCitation } from '@/types'

defineProps<{ bookId: number; citation: QuizCitation }>()
</script>

<style scoped>
.citation-chip {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 0.8rem;
  text-decoration: none;
  border: 1px solid #c7d2fe;
}
.citation-chip:hover {
  background: #e0e7ff;
}
</style>
