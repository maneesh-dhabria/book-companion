import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import ToastContainer from '../ToastContainer.vue'
import { useUiStore } from '@/stores/ui'

describe('ToastContainer', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders one element per active toast with type class', () => {
    const ui = useUiStore()
    ui.showToast('hello', 'success', 99999)
    ui.showToast('boom', 'error', 99999)
    const w = mount(ToastContainer)
    expect(w.findAll('[data-testid="toast"]').length).toBe(2)
    expect(w.find('.toast--success').exists()).toBe(true)
    expect(w.find('.toast--error').exists()).toBe(true)
  })

  it('manual close removes the toast', async () => {
    const ui = useUiStore()
    ui.showToast('bye', 'info', 99999)
    const w = mount(ToastContainer)
    await w.find('button[data-testid="toast-close"]').trigger('click')
    expect(ui.toasts.length).toBe(0)
  })

  it('auto-dismisses after duration', async () => {
    vi.useFakeTimers()
    const ui = useUiStore()
    ui.showToast('flash', 'info', 100)
    const w = mount(ToastContainer)
    expect(w.findAll('[data-testid="toast"]').length).toBe(1)
    vi.advanceTimersByTime(200)
    await w.vm.$nextTick()
    expect(ui.toasts.length).toBe(0)
    vi.useRealTimers()
  })

  it('FIFO drops oldest when 6th toast is pushed', () => {
    const ui = useUiStore()
    for (let i = 0; i < 5; i++) ui.showToast(`t${i}`, 'info', 99999)
    ui.showToast('t5', 'info', 99999)
    expect(ui.toasts.length).toBe(5)
    expect(ui.toasts.find((t) => t.message === 't0')).toBeUndefined()
    expect(ui.toasts.find((t) => t.message === 't5')).toBeDefined()
  })

  // FR-F13 regression: aria-live region must be present so screen readers
  // announce toasts emitted by useUiStore().showToast.
  it('renders aria-live=polite region', () => {
    const w = mount(ToastContainer)
    const region = w.find('.toast-stack')
    expect(region.attributes('aria-live')).toBe('polite')
  })
})
