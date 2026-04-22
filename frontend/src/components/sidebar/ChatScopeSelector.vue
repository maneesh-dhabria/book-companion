<script setup lang="ts">
import { computed } from 'vue'

export type ChatScope = 'section' | 'book'

const props = defineProps<{
  modelValue: ChatScope
  currentSectionTitle: string | null
  bookTitle: string
}>()

defineEmits<{
  'update:modelValue': [scope: ChatScope]
}>()

const sectionDisabled = computed(() => props.currentSectionTitle == null)
</script>

<template>
  <div class="scope-selector" role="group" aria-label="Chat scope">
    <button
      type="button"
      data-testid="section-scope"
      class="scope-btn"
      :class="{ active: modelValue === 'section' }"
      :disabled="sectionDisabled"
      :title="sectionDisabled ? 'Open a section to chat about it' : `Chat about ${currentSectionTitle}`"
      @click="$emit('update:modelValue', 'section')"
    >
      Section
      <span v-if="currentSectionTitle" class="context">: {{ currentSectionTitle }}</span>
    </button>
    <button
      type="button"
      data-testid="book-scope"
      class="scope-btn"
      :class="{ active: modelValue === 'book' }"
      :title="`Chat about ${bookTitle}`"
      @click="$emit('update:modelValue', 'book')"
    >
      Book
    </button>
  </div>
</template>

<style scoped>
.scope-selector {
  display: inline-flex;
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 999px;
  overflow: hidden;
  font-size: 0.8rem;
}
.scope-btn {
  padding: 0.35rem 0.85rem;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  font: inherit;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.scope-btn + .scope-btn { border-left: 1px solid var(--color-border, #e5e7eb); }
.scope-btn.active {
  background: var(--color-primary, #3b82f6);
  color: #fff;
}
.scope-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.context {
  font-weight: 400;
  opacity: 0.85;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
