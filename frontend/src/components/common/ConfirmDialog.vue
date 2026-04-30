<script setup lang="ts">
/**
 * Reusable confirm dialog. Used by StructureEditor (edit-impact warning),
 * QueuePanel (cancel-running confirmation), and EditStructureView.
 */
import { onMounted, onUnmounted } from 'vue'

defineProps<{
  open: boolean
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  /** 'danger' tints the confirm button red (delete, cancel-running). */
  tone?: 'default' | 'danger'
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel')
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Transition name="fade">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      data-testid="confirm-dialog"
      @click.self="$emit('cancel')"
    >
      <div
        class="w-full max-w-md rounded-lg bg-white p-5 shadow-xl dark:bg-stone-800"
      >
        <h3 class="text-lg font-medium text-stone-900 dark:text-stone-100">{{ title }}</h3>
        <div v-if="message || $slots.default" class="mt-2 text-sm text-stone-600 dark:text-stone-300">
          <slot>{{ message }}</slot>
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <button
            type="button"
            class="rounded-md border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-50 dark:border-stone-600 dark:hover:bg-stone-700"
            data-testid="confirm-cancel"
            @click="$emit('cancel')"
          >
            {{ cancelLabel || 'Cancel' }}
          </button>
          <button
            type="button"
            :class="[
              'rounded-md px-3 py-1.5 text-sm font-medium text-white',
              tone === 'danger'
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-blue-600 hover:bg-blue-700',
            ]"
            data-testid="confirm-ok"
            @click="$emit('confirm')"
          >
            {{ confirmLabel || 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
