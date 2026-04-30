import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick } from 'vue'

import CustomEditor from '../CustomEditor.vue'
import { useReaderSettingsStore } from '@/stores/readerSettings'

describe('CustomEditor', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('clicking a bg swatch calls store.stageCustom with new bg', async () => {
    const s = useReaderSettingsStore()
    s.customTheme = { name: 'Custom', bg: '#ffffff', fg: '#111827', accent: '#4f46e5' }
    const stageSpy = vi.spyOn(s, 'stageCustom')
    const w = mount(CustomEditor)
    const bgRow = w.findAllComponents({ name: 'ColorSwatchRow' })[0]
    bgRow.vm.$emit('update:modelValue', '#000000')
    await nextTick()
    expect(stageSpy).toHaveBeenCalledWith(expect.objectContaining({ bg: '#000000' }))
  })

  it('Save button disabled when not dirty', () => {
    const s = useReaderSettingsStore()
    s.dirty = false
    const w = mount(CustomEditor)
    const save = w.findAll('button').find((b) => /save/i.test(b.text()))!
    expect(save.attributes('disabled')).toBeDefined()
  })

  it('Save button enabled and calls saveCustom + applyCustom when dirty', async () => {
    const s = useReaderSettingsStore()
    s.customTheme = { name: 'Custom', bg: '#fff', fg: '#111', accent: '#4f46e5' }
    s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#4f46e5' }
    s.dirty = true
    const saveSpy = vi.spyOn(s, 'saveCustom')
    const applySpy = vi.spyOn(s, 'applyCustom').mockImplementation(() => {})
    const w = mount(CustomEditor)
    const save = w.findAll('button').find((b) => /save/i.test(b.text()))!
    expect(save.attributes('disabled')).toBeUndefined()
    await save.trigger('click')
    expect(saveSpy).toHaveBeenCalled()
    expect(applySpy).toHaveBeenCalled()
  })

  it('Revert button calls discardCustom', async () => {
    const s = useReaderSettingsStore()
    s.dirty = true
    s.pendingCustom = { name: 'Custom', bg: '#000', fg: '#fff', accent: '#4f46e5' }
    const discardSpy = vi.spyOn(s, 'discardCustom')
    const w = mount(CustomEditor)
    const revert = w.findAll('button').find((b) => /revert/i.test(b.text()))!
    await revert.trigger('click')
    expect(discardSpy).toHaveBeenCalled()
  })

  it('shows dirty hint only when dirty', async () => {
    const s = useReaderSettingsStore()
    s.dirty = false
    const w = mount(CustomEditor)
    expect(w.text()).not.toMatch(/not saved/i)
    s.dirty = true
    await nextTick()
    expect(w.text()).toMatch(/not saved/i)
  })

  it('focuses first BACKGROUND swatch on mount (FR-13b)', async () => {
    const s = useReaderSettingsStore()
    s.customTheme = { name: 'Custom', bg: '#fff', fg: '#111', accent: '#4f46e5' }
    const w = mount(CustomEditor, { attachTo: document.body })
    await nextTick()
    await nextTick()
    const firstBgSwatch = w.findAllComponents({ name: 'ColorSwatchRow' })[0]
      .findAll('button')[0].element as HTMLElement
    expect(document.activeElement).toBe(firstBgSwatch)
    w.unmount()
  })

  it('font select calls updateSetting on change', async () => {
    const s = useReaderSettingsStore()
    const updateSpy = vi.spyOn(s, 'updateSetting')
    const w = mount(CustomEditor)
    const fontSelect = w.find('select')
    await fontSelect.setValue('Inter')
    expect(updateSpy).toHaveBeenCalledWith('font_family', 'Inter')
  })

  it('size stepper increments call updateSetting', async () => {
    const s = useReaderSettingsStore()
    s.currentSettings = { ...s.currentSettings, font_size_px: 16 }
    const updateSpy = vi.spyOn(s, 'updateSetting')
    const w = mount(CustomEditor)
    const stepper = w.findAllComponents({ name: 'ValueStepper' }).find((c) => c.props('ariaLabel') === 'Size')!
    stepper.vm.$emit('update:modelValue', 17)
    await nextTick()
    expect(updateSpy).toHaveBeenCalledWith('font_size_px', 17)
  })
})
