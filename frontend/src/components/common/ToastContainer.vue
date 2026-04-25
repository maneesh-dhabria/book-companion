<script setup lang="ts">
import { storeToRefs } from 'pinia'

import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const { toasts } = storeToRefs(ui)
</script>

<template>
  <div
    class="toast-stack"
    role="region"
    aria-label="Notifications"
    aria-live="polite"
    aria-atomic="false"
  >
    <TransitionGroup name="toast" tag="div" class="toast-stack-inner">
      <div
        v-for="t in toasts"
        :key="t.id"
        :class="['toast', `toast--${t.type}`]"
        data-testid="toast"
        role="status"
      >
        <span class="toast-message">{{ t.message }}</span>
        <button
          type="button"
          class="toast-close"
          aria-label="Dismiss notification"
          data-testid="toast-close"
          @click="ui.dismissToast(t.id)"
        >
          ✕
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 50;
  pointer-events: none;
}
.toast-stack-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  min-width: 240px;
  max-width: 380px;
  padding: 10px 14px 10px 12px;
  border-radius: 8px;
  background: #ffffff;
  border-left: 4px solid #6b7280;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.9rem;
  color: #111827;
}
.toast--success {
  border-left-color: #16a34a;
}
.toast--error {
  border-left-color: #dc2626;
}
.toast--warning {
  border-left-color: #d97706;
}
.toast--info {
  border-left-color: #2563eb;
}
.toast-message {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-word;
}
.toast-close {
  flex: 0 0 auto;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 0.85rem;
  line-height: 1;
  padding: 2px 4px;
}
.toast-close:hover {
  color: #111827;
}

.toast-enter-active,
.toast-leave-active {
  transition:
    transform 180ms ease,
    opacity 180ms ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(8px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(8px);
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: opacity 80ms ease;
  }
  .toast-enter-from,
  .toast-leave-to {
    transform: none;
  }
}
</style>
