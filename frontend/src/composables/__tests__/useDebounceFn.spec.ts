import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useDebounceFn } from '../useDebounceFn'

const mountHarness = (setup: () => unknown) =>
  mount(defineComponent({ setup, render: () => h('div') }))

describe('useDebounceFn', () => {
  it('debounces trailing-edge calls', async () => {
    vi.useFakeTimers()
    try {
      const spy = vi.fn()
      let debounced: ReturnType<typeof useDebounceFn<[number]>>
      mountHarness(() => {
        debounced = useDebounceFn((n: number) => spy(n), 100)
      })
      debounced!(1)
      debounced!(2)
      debounced!(3)
      vi.advanceTimersByTime(99)
      expect(spy).not.toHaveBeenCalled()
      vi.advanceTimersByTime(2)
      expect(spy).toHaveBeenCalledOnce()
      expect(spy).toHaveBeenCalledWith(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('cancel() suppresses pending call', async () => {
    vi.useFakeTimers()
    try {
      const spy = vi.fn()
      let debounced: ReturnType<typeof useDebounceFn<[number]>>
      mountHarness(() => {
        debounced = useDebounceFn((n: number) => spy(n), 50)
      })
      debounced!(1)
      debounced!.cancel()
      vi.advanceTimersByTime(100)
      expect(spy).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('flush() runs pending call immediately', () => {
    vi.useFakeTimers()
    try {
      const spy = vi.fn()
      let debounced: ReturnType<typeof useDebounceFn<[string]>>
      mountHarness(() => {
        debounced = useDebounceFn((v: string) => spy(v), 200)
      })
      debounced!('hi')
      debounced!.flush()
      expect(spy).toHaveBeenCalledWith('hi')
    } finally {
      vi.useRealTimers()
    }
  })
})
