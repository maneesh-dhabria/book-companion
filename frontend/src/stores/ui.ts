import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
  duration: number
}

let toastId = 0

export const useUiStore = defineStore('ui', () => {
  const commandPaletteOpen = ref(false)
  const uploadWizardOpen = ref(false)
  const toasts = ref<Toast[]>([])

  function showToast(message: string, type: Toast['type'] = 'info', duration = 5000) {
    const id = ++toastId
    toasts.value.push({ id, message, type, duration })
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, duration)
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
    openPalette,
    closePalette,
  }
})
