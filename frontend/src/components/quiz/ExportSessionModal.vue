<template>
  <div data-test="export-modal" class="modal-backdrop" @click.self="onCancel">
    <div class="modal" role="dialog" aria-labelledby="export-title">
      <h3 id="export-title" class="title">Export this session</h3>
      <p class="body">
        Download a Markdown file with every question, your answer, and the agent's feedback.
      </p>
      <div class="row">
        <span class="label">Filename:</span>
        <code class="filename">{{ filename }}</code>
      </div>
      <div class="actions">
        <button
          type="button"
          data-test="cancel-export"
          class="btn-secondary"
          @click="onCancel"
        >
          Cancel
        </button>
        <button
          type="button"
          data-test="confirm-export"
          class="btn-primary"
          @click="onConfirm"
        >
          Download .md
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QuizSessionListItem } from '@/types'

const props = defineProps<{ session: QuizSessionListItem; bookSlug: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const filename = computed(() => `${props.bookSlug}_quiz_session_${props.session.id}.md`)
const url = computed(
  () => `/api/v1/quiz-sessions/${props.session.id}/export?fmt=markdown`,
)

function onCancel() {
  emit('close')
}

function onConfirm() {
  // T34 implements server-side; here we just trigger a Markdown download.
  const a = document.createElement('a')
  a.href = url.value
  a.download = filename.value
  a.target = '_blank'
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  emit('close')
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: white;
  padding: 1.25rem;
  border-radius: 8px;
  max-width: 28rem;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #111827;
}
.body {
  margin: 0;
  font-size: 0.9rem;
  color: #4b5563;
}
.row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.label {
  font-size: 0.78rem;
  color: #6b7280;
}
.filename {
  font-size: 0.85rem;
  background: #f9fafb;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  border: 1px solid #e5e7eb;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
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
.btn-secondary {
  background: white;
  color: #4b5563;
  border: 1px solid #d1d5db;
}
</style>
