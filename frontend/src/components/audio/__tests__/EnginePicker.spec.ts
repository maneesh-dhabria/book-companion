import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'

import EnginePicker from '../EnginePicker.vue'

describe('EnginePicker (FR-11)', () => {
  it('renders two segments with correct aria-pressed for the bound engine', () => {
    const wrapper = mount(EnginePicker, { props: { modelValue: 'mp3' } })
    const buttons = wrapper.findAll('[role="radio"]')
    expect(buttons.length).toBe(2)
    const mp3Btn = buttons.find((b) => b.text().includes('MP3'))
    const wsBtn = buttons.find((b) => b.text().includes('Web Speech'))
    expect(mp3Btn?.attributes('aria-checked')).toBe('true')
    expect(wsBtn?.attributes('aria-checked')).toBe('false')
    expect(wrapper.find('[role="radiogroup"]').exists()).toBe(true)
  })

  it('clicking the alternative segment emits update:modelValue with the new engine', async () => {
    const wrapper = mount(EnginePicker, { props: { modelValue: 'mp3' } })
    const wsBtn = wrapper
      .findAll('[role="radio"]')
      .find((b) => b.text().includes('Web Speech'))!
    await wsBtn.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['web-speech']])
  })

  it('clicking the same segment is a no-op', async () => {
    const wrapper = mount(EnginePicker, { props: { modelValue: 'mp3' } })
    const mp3Btn = wrapper.findAll('[role="radio"]').find((b) => b.text().includes('MP3'))!
    await mp3Btn.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
