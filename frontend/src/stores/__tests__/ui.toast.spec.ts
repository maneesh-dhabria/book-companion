import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import { useUiStore } from '@/stores/ui'

describe('useUiStore.showToast (FR-04)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('actionable toast persists past duration', () => {
    const ui = useUiStore()
    ui.showToast('Retry?', 'error', {
      actionable: true,
      action: { label: 'Retry', onClick: () => {} },
      dedupeKey: 'k',
      dismissible: false,
    })
    vi.advanceTimersByTime(60_000)
    expect(ui.toasts).toHaveLength(1)
  })

  it('dismissToast no-op on actionable+!dismissible', () => {
    const ui = useUiStore()
    ui.showToast('Retry?', 'error', {
      actionable: true,
      action: { label: 'Retry', onClick: () => {} },
      dedupeKey: 'k',
      dismissible: false,
    })
    const id = ui.toasts[0].id
    ui.dismissToast(id)
    expect(ui.toasts).toHaveLength(1)
  })

  it('same dedupeKey replaces in 5s window preserving id', () => {
    const ui = useUiStore()
    ui.showToast('A', 'error', { dedupeKey: 'k' })
    const firstId = ui.toasts[0].id
    vi.advanceTimersByTime(2000)
    ui.showToast('B', 'error', { dedupeKey: 'k' })
    expect(ui.toasts).toHaveLength(1)
    expect(ui.toasts[0].id).toBe(firstId)
    expect(ui.toasts[0].message).toBe('B')
  })

  it('different dedupeKey stacks', () => {
    const ui = useUiStore()
    ui.showToast('A', 'error', { dedupeKey: 'k1' })
    ui.showToast('B', 'error', { dedupeKey: 'k2' })
    expect(ui.toasts).toHaveLength(2)
  })

  it('clearByKey clears only matching dedupeKey', () => {
    const ui = useUiStore()
    ui.showToast('A', 'error', { dedupeKey: 'k1' })
    ui.showToast('B', 'error', { dedupeKey: 'k2' })
    ui.clearByKey('k1')
    expect(ui.toasts.map((t) => t.message)).toEqual(['B'])
  })

  it('legacy positional signature unchanged', () => {
    const ui = useUiStore()
    ui.showToast('saved', 'success', 3000)
    expect(ui.toasts[0].message).toBe('saved')
    expect(ui.toasts[0].duration).toBe(3000)
  })
})
