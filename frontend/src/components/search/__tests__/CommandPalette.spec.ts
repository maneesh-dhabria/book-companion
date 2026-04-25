import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import CommandPalette from '../CommandPalette.vue'
import { useSearchStore } from '@/stores/search'
import { useUiStore } from '@/stores/ui'

function paletteInput(): HTMLInputElement | null {
  return document.querySelector<HTMLInputElement>('input.palette-input')
}

describe('CommandPalette', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ recent_searches: [] }),
    } as Response)
  })

  it('debounces typing into a single doQuickSearch call', async () => {
    const search = useSearchStore()
    const spy = vi
      .spyOn(search, 'doQuickSearch')
      .mockResolvedValue(undefined as never)
    const ui = useUiStore()
    ui.openPalette()
    mount(CommandPalette, { attachTo: document.body })
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()
    const input = paletteInput()!
    expect(input).toBeTruthy()
    for (const ch of 'hello world') {
      input.value = input.value + ch
      input.dispatchEvent(new Event('input'))
      await vi.advanceTimersByTimeAsync(50)
    }
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy).toHaveBeenCalledWith('hello world')
  })

  it('clears query on every open', async () => {
    const ui = useUiStore()
    const search = useSearchStore()
    search.query = 'leftover'
    ui.openPalette()
    mount(CommandPalette, { attachTo: document.body })
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()
    const input = paletteInput()!
    expect(input).toBeTruthy()
    expect(input.value).toBe('')
  })

  it('focuses the input on open', async () => {
    const ui = useUiStore()
    ui.openPalette()
    mount(CommandPalette, { attachTo: document.body })
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()
    const input = paletteInput()!
    expect(input).toBeTruthy()
    expect(document.activeElement).toBe(input)
  })
})
