import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
  duration: number
}

const MAX_VISIBLE_TOASTS = 5

let toastId = 0

export const useUiStore = defineStore('ui', () => {
  const commandPaletteOpen = ref(false)
  const uploadWizardOpen = ref(false)
  const toasts = ref<Toast[]>([])
  // Per-toast dismiss timers, keyed by id, so manual close cancels its timer
  // and the FIFO cap can also cancel the dropped oldest toast's timer.
  const timers = new Map<number, ReturnType<typeof setTimeout>>()

  function dismissToast(id: number) {
    const t = timers.get(id)
    if (t !== undefined) {
      clearTimeout(t)
      timers.delete(id)
    }
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }

  function showToast(message: string, type: Toast['type'] = 'info', duration = 5000) {
    // FR-F6.1 / P9: cap at 5 visible toasts; drop oldest before pushing.
    while (toasts.value.length >= MAX_VISIBLE_TOASTS) {
      dismissToast(toasts.value[0].id)
    }
    const id = ++toastId
    toasts.value.push({ id, message, type, duration })
    const handle = setTimeout(() => {
      dismissToast(id)
    }, duration)
    timers.set(id, handle)
  }

  function openPalette() {
    commandPaletteOpen.value = true
  }

  function closePalette() {
    commandPaletteOpen.value = false
  }

  return {
    commandPaletteOpen,
    uploadWizardOpen,
    toasts,
    showToast,
    dismissToast,
    openPalette,
    closePalette,
  }
})
