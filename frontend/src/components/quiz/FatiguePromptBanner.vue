<template>
  <div v-if="show" data-test="fatigue-banner" class="fatigue-banner">
    <p class="text">{{ COPY.fatigueClause }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { COPY } from '@/components/quiz/copy'
import type { QuizFeedback } from '@/types'

const props = defineProps<{ feedback: QuizFeedback | null }>()

const show = computed(() => {
  if (!props.feedback) return false
  return props.feedback.actual.includes(COPY.fatigueClause)
})
</script>

<style scoped>
.fatigue-banner {
  padding: 0.6rem 0.85rem;
  background: #fffbeb;
  border-left: 3px solid #d97706;
  border-radius: 4px;
}
.text {
  margin: 0;
  font-size: 0.9rem;
  color: #92400e;
}
</style>
