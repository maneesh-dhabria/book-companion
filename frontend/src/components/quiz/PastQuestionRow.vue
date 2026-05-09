<template>
  <li data-test="past-question-row" class="row" :class="{ stale: question.is_stale, discarded: question.discarded }">
    <div class="header">
      <span class="shape">{{ question.shape }}</span>
      <span v-if="question.is_stale" data-test="stale-badge" class="badge stale-badge">
        stale (re-imported)
      </span>
      <span v-if="question.discarded" data-test="discarded-badge" class="badge discarded-badge">
        discarded
      </span>
      <span v-if="question.warm_up" class="badge warm-up-badge">warm-up</span>
      <span v-if="question.self_assessment" class="badge sa-badge" :class="`sa-${question.self_assessment}`">
        {{ saLabel }}
      </span>
    </div>
    <p class="stem">{{ question.stem }}</p>
    <p v-if="question.user_answer" class="answer">
      <span class="label">Your answer:</span>
      {{ question.user_answer }}
    </p>
    <p v-else-if="question.skip_count > 0" class="answer skipped">
      <span class="label">(skipped)</span>
    </p>
    <p v-if="question.override_note" class="override">
      <span class="label">Override:</span>
      {{ question.override_note }}
    </p>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QuizQuestion } from '@/types'

const props = defineProps<{ question: QuizQuestion }>()

const saLabel = computed(() => {
  switch (props.question.self_assessment) {
    case 'got_it':
      return 'Got it'
    case 'partial':
      return 'Partial'
    case 'missed':
      return 'Missed'
    default:
      return ''
  }
})
</script>

<style scoped>
.row {
  list-style: none;
  padding: 0.6rem 0.7rem;
  border-radius: 4px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.row.stale {
  opacity: 0.6;
}
.row.discarded {
  opacity: 0.7;
  text-decoration: line-through;
}
.header {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}
.shape {
  font-size: 0.7rem;
  text-transform: uppercase;
  font-weight: 600;
  color: #6b7280;
  letter-spacing: 0.04em;
}
.badge {
  font-size: 0.68rem;
  font-weight: 500;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  text-transform: uppercase;
}
.stale-badge {
  background: #fee2e2;
  color: #991b1b;
}
.discarded-badge {
  background: #f3f4f6;
  color: #4b5563;
}
.warm-up-badge {
  background: #dbeafe;
  color: #1e40af;
}
.sa-badge.sa-got_it {
  background: #d1fae5;
  color: #065f46;
}
.sa-badge.sa-partial {
  background: #fef3c7;
  color: #92400e;
}
.sa-badge.sa-missed {
  background: #fee2e2;
  color: #991b1b;
}
.stem {
  margin: 0;
  font-weight: 500;
  font-size: 0.9rem;
  color: #111827;
}
.answer,
.override {
  margin: 0;
  font-size: 0.82rem;
  color: #4b5563;
}
.label {
  font-weight: 600;
  margin-right: 0.3rem;
}
.skipped {
  font-style: italic;
}
</style>
