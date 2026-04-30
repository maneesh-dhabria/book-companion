import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import ThemeGrid from '../ThemeGrid.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'

const PRESETS = [
  { id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' },
  { id: 2, name: 'Dark', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'dark', created_at: '' },
  { id: 3, name: 'Sepia', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'sepia', created_at: '' },
  { id: 4, name: 'Night', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'night', created_at: '' },
  { id: 5, name: 'Paper', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'paper', created_at: '' },
  { id: 6, name: 'High Contrast', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'contrast', created_at: '' },
]

describe('ThemeGrid', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders 7 cards in spec order: Light, Dark, Sepia, Night, Paper, High Contrast, Custom', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const w = mount(ThemeGrid)
    const labels = w.findAllComponents({ name: 'ThemeCard' }).map((c) => c.props('label'))
    expect(labels).toEqual(['Light', 'Dark', 'Sepia', 'Night', 'Paper', 'High Contrast', 'Custom'])
  })

  it('grid has role=radiogroup with aria-label', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const w = mount(ThemeGrid)
    const grid = w.get('[role="radiogroup"]')
    expect(grid.attributes('aria-label')).toMatch(/theme/i)
  })

  it('clicking Sepia card calls applyPreset(3)', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const spy = vi.spyOn(s, 'applyPreset').mockImplementation(() => {})
    const w = mount(ThemeGrid)
    const sepia = w.findAllComponents({ name: 'ThemeCard' }).find((c) => c.props('label') === 'Sepia')!
    await sepia.trigger('click')
    expect(spy).toHaveBeenCalledWith(3)
  })

  it('clicking Custom card (when not active) calls applyCustom + toggleCustomEditor', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const applyCustomSpy = vi.spyOn(s, 'applyCustom').mockImplementation(() => {})
    const toggleSpy = vi.spyOn(s, 'toggleCustomEditor').mockImplementation(() => {})
    const w = mount(ThemeGrid)
    const custom = w.findAllComponents({ name: 'ThemeCard' }).find((c) => c.props('label') === 'Custom')!
    await custom.trigger('click')
    expect(applyCustomSpy).toHaveBeenCalled()
    expect(toggleSpy).toHaveBeenCalled()
  })

  it('clicking Custom (already active) calls toggleCustomEditor only', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'custom'
    const applyCustomSpy = vi.spyOn(s, 'applyCustom').mockImplementation(() => {})
    const toggleSpy = vi.spyOn(s, 'toggleCustomEditor').mockImplementation(() => {})
    const w = mount(ThemeGrid)
    const custom = w.findAllComponents({ name: 'ThemeCard' }).find((c) => c.props('label') === 'Custom')!
    await custom.trigger('click')
    expect(applyCustomSpy).not.toHaveBeenCalled()
    expect(toggleSpy).toHaveBeenCalled()
  })

  it('arrow-right moves focus to next card', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'system:1'
    const w = mount(ThemeGrid, { attachTo: document.body })
    const cards = w.findAll('button[role="radio"]')
    await cards[0].trigger('keydown', { key: 'ArrowRight' })
    expect(cards[1].attributes('tabindex')).toBe('0')
    expect(cards[0].attributes('tabindex')).toBe('-1')
    w.unmount()
  })

  it('arrow-right wraps from Custom (last) back to Light (first)', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.appliedPresetKey = 'custom'
    const w = mount(ThemeGrid, { attachTo: document.body })
    const cards = w.findAll('button[role="radio"]')
    await cards[6].trigger('keydown', { key: 'ArrowRight' })
    expect(cards[0].attributes('tabindex')).toBe('0')
    w.unmount()
  })

  it('Enter key on focused card activates it', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const spy = vi.spyOn(s, 'applyPreset').mockImplementation(() => {})
    const w = mount(ThemeGrid)
    const cards = w.findAll('button[role="radio"]')
    await cards[2].trigger('keydown', { key: 'Enter' })
    expect(spy).toHaveBeenCalledWith(3)
  })

  it('renders empty grid cells (FR-02b) as inert and aria-hidden', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    const w = mount(ThemeGrid)
    const empties = w.findAll('.empty-cell')
    expect(empties.length).toBe(2)
    empties.forEach((e) => {
      expect(e.attributes('aria-hidden')).toBe('true')
      expect((e.element as HTMLElement).style.pointerEvents).toBe('none')
    })
  })

  it('shows error notice when presets is empty (E1 / Q5)', () => {
    const s = useReaderSettingsStore()
    s.presets = [] as never
    const w = mount(ThemeGrid)
    expect(w.find('.presets-error').exists()).toBe(true)
    const labels = w.findAllComponents({ name: 'ThemeCard' }).map((c) => c.props('label'))
    expect(labels).toEqual(['Custom'])
  })
})
