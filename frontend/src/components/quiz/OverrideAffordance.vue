<template>
  <div data-test="override" class="override">
    <button
      v-if="!expanded"
      type="button"
      data-test="override-toggle"
      class="toggle"
      @click="expanded = true"
    >
      Add an override note
    </button>

    <div v-else class="form">
      <label class="label">Override note (does not change tally)</label>
      <textarea
        data-test="override-textarea"
        class="ta"
        :value="note"
        rows="3"
        placeholder="Explain why your self-assessment differs from the agent…"
        @input="onInput"
      />
      <div class="footer">
        <span data-test="override-counter" class="counter">{{ note.length }} / {{ MAX }}</span>
        <div class="actions">
          <button
            type="button"
            class="btn-secondary"
            @click="expanded = false"
          >
            Cancel
          </button>
          <button
            type="button"
            data-test="override-save"
            class="btn-primary"
            :disabled="note.length === 0 || saving"
            @click="onSave"
          >
            Save override
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { overrideQuestion } from '@/api/quizSessions'

const props = defineProps<{ sessionId: number; questionId: number }>()
const emit = defineEmits<{ (e: 'saved', note: string): void }>()

const MAX = 500
const expanded = ref(false)
const note = ref('')
const saving = ref(false)

function onInput(e: Event) {
  const v = (e.target as HTMLTextAreaElement).value
  note.value = v.length > MAX ? v.slice(0, MAX) : v
  // Reflect the clamped value back into the DOM in case the browser kept the longer value.
  ;(e.target as HTMLTextAreaElement).value = note.value
}

async function onSave() {
  if (saving.value || note.value.length === 0) return
  saving.value = true
  try {
    await overrideQuestion(props.sessionId, props.questionId, note.value)
    emit('saved', note.value)
    expanded.value = false
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.override {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.toggle {
  background: none;
  border: none;
  color: #4f46e5;
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0;
  align-self: flex-start;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}
.label {
  font-size: 0.78rem;
  font-weight: 500;
  color: #4b5563;
}
.ta {
  width: 100%;
  padding: 0.5rem;
  border-radius: 4px;
  border: 1px solid #d1d5db;
  font-family: inherit;
  font-size: 0.9rem;
  resize: vertical;
}
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.counter {
  font-size: 0.75rem;
  color: #6b7280;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
.btn-primary,
.btn-secondary {
  padding: 0.35rem 0.85rem;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
}
.btn-primary {
  background: #4f46e5;
  color: white;
  border: none;
}
.btn-primary:disabled {
  background: #c7d2fe;
}
.btn-secondary {
  background: white;
  color: #4b5563;
  border: 1px solid #d1d5db;
}
</style>
