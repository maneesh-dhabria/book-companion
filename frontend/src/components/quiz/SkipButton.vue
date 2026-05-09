<template>
  <button
    type="button"
    data-test="skip"
    class="skip-btn"
    :disabled="busy"
    @click="onClick"
  >
    Skip
  </button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { skipQuestion } from '@/api/quizSessions'

const props = defineProps<{ sessionId: number; questionId: number }>()
const emit = defineEmits<{ (e: 'skipped'): void; (e: 'error', err: unknown): void }>()

const busy = ref(false)

async function onClick() {
  if (busy.value) return
  busy.value = true
  try {
    await skipQuestion(props.sessionId, props.questionId)
    emit('skipped')
  } catch (err) {
    emit('error', err)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.skip-btn {
  padding: 0.4rem 0.85rem;
  background: white;
  color: #6b7280;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
}
.skip-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.skip-btn:hover:not(:disabled) {
  background: #f9fafb;
}
</style>
