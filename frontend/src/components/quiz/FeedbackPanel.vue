<template>
  <div v-if="feedback" data-test="feedback-panel" class="feedback-panel">
    <div data-test="feedback-field" class="field correct">
      <span class="label">What you got right</span>
      <p class="text">{{ feedback.correct }}</p>
    </div>
    <div data-test="feedback-field" class="field missing">
      <span class="label">What was missing</span>
      <p class="text">{{ feedback.missing }}</p>
    </div>
    <div data-test="feedback-field" class="field actual">
      <span class="label">What the book actually says</span>
      <p class="text">{{ feedback.actual }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { QuizFeedback } from '@/types'

defineProps<{ feedback: QuizFeedback | null }>()
</script>

<style scoped>
.feedback-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b7280;
}
.field.correct .label {
  color: #047857;
}
.field.missing .label {
  color: #b45309;
}
.field.actual .label {
  color: #4338ca;
}
.text {
  margin: 0;
  font-size: 0.95rem;
  color: #111827;
}
</style>
