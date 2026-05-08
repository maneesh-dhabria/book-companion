<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const visible = ref(false)

function isTypingTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false
  if (t.isContentEditable) return true
  const tag = t.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && visible.value) {
    e.preventDefault()
    visible.value = false
    return
  }
  if (e.key !== '?') return
  if (isTypingTarget(e.target)) return
  if (e.ctrlKey || e.metaKey || e.altKey) return
  e.preventDefault()
  visible.value = !visible.value
}

function close() {
  visible.value = false
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

defineExpose({ visible })
</script>

<template>
  <div
    v-if="visible"
    data-testid="keyboard-shortcuts-overlay"
    role="dialog"
    aria-modal="true"
    aria-label="Keyboard shortcuts"
    class="kbd-overlay"
    @click.self="close"
  >
    <div class="kbd-overlay__panel" role="document">
      <header class="kbd-overlay__header">
        <h2>Keyboard shortcuts</h2>
        <button
          type="button"
          aria-label="Close"
          class="kbd-overlay__close"
          @click="close"
        >
          ✕
        </button>
      </header>
      <dl class="kbd-overlay__list">
        <div class="kbd-overlay__row">
          <dt><kbd>Space</kbd></dt><dd>Play / pause audio</dd>
        </div>
        <div class="kbd-overlay__row">
          <dt><kbd>→</kbd></dt><dd>Next sentence</dd>
        </div>
        <div class="kbd-overlay__row">
          <dt><kbd>←</kbd></dt><dd>Previous sentence</dd>
        </div>
        <div class="kbd-overlay__row">
          <dt><kbd>?</kbd></dt><dd>Toggle this overlay</dd>
        </div>
        <div class="kbd-overlay__row">
          <dt><kbd>Esc</kbd></dt><dd>Close this overlay</dd>
        </div>
      </dl>
    </div>
  </div>
</template>

<style scoped>
.kbd-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.kbd-overlay__panel {
  background: rgb(255 255 255);
  color: rgb(15 23 42);
  border-radius: 0.5rem;
  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.2);
  padding: 1.25rem 1.5rem;
  min-width: 20rem;
  max-width: 26rem;
}
.dark .kbd-overlay__panel {
  background: rgb(30 41 59);
  color: rgb(241 245 249);
}
.kbd-overlay__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}
.kbd-overlay__header h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}
.kbd-overlay__close {
  appearance: none;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 1rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
}
.kbd-overlay__list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}
.kbd-overlay__row {
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
  font-size: 0.875rem;
}
.kbd-overlay__row dt {
  flex: 0 0 4rem;
}
.kbd-overlay__row kbd {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.75rem;
  background: rgb(241 245 249);
  border: 1px solid rgb(203 213 225);
  border-radius: 0.25rem;
  padding: 0.0625rem 0.375rem;
  color: rgb(15 23 42);
}
.dark .kbd-overlay__row kbd {
  background: rgb(51 65 85);
  border-color: rgb(71 85 105);
  color: rgb(241 245 249);
}
</style>
