import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import ReaderSettingsPopover from '../ReaderSettingsPopover.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'

const PRESETS = [
  {
    id: 1,
    name: 'Light',
    font_family: 'Georgia',
    font_size_px: 16,
    line_spacing: 1.6,
    content_width_px: 720,
    theme: 'light',
    created_at: '',
  },
  {
    id: 2,
    name: 'Sepia',
    font_family: 'Georgia',
    font_size_px: 16,
    line_spacing: 1.6,
    content_width_px: 720,
    theme: 'sepia',
    created_at: '',
  },
]

describe('ReaderSettingsPopover', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('clicking a shipped-theme card calls applyPreset for the matching preset name', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    const spy = vi.spyOn(s, 'applyPreset').mockImplementation(() => {})
    const w = mount(ReaderSettingsPopover)
    const sepiaCard = w
      .findAll('.theme-card')
      .find((c) => /Sepia/i.test(c.text()))!
    expect(sepiaCard).toBeTruthy()
    await sepiaCard.trigger('click')
    expect(spy).toHaveBeenCalledWith(2)
  })

  it('shipped-theme without a matching preset name is a no-op (does not break)', async () => {
    const s = useReaderSettingsStore()
    s.presets = [PRESETS[0]] as never
    s.popoverOpen = true
    const spy = vi.spyOn(s, 'applyPreset').mockImplementation(() => {})
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const w = mount(ReaderSettingsPopover)
    const sepiaCard = w
      .findAll('.theme-card')
      .find((c) => /Sepia/i.test(c.text()))!
    await sepiaCard.trigger('click')
    expect(spy).not.toHaveBeenCalled()
    expect(warnSpy).toHaveBeenCalled()
  })

  it('does not render Save-as-Preset block', () => {
    const s = useReaderSettingsStore()
    s.popoverOpen = true
    const w = mount(ReaderSettingsPopover)
    expect(w.text()).not.toMatch(/Save as Preset/i)
  })

  it('does not render the standalone Custom theme-card', () => {
    const s = useReaderSettingsStore()
    s.popoverOpen = true
    const w = mount(ReaderSettingsPopover)
    expect(w.find('.theme-card.custom').exists()).toBe(false)
  })
})
