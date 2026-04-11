<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  visible: boolean
  rect: { top: number; left: number; width: number; height: number } | null
  selectedText: string
}>()

const emit = defineEmits<{
  highlight: []
  note: []
  askAi: []
  copy: []
}>()

const style = computed(() => {
  if (!props.rect) return { display: 'none' }
  return {
    position: 'fixed' as const,
    top: `${props.rect.top - 48}px`,
    left: `${props.rect.left + props.rect.width / 2}px`,
    transform: 'translateX(-50%)',
    zIndex: 1000,
  }
})

function copyText() {
  navigator.clipboard.writeText(props.selectedText)
  emit('copy')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible && rect" class="floating-toolbar" :style="style">
      <button class="toolbar-btn" @click="$emit('highlight')" title="Highlight">
        <span class="icon">🖍</span>
        <span class="label">Highlight</span>
      </button>
      <button class="toolbar-btn" @click="$emit('note')" title="Add Note">
        <span class="icon">📝</span>
        <span class="label">Note</span>
      </button>
      <button class="toolbar-btn" @click="$emit('askAi')" title="Ask AI">
        <span class="icon">💬</span>
        <span class="label">Ask AI</span>
      </button>
      <button class="toolbar-btn" @click="copyText" title="Copy">
        <span class="icon">📋</span>
        <span class="label">Copy</span>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.floating-toolbar { display: flex; gap: 0.25rem; padding: 0.375rem; background: var(--color-bg-elevated, #fff); border: 1px solid var(--color-border, #ddd); border-radius: 0.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.toolbar-btn { display: flex; flex-direction: column; align-items: center; gap: 0.125rem; padding: 0.375rem 0.5rem; border: none; background: transparent; cursor: pointer; border-radius: 0.375rem; transition: background 0.1s; }
.toolbar-btn:hover { background: var(--color-bg-hover, #f3f4f6); }
.icon { font-size: 1rem; }
.label { font-size: 0.625rem; color: var(--color-text-secondary, #666); }
</style>
