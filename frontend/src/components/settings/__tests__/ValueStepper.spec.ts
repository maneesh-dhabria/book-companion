import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'

import Stepper from '../ValueStepper.vue'

describe('Stepper', () => {
  it('renders − [value] + and emits update on click', async () => {
    const w = mount(Stepper, {
      props: { modelValue: 16, step: 1, format: (v: number) => `${v}px`, ariaLabel: 'Size' },
    })
    expect(w.text()).toContain('16px')
    const buttons = w.findAll('button')
    await buttons[1].trigger('click') // +
    expect(w.emitted('update:modelValue')![0]).toEqual([17])
    await buttons[0].trigger('click') // −
    expect(w.emitted('update:modelValue')![1]).toEqual([15])
  })

  it('respects custom step size for fractional values', async () => {
    const w = mount(Stepper, {
      props: { modelValue: 1.6, step: 0.1, format: (v: number) => v.toFixed(1), ariaLabel: 'Spacing' },
    })
    await w.findAll('button')[1].trigger('click')
    const emitted = w.emitted('update:modelValue')![0][0] as number
    expect(emitted).toBeCloseTo(1.7, 5)
  })
})
