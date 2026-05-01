import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ContentToggle from '@/components/reader/ContentToggle.vue'

describe('ContentToggle', () => {
  it('inactive tab is fully clickable, not visually disabled', async () => {
    const wrapper = mount(ContentToggle, { props: { mode: 'summary', hasSummary: true } })
    const inactive = wrapper
      .findAll('.toggle-btn')
      .find((b) => !b.classes().includes('active'))!
    expect(inactive.attributes('disabled')).toBeUndefined()
    await inactive.trigger('click')
    expect(wrapper.emitted('toggle')).toBeDefined()
  })

  it('active tab still emits on re-click but stays styled active', async () => {
    const wrapper = mount(ContentToggle, { props: { mode: 'original', hasSummary: true } })
    const active = wrapper.find('.toggle-btn.active')
    expect(active.attributes('disabled')).toBeUndefined()
    await active.trigger('click')
    expect(wrapper.emitted('toggle')).toBeDefined()
  })
})
