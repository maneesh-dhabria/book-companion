import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatScopeSelector from '../ChatScopeSelector.vue'

describe('ChatScopeSelector', () => {
  it('toggles from section to book', async () => {
    const w = mount(ChatScopeSelector, {
      props: {
        modelValue: 'section',
        currentSectionTitle: 'Intro',
        bookTitle: 'Porter',
      },
    })
    await w.find('[data-testid="book-scope"]').trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['book'])
  })

  it('disables section toggle when no current section', () => {
    const w = mount(ChatScopeSelector, {
      props: {
        modelValue: 'book',
        currentSectionTitle: null,
        bookTitle: 'Porter',
      },
    })
    expect(w.find('[data-testid="section-scope"]').attributes('disabled')).toBeDefined()
  })

  it('marks the active scope', () => {
    const w = mount(ChatScopeSelector, {
      props: {
        modelValue: 'book',
        currentSectionTitle: 'Intro',
        bookTitle: 'Porter',
      },
    })
    expect(w.find('[data-testid="book-scope"]').classes()).toContain('active')
    expect(w.find('[data-testid="section-scope"]').classes()).not.toContain('active')
  })
})
