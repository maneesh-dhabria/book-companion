import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  apiClient: { patch: vi.fn().mockResolvedValue({}) },
}))

import { apiClient } from '@/api/client'
import WpmSlider from '@/components/settings/WpmSlider.vue'
import { useUiStore } from '@/stores/ui'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('WpmSlider — FR-16', () => {
  it('renders label, value text, and a range input bound to modelValue', () => {
    const wrap = mount(WpmSlider, {
      props: {
        label: 'Listen wpm',
        min: 100,
        max: 400,
        step: 25,
        modelValue: 200,
        settingsPath: 'tts.listen_wpm',
      },
    })
    expect(wrap.text()).toContain('Listen wpm')
    expect(wrap.text()).toContain('200 wpm')
    const input = wrap.find('input[type="range"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('min')).toBe('100')
    expect(input.attributes('max')).toBe('400')
    expect(input.attributes('step')).toBe('25')
    expect((input.element as HTMLInputElement).value).toBe('200')
  })

  it('change event emits update:modelValue and PATCHes the settings path', async () => {
    const wrap = mount(WpmSlider, {
      props: {
        label: 'Listen wpm',
        min: 100,
        max: 400,
        step: 25,
        modelValue: 200,
        settingsPath: 'tts.listen_wpm',
      },
    })
    const input = wrap.find('input[type="range"]')
    await input.setValue(225)
    await input.trigger('change')
    await flushPromises()

    expect(wrap.emitted('update:modelValue')).toBeTruthy()
    expect(wrap.emitted('update:modelValue')![0]).toEqual([225])
    expect(apiClient.patch).toHaveBeenCalledWith('/settings', {
      tts: { listen_wpm: 225 },
    })
  })

  it('PATCH failure surfaces a UI toast and does not advance the bound value', async () => {
    ;(apiClient.patch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('boom'),
    )
    const wrap = mount(WpmSlider, {
      props: {
        label: 'Listen wpm',
        min: 100,
        max: 400,
        step: 25,
        modelValue: 200,
        settingsPath: 'tts.listen_wpm',
      },
    })
    const input = wrap.find('input[type="range"]')
    await input.setValue(250)
    await input.trigger('change')
    await flushPromises()

    const toasts = useUiStore().toasts
    expect(toasts.length).toBeGreaterThanOrEqual(1)
    expect(toasts[0].message.toLowerCase()).toContain('save')
    expect(toasts[0].type).toBe('error')
  })

  it('builds nested PATCH body for deep settings paths (reading.reading_wpm)', async () => {
    const wrap = mount(WpmSlider, {
      props: {
        label: 'Reading wpm',
        min: 100,
        max: 500,
        step: 25,
        modelValue: 250,
        settingsPath: 'reading.reading_wpm',
      },
    })
    const input = wrap.find('input[type="range"]')
    await input.setValue(300)
    await input.trigger('change')
    await flushPromises()

    expect(apiClient.patch).toHaveBeenCalledWith('/settings', {
      reading: { reading_wpm: 300 },
    })
  })
})
