<template>
  <div data-test="active-session" class="active-session">
    <WarmUpBanner
      v-if="warmUpActive"
      :missed-concepts="missedConcepts"
      :partial-concepts="partialConcepts"
    />

    <!-- T29: <QuestionTurn :question="currentQuestion" /> -->
    <div v-if="currentQuestion" data-test="question-turn-placeholder" class="placeholder">
      <p class="stem">{{ currentQuestion.stem }}</p>
      <p class="hint">QuestionTurn UI lands in T29.</p>
    </div>
    <div v-else class="placeholder">
      <p>Loading question…</p>
    </div>

    <!-- T33: <SessionEndActions /> -->
    <div data-test="session-end-actions-placeholder" class="actions-placeholder">
      <button type="button" class="btn-secondary" data-test="stop-session" @click="onStop">
        Stop session
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import WarmUpBanner from './WarmUpBanner.vue'
import { useQuizSessionsStore } from '@/stores/quizSessions'

const props = defineProps<{ bookId: number }>()

const store = useQuizSessionsStore()

const bookState = computed(() => store.byBook.get(props.bookId) ?? null)
const currentQuestion = computed(() => bookState.value?.currentQuestion ?? null)
const activeSession = computed(() => bookState.value?.activeSession ?? null)

// FR-72: warm-up enumerates Missed/Partial concept_labels from prior sessions.
// The full data wiring lands in Phase 5 (T32). Until then we surface no
// warm-up cues by default; ActiveSession will gate on `warmUpActive` once
// the store exposes prior-session aggregates.
const warmUpActive = computed(() => activeSession.value?.is_warm_up_session ?? false)
const missedConcepts = computed<string[]>(() => [])
const partialConcepts = computed<string[]>(() => [])

async function onStop() {
  if (!activeSession.value) return
  // Phase 5 (T33) wires the proper end-of-session pivot; this minimal
  // handler reloads so the UI returns to the scope picker.
  await store.loadForBook(props.bookId)
}
</script>

<style scoped>
.active-session {
  padding: 1rem;
}
.placeholder {
  padding: 1rem;
  border: 1px dashed var(--color-border, #ccc);
  border-radius: 6px;
  margin-bottom: 1rem;
}
.placeholder .stem {
  font-weight: 600;
  margin-bottom: 0.5rem;
}
.placeholder .hint {
  font-size: 0.85rem;
  color: var(--color-text-muted, #666);
}
.actions-placeholder {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}
.btn-secondary {
  padding: 0.4rem 0.9rem;
  background: white;
  color: #4f46e5;
  border: 1px solid #4f46e5;
  border-radius: 4px;
  cursor: pointer;
}
</style>
