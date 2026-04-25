import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import TagChipInput from '../TagChipInput.vue'
import { useUiStore } from '@/stores/ui'

function makeWrapper(modelValue: string[] = []) {
  return mount(TagChipInput, {
    props: { modelValue },
    attachTo: document.body,
  })
}

describe('TagChipInput', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('default mode renders + Add tag button (no persistent input)', () => {
    const w = makeWrapper()
    expect(w.find('button.add-tag-btn').exists()).toBe(true)
    expect(w.find('input.chip-field').exists()).toBe(false)
    expect(w.find('button.add-tag-btn').text()).toMatch(/\+ Add tag/i)
  })

  it('clicking the button reveals a focused input and hides the button', async () => {
    const w = makeWrapper()
    await w.find('button.add-tag-btn').trigger('click')
    const input = w.find('input.chip-field').element as HTMLInputElement
    expect(input).toBeTruthy()
    expect(document.activeElement).toBe(input)
    expect(w.find('button.add-tag-btn').exists()).toBe(false)
  })

  it('Enter on non-empty input commits + clears + stays in edit mode', async () => {
    const w = makeWrapper()
    await w.find('button.add-tag-btn').trigger('click')
    const input = w.find('input.chip-field')
    await input.setValue('psychology')
    await input.trigger('keydown.enter')
    const emitted = w.emitted('update:modelValue')!
    expect(emitted[emitted.length - 1]).toEqual([['psychology']])
    expect((input.element as HTMLInputElement).value).toBe('')
    expect(w.find('input.chip-field').exists()).toBe(true)
  })

  it('Esc dismisses the input back to button mode', async () => {
    const w = makeWrapper()
    await w.find('button.add-tag-btn').trigger('click')
    await w.find('input.chip-field').trigger('keydown.escape')
    expect(w.find('button.add-tag-btn').exists()).toBe(true)
    expect(w.find('input.chip-field').exists()).toBe(false)
  })

  it('blur on empty input dismisses to button', async () => {
    const w = makeWrapper()
    await w.find('button.add-tag-btn').trigger('click')
    await w.find('input.chip-field').trigger('blur')
    expect(w.find('button.add-tag-btn').exists()).toBe(true)
  })

  it('blur on non-empty input commits + dismisses', async () => {
    const w = makeWrapper()
    await w.find('button.add-tag-btn').trigger('click')
    await w.find('input.chip-field').setValue('history')
    await w.find('input.chip-field').trigger('blur')
    const emitted = w.emitted('update:modelValue')!
    expect(emitted[emitted.length - 1]).toEqual([['history']])
    expect(w.find('button.add-tag-btn').exists()).toBe(true)
  })

  it('truncates at 64 chars and fires warning toast', async () => {
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    const w = makeWrapper()
    await w.find('button.add-tag-btn').trigger('click')
    await w.find('input.chip-field').setValue('a'.repeat(80))
    await w.find('input.chip-field').trigger('keydown.enter')
    const emitted = w.emitted('update:modelValue')!
    expect((emitted[emitted.length - 1][0] as string[])[0]).toHaveLength(64)
    expect(toastSpy).toHaveBeenCalledWith('Tag truncated to 64 characters', 'warning')
  })

  it('Backspace on empty deletes last chip', async () => {
    const w = makeWrapper(['old'])
    await w.find('button.add-tag-btn').trigger('click')
    await w.find('input.chip-field').trigger('keydown', { key: 'Backspace' })
    const emitted = w.emitted('update:modelValue')!
    expect(emitted[emitted.length - 1]).toEqual([[]])
  })
})
