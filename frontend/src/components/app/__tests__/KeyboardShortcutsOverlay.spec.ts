import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import KeyboardShortcutsOverlay from '@/components/app/KeyboardShortcutsOverlay.vue'

describe('KeyboardShortcutsOverlay (FR-E09)', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('is hidden by default', () => {
    const w = mount(KeyboardShortcutsOverlay)
    expect(w.find('[data-testid="keyboard-shortcuts-overlay"]').exists()).toBe(false)
  })

  it('toggles visible on `?` keydown when no input is focused', async () => {
    const w = mount(KeyboardShortcutsOverlay, { attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await w.vm.$nextTick()
    expect(w.find('[data-testid="keyboard-shortcuts-overlay"]').exists()).toBe(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await w.vm.$nextTick()
    expect(w.find('[data-testid="keyboard-shortcuts-overlay"]').exists()).toBe(false)
    w.unmount()
  })

  it('does NOT toggle when an input is focused', async () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    const w = mount(KeyboardShortcutsOverlay, { attachTo: document.body })
    input.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true }))
    await w.vm.$nextTick()
    expect(w.find('[data-testid="keyboard-shortcuts-overlay"]').exists()).toBe(false)
    w.unmount()
  })

  it('closes on Escape', async () => {
    const w = mount(KeyboardShortcutsOverlay, { attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await w.vm.$nextTick()
    expect(w.find('[data-testid="keyboard-shortcuts-overlay"]').exists()).toBe(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await w.vm.$nextTick()
    expect(w.find('[data-testid="keyboard-shortcuts-overlay"]').exists()).toBe(false)
    w.unmount()
  })

  it('lists Space, →, ←, ?, Esc shortcuts', async () => {
    const w = mount(KeyboardShortcutsOverlay, { attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
    await w.vm.$nextTick()
    const text = w.text()
    expect(text).toContain('Space')
    expect(text).toContain('→')
    expect(text).toContain('←')
    expect(text).toContain('Esc')
    w.unmount()
  })
})
