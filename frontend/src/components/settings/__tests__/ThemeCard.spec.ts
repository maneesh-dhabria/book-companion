import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'

import ThemeCard from '../ThemeCard.vue'

describe('ThemeCard', () => {
  it('renders bg as background and fg as text colour', () => {
    const w = mount(ThemeCard, {
      props: { label: 'Sepia', bg: '#f4ecd8', fg: '#3a2f1d', active: false },
    })
    const el = w.get('button')
    expect(el.attributes('style')).toContain('background')
    expect(el.text()).toContain('Sepia')
    expect(el.text()).toContain('Aa')
  })

  it('shows ✓ glyph and aria-pressed=true when active', () => {
    const w = mount(ThemeCard, {
      props: { label: 'Light', bg: '#fff', fg: '#111', active: true },
    })
    expect(w.text()).toContain('✓')
    expect(w.get('button').attributes('aria-pressed')).toBe('true')
  })

  it('aria-pressed=false when inactive', () => {
    const w = mount(ThemeCard, {
      props: { label: 'Light', bg: '#fff', fg: '#111', active: false },
    })
    expect(w.get('button').attributes('aria-pressed')).toBe('false')
    expect(w.text()).not.toContain('✓')
  })

  it('emits click when clicked', async () => {
    const w = mount(ThemeCard, {
      props: { label: 'Light', bg: '#fff', fg: '#111', active: false },
    })
    await w.get('button').trigger('click')
    expect(w.emitted('click')).toBeTruthy()
  })

  it('honours tabindex prop for roving-tabindex pattern', () => {
    const w = mount(ThemeCard, {
      props: { label: 'Light', bg: '#fff', fg: '#111', active: false, tabindex: -1 },
    })
    expect(w.get('button').attributes('tabindex')).toBe('-1')
  })
})
