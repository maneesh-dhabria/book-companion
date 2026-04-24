<template>
  <section class="note-composition-panel" :aria-hidden="!visible">
    <header>
      <h3>{{ title }}</h3>
      <button
        type="button"
        class="close"
        aria-label="Close note editor"
        @click="$emit('close')"
      >
        &times;
      </button>
    </header>
    <div v-if="context" class="context-quote">
      <blockquote>{{ context }}</blockquote>
    </div>
    <textarea
      ref="textareaEl"
      v-model="draft"
      rows="8"
      placeholder="Add your note in markdown…"
      aria-label="Note body"
      @keydown.ctrl.enter="save"
      @keydown.meta.enter="save"
    />
    <footer>
      <span class="char-count">{{ draft.length }}/10000</span>
      <div class="actions">
        <button type="button" class="cancel" @click="$emit('close')">
          Cancel
        </button>
        <button
          type="button"
          class="save"
          :disabled="draft.length === 0 || draft.length > 10000"
          @click="save"
        >
          Save note
        </button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    visible: boolean
    context?: string
    title?: string
    initialText?: string
  }>(),
  { title: 'Add note', initialText: '' },
)

const emit = defineEmits<{
  (e: 'save', note: string): void
  (e: 'close'): void
}>()

const draft = ref(props.initialText)
const textareaEl = ref<HTMLTextAreaElement | null>(null)

watch(
  () => props.visible,
  async (v) => {
    if (v) {
      draft.value = props.initialText
      await nextTick()
      textareaEl.value?.focus()
    }
  },
)

function save() {
  if (!draft.value.trim() || draft.value.length > 10000) return
  emit('save', draft.value)
}
</script>

<style scoped>
.note-composition-panel {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.75rem;
  background: white;
  border-left: 1px solid #e5e7eb;
  height: 100%;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
h3 {
  margin: 0;
  font-size: 0.95rem;
}
.close {
  background: transparent;
  border: 0;
  font-size: 1.25rem;
  cursor: pointer;
}
.context-quote blockquote {
  background: #f8fafc;
  border-left: 3px solid #94a3b8;
  padding: 0.25rem 0.6rem;
  margin: 0;
  font-size: 0.8125rem;
  color: #475569;
  max-height: 4rem;
  overflow-y: auto;
}
textarea {
  flex: 1;
  resize: vertical;
  padding: 0.5rem;
  font: inherit;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
}
footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: #64748b;
}
.actions {
  display: flex;
  gap: 0.35rem;
}
button.save {
  background: #4f46e5;
  color: white;
  border: 0;
  padding: 0.35rem 0.9rem;
  border-radius: 0.25rem;
  cursor: pointer;
}
button.save:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
button.cancel {
  background: transparent;
  border: 1px solid #d1d5db;
  padding: 0.3rem 0.8rem;
  border-radius: 0.25rem;
  cursor: pointer;
}
</style>
