import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PresetGrid from '../PresetGrid.vue'

const presets = [
  { id: 'practitioner_bullets', label: 'Practitioner', description: 'Bullet-form' },
  { id: 'academic_detailed', label: 'Academic', description: 'Detailed prose' },
]

describe('PresetGrid', () => {
  it('renders one card per preset with label + description', () => {
    const w = mount(PresetGrid, { props: { presets, modelValue: null } })
    const cards = w.findAll('[data-testid="preset-card"]')
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain('Practitioner')
    expect(cards[0].text()).toContain('Bullet-form')
  })

  it('emits update:modelValue on card click', async () => {
    const w = mount(PresetGrid, { props: { presets, modelValue: null } })
    await w.findAll('[data-testid="preset-card"]')[1].trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['academic_detailed'])
  })

  it('pre-selects card when modelValue is provided', () => {
    const w = mount(PresetGrid, {
      props: { presets, modelValue: 'academic_detailed' },
    })
    expect(
      w.findAll('[data-testid="preset-card"]')[1].classes(),
    ).toContain('selected')
  })
})
