import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import PresetCards from '../PresetCards.vue'
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

describe('PresetCards', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders one card per preset plus a Custom card', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const w = mount(PresetCards)
    const cards = w.findAll('.preset-card')
    expect(cards.length).toBe(3)
    const custom = cards[cards.length - 1]
    expect(custom.text()).toMatch(/Custom/)
  })

  it('pencil icon renders only when Custom is the applied state', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const w = mount(PresetCards)
    expect(w.find('.preset-pencil').exists()).toBe(false)
    s.appliedPresetKey = 'custom'
    await w.vm.$nextTick()
    expect(w.find('.preset-pencil').exists()).toBe(true)
  })

  it('checkmark on system card renders top-right (no Custom modifier)', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'system:2'
    const w = mount(PresetCards)
    const checks = w.findAll('.preset-check')
    expect(checks.length).toBe(1)
    expect(checks[0].classes()).not.toContain('preset-check--custom')
  })

  it('checkmark on Custom card carries the --custom modifier', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'custom'
    const w = mount(PresetCards)
    const checks = w.findAll('.preset-check')
    expect(checks.length).toBe(1)
    expect(checks[0].classes()).toContain('preset-check--custom')
  })

  it('clicking a system card calls applyPreset with that id', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const spy = vi.spyOn(s, 'applyPreset').mockImplementation(() => {})
    const w = mount(PresetCards)
    await w.findAll('.preset-card')[1].trigger('click')
    expect(spy).toHaveBeenCalledWith(2)
  })

  it('first click on Custom (when not active) calls openCustomPicker', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'system:1'
    const spy = vi.spyOn(s, 'openCustomPicker').mockImplementation(() => {})
    const w = mount(PresetCards)
    const cards = w.findAll('.preset-card')
    await cards[cards.length - 1].trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('subsequent click on Custom (already active) calls applyCustom', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'custom'
    const spy = vi.spyOn(s, 'applyCustom').mockImplementation(() => {})
    const w = mount(PresetCards)
    const cards = w.findAll('.preset-card')
    await cards[cards.length - 1].trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('pencil click calls openCustomPicker', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'custom'
    const spy = vi.spyOn(s, 'openCustomPicker').mockImplementation(() => {})
    const w = mount(PresetCards)
    await w.find('.preset-pencil').trigger('click')
    expect(spy).toHaveBeenCalled()
  })
})
