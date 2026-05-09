<template>
  <div data-test="session-end-actions" class="actions-bar">
    <div class="buttons">
      <button
        type="button"
        data-test="stop"
        class="btn-secondary"
        :disabled="stopping"
        @click="onStop"
      >
        Stop session
      </button>
      <button
        type="button"
        data-test="export"
        class="btn-primary"
        :disabled="exportDisabled"
        @click="exportOpen = true"
      >
        Export
      </button>
    </div>
    <p v-if="exportDisabled" data-test="export-disabled-msg" class="warn">
      {{ COPY.abandonedExportError }}
    </p>

    <ExportSessionModal
      v-if="exportOpen"
      :session="session"
      :book-slug="bookSlug"
      @close="exportOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import ExportSessionModal from './ExportSessionModal.vue'
import { stopSession } from '@/api/quizSessions'
import { COPY } from '@/components/quiz/copy'
import type { QuizSessionListItem } from '@/types'

const props = defineProps<{ session: QuizSessionListItem; bookSlug: string }>()
const emit = defineEmits<{
  (e: 'stopped', session: QuizSessionListItem): void
  (e: 'error', err: unknown): void
}>()

const stopping = ref(false)
const exportOpen = ref(false)

const exportDisabled = computed(() => props.session.status === 'abandoned')

async function onStop() {
  if (stopping.value) return
  stopping.value = true
  try {
    const updated = await stopSession(props.session.id)
    emit('stopped', updated)
  } catch (err) {
    emit('error', err)
  } finally {
    stopping.value = false
  }
}
</script>

<style scoped>
.actions-bar {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.75rem;
  background: white;
  border-top: 1px solid #e5e7eb;
}
.buttons {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
}
.btn-primary,
.btn-secondary {
  padding: 0.45rem 0.95rem;
  border-radius: 4px;
  font-size: 0.9rem;
  cursor: pointer;
}
.btn-primary {
  background: #4f46e5;
  color: white;
  border: none;
}
.btn-primary:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
}
.btn-secondary {
  background: white;
  color: #4b5563;
  border: 1px solid #d1d5db;
}
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.warn {
  margin: 0;
  font-size: 0.78rem;
  color: #b45309;
  align-self: flex-end;
}
</style>
