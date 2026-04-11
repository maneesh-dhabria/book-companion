<script setup lang="ts">
import type { Annotation } from '@/types'
import { ref } from 'vue'

const props = defineProps<{
  annotation: Annotation
}>()

const emit = defineEmits<{
  delete: []
}>()

const editing = ref(false)
const editNote = ref(props.annotation.note || '')

function startEdit() {
  editNote.value = props.annotation.note || ''
  editing.value = true
}
</script>

<template>
  <div class="annotation-card" :class="`type-${annotation.type}`">
    <div v-if="annotation.selected_text" class="selected-text">
      "{{ annotation.selected_text }}"
    </div>
    <div v-if="annotation.note && !editing" class="note" @dblclick="startEdit">
      {{ annotation.note }}
    </div>
    <div class="meta">
      <span class="type-badge">{{ annotation.type }}</span>
      <span class="date">{{ new Date(annotation.created_at).toLocaleDateString() }}</span>
      <button class="delete-btn" @click="$emit('delete')">Delete</button>
    </div>
  </div>
</template>

<style scoped>
.annotation-card { padding: 0.625rem; border: 1px solid var(--color-border, #e0e0e0); border-radius: 0.5rem; background: var(--color-bg, #fff); }
.annotation-card.type-highlight { border-left: 3px solid #fbbf24; }
.annotation-card.type-note { border-left: 3px solid #3b82f6; }
.annotation-card.type-freeform { border-left: 3px solid #8b5cf6; }
.selected-text { font-style: italic; color: var(--color-text-secondary, #555); font-size: 0.8rem; margin-bottom: 0.375rem; }
.note { font-size: 0.85rem; margin-bottom: 0.375rem; }
.meta { display: flex; align-items: center; gap: 0.5rem; font-size: 0.7rem; color: var(--color-text-secondary, #888); }
.type-badge { text-transform: capitalize; background: var(--color-bg-secondary, #f3f4f6); padding: 0.125rem 0.375rem; border-radius: 0.25rem; }
.delete-btn { margin-left: auto; background: none; border: none; color: var(--color-danger, #ef4444); cursor: pointer; font-size: 0.7rem; }
</style>
