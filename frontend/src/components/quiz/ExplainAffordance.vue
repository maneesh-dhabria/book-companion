<template>
  <div data-test="explain-affordance" class="explain">
    <ul v-if="question.explain_history.length > 0" class="history">
      <li
        v-for="(line, idx) in question.explain_history"
        :key="idx"
        data-test="explain-history-item"
        class="entry"
      >
        <span class="prefix">Clarification:</span>
        <span class="text">{{ line }}</span>
      </li>
    </ul>

    <p v-if="atSoftCap" data-test="explain-soft-cap" class="soft-cap">
      {{ COPY.explainSoftCap }}
    </p>
    <button
      v-else
      type="button"
      data-test="explain"
      class="explain-btn"
      :disabled="busy"
      @click="onClick"
    >
      Explain
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { explainQuestion } from '@/api/quizSessions'
import { COPY } from '@/components/quiz/copy'
import { QUIZ_EXPLAIN_SOFT_CAP } from '@/components/quiz/constants'
import type { QuizQuestion, QuizExplainResponse } from '@/types'

const props = defineProps<{ sessionId: number; question: QuizQuestion }>()
const emit = defineEmits<{
  (e: 'explained', resp: QuizExplainResponse): void
  (e: 'error', err: unknown): void
}>()

const busy = ref(false)

const atSoftCap = computed(
  () => props.question.explain_history.length >= QUIZ_EXPLAIN_SOFT_CAP,
)

async function onClick() {
  if (busy.value || atSoftCap.value) return
  busy.value = true
  try {
    const resp = await explainQuestion(props.sessionId, props.question.id)
    emit('explained', resp)
  } catch (err) {
    emit('error', err)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.explain {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.history {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.entry {
  font-size: 0.85rem;
  color: #6b7280;
  background: #f9fafb;
  padding: 0.5rem 0.7rem;
  border-radius: 4px;
  border-left: 2px solid #c7d2fe;
}
.prefix {
  font-weight: 600;
  margin-right: 0.4rem;
  color: #4338ca;
}
.text {
  color: #374151;
}
.soft-cap {
  margin: 0;
  padding: 0.45rem 0.7rem;
  font-size: 0.85rem;
  color: #6b7280;
  font-style: italic;
}
.explain-btn {
  align-self: flex-start;
  padding: 0.4rem 0.85rem;
  background: white;
  color: #4f46e5;
  border: 1px solid #4f46e5;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
}
.explain-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.explain-btn:hover:not(:disabled) {
  background: #eef2ff;
}
</style>
