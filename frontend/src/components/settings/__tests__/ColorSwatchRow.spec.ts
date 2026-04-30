import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'

import ColorSwatchRow from '../ColorSwatchRow.vue'

describe('ColorSwatchRow', () => {
  it('renders one button per palette colour and marks the active one', () => {
    const w = mount(ColorSwatchRow, {
      props: { palette: ['#fff', '#000', '#abc'], modelValue: '#000', ariaLabelPrefix: 'Background' },
    })
    const buttons = w.findAll('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[1].classes()).toContain('active')
    expect(buttons[0].classes()).not.toContain('active')
  })

  it('emits update:modelValue on swatch click', async () => {
    const w = mount(ColorSwatchRow, {
      props: { palette: ['#fff', '#000'], modelValue: '#fff', ariaLabelPrefix: 'Foreground' },
    })
    await w.findAll('button')[1].trigger('click')
    expect(w.emitted('update:modelValue')![0]).toEqual(['#000'])
  })

  it('aria-label uses prefix + colour', () => {
    const w = mount(ColorSwatchRow, {
      props: { palette: ['#fff'], modelValue: '#fff', ariaLabelPrefix: 'Background' },
    })
    expect(w.get('button').attributes('aria-label')).toBe('Background #fff')
  })
})
