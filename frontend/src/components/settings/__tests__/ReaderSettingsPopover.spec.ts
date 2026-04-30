import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach } from 'vitest'

import ReaderSettingsPopover from '../ReaderSettingsPopover.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'

const PRESETS = [
  { id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' },
]

describe('ReaderSettingsPopover (T7 smoke)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders ThemeGrid and chrome toggles when popoverOpen', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'ThemeGrid' }).exists()).toBe(true)
    expect(w.text()).toMatch(/highlights/i)
  })

  it('does not render CustomEditor by default', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    s.editingCustom = false
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(false)
  })

  it('renders CustomEditor when editingCustom and Custom is applied', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    s.appliedPresetKey = 'custom'
    s.editingCustom = true
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(true)
  })

  it('does NOT render font/size/spacing/width controls in default state (FR-10)', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    s.editingCustom = false
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(false)
    expect(w.text()).not.toMatch(/Line Spacing/i)
    expect(w.text()).not.toMatch(/Content Width/i)
  })

  it('does NOT render StickySaveBar (FR-29 / D5)', () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'StickySaveBar' }).exists()).toBe(false)
  })

  it('Escape key closes the popover', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    mount(ReaderSettingsPopover, { attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await new Promise((r) => setTimeout(r, 0))
    expect(s.popoverOpen).toBe(false)
  })

  it('outside click closes the popover', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    const w = mount(ReaderSettingsPopover, { attachTo: document.body })
    const outside = document.createElement('div')
    document.body.appendChild(outside)
    outside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await new Promise((r) => setTimeout(r, 0))
    expect(s.popoverOpen).toBe(false)
    outside.remove()
    w.unmount()
  })

  it('click inside popover does NOT close', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    const w = mount(ReaderSettingsPopover, { attachTo: document.body })
    const inside = w.find('.settings-popover').element
    inside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await new Promise((r) => setTimeout(r, 0))
    expect(s.popoverOpen).toBe(true)
    w.unmount()
  })

  it("shows preset-load-fail notice in popover when presets empty", () => {
    const s = useReaderSettingsStore()
    s.presets = [] as never
    s.popoverOpen = true
    const w = mount(ReaderSettingsPopover)
    expect(w.text()).toMatch(/couldn't load themes/i)
  })

  it('switching from Custom to Sepia mid-edit collapses editor and clears pending state (E5)', async () => {
    const s = useReaderSettingsStore()
    s.presets = [
      { id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' },
      { id: 3, name: 'Sepia', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'sepia', created_at: '' },
    ] as never
    s.popoverOpen = true
    await new Promise((r) => setTimeout(r, 0))
    s.appliedPresetKey = 'custom'
    s.editingCustom = true
    s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#abc' }
    s.dirty = true
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(true)
    const sepia = w.findAllComponents({ name: 'ThemeCard' }).find((c) => c.props('label') === 'Sepia')!
    await sepia.trigger('click')
    expect(s.appliedPresetKey).toBe('system:3')
    expect(s.editingCustom).toBe(false)
    expect(s.pendingCustom).toBeNull()
    expect(s.dirty).toBe(false)
  })

  it('toggling editor closed via second Custom click preserves pendingCustom (Q6/E6)', async () => {
    const s = useReaderSettingsStore()
    s.presets = [{ id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' }] as never
    s.popoverOpen = true
    await new Promise((r) => setTimeout(r, 0))
    s.appliedPresetKey = 'custom'
    s.editingCustom = true
    s.pendingCustom = { name: 'Custom', bg: '#222', fg: '#eee', accent: '#abc' }
    s.dirty = true
    const w = mount(ReaderSettingsPopover)
    const customCard = w.findAllComponents({ name: 'ThemeCard' }).find((c) => c.props('label') === 'Custom')!
    await customCard.trigger('click')
    expect(s.editingCustom).toBe(false)
    expect(s.pendingCustom).toEqual({ name: 'Custom', bg: '#222', fg: '#eee', accent: '#abc' })
    expect(s.dirty).toBe(true)
  })

  it('reopening the popover with Custom active leaves editor collapsed (D7/D12)', async () => {
    const s = useReaderSettingsStore()
    s.presets = [{ id: 1, name: 'Light', font_family: 'Georgia', font_size_px: 16, line_spacing: 1.6, content_width_px: 720, theme: 'light', created_at: '' }] as never
    s.appliedPresetKey = 'custom'
    s.editingCustom = true
    s.popoverOpen = true
    s.popoverOpen = false
    await new Promise((r) => setTimeout(r, 0))
    s.popoverOpen = true
    await new Promise((r) => setTimeout(r, 0))
    expect(s.editingCustom).toBe(false)
    const w = mount(ReaderSettingsPopover)
    expect(w.findComponent({ name: 'CustomEditor' }).exists()).toBe(false)
  })

  it('outside click preserves pendingCustom (E9)', async () => {
    const s = useReaderSettingsStore()
    s.presets = PRESETS as never
    s.popoverOpen = true
    s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#abc' }
    s.dirty = true
    const w = mount(ReaderSettingsPopover, { attachTo: document.body })
    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await new Promise((r) => setTimeout(r, 0))
    expect(s.pendingCustom).toEqual({ name: 'Custom', bg: '#000', fg: '#fff', accent: '#abc' })
    expect(s.dirty).toBe(true)
    w.unmount()
  })
})
