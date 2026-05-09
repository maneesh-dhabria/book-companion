<template>
  <div data-test="self-assessment" class="sa">
    <div class="row">
      <button
        type="button"
        data-test="sa-got_it"
        class="btn got"
        :disabled="disabled"
        @click="onClick('got_it')"
      >
        Got it
      </button>
      <button
        type="button"
        data-test="sa-partial"
        class="btn partial"
        :disabled="disabled"
        @click="onClick('partial')"
      >
        Partial
      </button>
      <button
        type="button"
        data-test="sa-missed"
        class="btn missed"
        :disabled="disabled"
        @click="onClick('missed')"
      >
        Missed
      </button>
    </div>
    <p v-if="isFirstSession" data-test="sa-microcopy" class="microcopy">
      {{ microcopy }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { useQuizSessionsStore } from '@/stores/quizSessions'
import { COPY } from '@/components/quiz/copy'
import type { QuizSelfAssessment } from '@/types'

const props = defineProps<{
  bookId: number
  disabled: boolean
  isFirstSession: boolean
}>()

const microcopy = COPY.selfAssessmentMicrocopy
const store = useQuizSessionsStore()

async function onClick(sa: QuizSelfAssessment) {
  if (props.disabled) return
  await store.recordSelfAssessment(props.bookId, sa)
}
</script>

<style scoped>
.sa {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.row {
  display: flex;
  gap: 0.6rem;
}
.btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid;
  font-weight: 500;
  cursor: pointer;
  font-size: 0.9rem;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.got {
  background: #4f46e5;
  color: white;
  border-color: #4f46e5;
}
.btn.partial {
  background: white;
  color: #b45309;
  border-color: #d97706;
}
.btn.missed {
  background: white;
  color: #6b7280;
  border-color: #9ca3af;
}
.microcopy {
  margin: 0;
  font-size: 0.78rem;
  color: #6b7280;
  font-style: italic;
}
</style>
