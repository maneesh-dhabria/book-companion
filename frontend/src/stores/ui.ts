import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
  duration: number
  actionable: boolean
  action?: { label: string; onClick: () => void | Promise<void> }
  dedupeKey?: string
  dismissible: boolean
}

export interface ShowToastOptions {
  duration?: number
  actionable?: boolean
  action?: Toast['action']
  dedupeKey?: string
  dismissible?: boolean
}

const MAX_VISIBLE_TOASTS = 5

let toastId = 0

export const useUiStore = defineStore('ui', () => {
  const commandPaletteOpen = ref(false)
  const uploadWizardOpen = ref(false)
  const bulkSelectMode = ref(false)
  const toasts = ref<Toast[]>([])
  // Per-toast dismiss timers, keyed by id, so manual close cancels its timer
  // and the FIFO cap can also cancel the dropped oldest toast's timer.
  const timers = new Map<number, ReturnType<typeof setTimeout>>()
  // dedupeKey → toast.id. CLAUDE.md gotcha #28: use reactive(new Map()) so
  // collection mutations track properly across recomposed state.
  const dedupeKeys = reactive(new Map<string, number>())

  function dismissToast(id: number) {
    const target = toasts.value.find((t) => t.id === id)
    // FR-04: actionable + non-dismissible toasts ignore dismissToast entirely.
    if (target && target.dismissible === false) return
    const handle = timers.get(id)
    if (handle !== undefined) {
      clearTimeout(handle)
      timers.delete(id)
    }
    if (target?.dedupeKey) dedupeKeys.delete(target.dedupeKey)
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }

  function showToast(
    message: string,
    type: Toast['type'] = 'info',
    durationOrOptions: number | ShowToastOptions = 5000,
  ) {
    const opts: ShowToastOptions =
      typeof durationOrOptions === 'number' ? { duration: durationOrOptions } : durationOrOptions
    const duration = opts.duration ?? 5000
    const actionable = opts.actionable ?? false
    // Default: actionable toasts are sticky; non-actionable toasts dismissible.
    const dismissible = opts.dismissible ?? !actionable

    // Dedupe replacement — preserve id so callers tracking it stay valid.
    if (opts.dedupeKey && dedupeKeys.has(opts.dedupeKey)) {
      const existingId = dedupeKeys.get(opts.dedupeKey)!
      const idx = toasts.value.findIndex((t) => t.id === existingId)
      if (idx >= 0) {
        toasts.value[idx] = {
          id: existingId,
          message,
          type,
          duration,
          actionable,
          action: opts.action,
          dedupeKey: opts.dedupeKey,
          dismissible,
        }
        const old = timers.get(existingId)
        if (old !== undefined) {
          clearTimeout(old)
          timers.delete(existingId)
        }
        if (dismissible) {
          timers.set(
            existingId,
            setTimeout(() => dismissToast(existingId), duration),
          )
        }
        return
      }
    }

    // FIFO cap (FR-F6.1 / P9): drop oldest before pushing the 6th.
    while (toasts.value.length >= MAX_VISIBLE_TOASTS) {
      // Force-drop the oldest even if non-dismissible — cap is structural.
      forceDismiss(toasts.value[0].id)
    }
    const id = ++toastId
    toasts.value.push({
      id,
      message,
      type,
      duration,
      actionable,
      action: opts.action,
      dedupeKey: opts.dedupeKey,
      dismissible,
    })
    if (opts.dedupeKey) dedupeKeys.set(opts.dedupeKey, id)
    if (dismissible) {
      timers.set(
        id,
        setTimeout(() => dismissToast(id), duration),
      )
    }
  }

  /** Internal helper: drop a toast unconditionally (bypasses the
   * dismissible-guard so FIFO cap and clearByKey can do their job). */
  function forceDismiss(id: number) {
    const target = toasts.value.find((t) => t.id === id)
    const handle = timers.get(id)
    if (handle !== undefined) {
      clearTimeout(handle)
      timers.delete(id)
    }
    if (target?.dedupeKey) dedupeKeys.delete(target.dedupeKey)
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }

  /** FR-04: canonical clear path for actionable toasts (e.g. retry success). */
  function clearByKey(key: string) {
    const id = dedupeKeys.get(key)
    if (id === undefined) return
    forceDismiss(id)
  }

  function openPalette() {
    commandPaletteOpen.value = true
  }

  function closePalette() {
    commandPaletteOpen.value = false
  }

  function toggleBulkSelect(value?: boolean) {
    const next = typeof value === 'boolean' ? value : !bulkSelectMode.value
    bulkSelectMode.value = next
  }

  return {
    commandPaletteOpen,
    uploadWizardOpen,
    bulkSelectMode,
    toggleBulkSelect,
    toasts,
    showToast,
    dismissToast,
    clearByKey,
    openPalette,
    closePalette,
  }
})
