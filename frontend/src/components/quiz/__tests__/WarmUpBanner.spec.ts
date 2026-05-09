import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import WarmUpBanner from '@/components/quiz/WarmUpBanner.vue'

describe('WarmUpBanner', () => {
  it('enumerates the actual concept labels in the banner copy', () => {
    const wrapper = mount(WarmUpBanner, {
      props: { missedConcepts: ['loss aversion'], partialConcepts: ['anchoring'] },
    })
    const text = wrapper.text()
    expect(text).toContain('loss aversion')
    expect(text).toContain('Missed')
    expect(text).toContain('anchoring')
    expect(text).toContain('Partial')
  })

  it('renders nothing when both arrays empty (FR-74)', () => {
    const wrapper = mount(WarmUpBanner, {
      props: { missedConcepts: [], partialConcepts: [] },
    })
    expect(wrapper.find('[data-test="warm-up-banner"]').exists()).toBe(false)
  })

  it('formats a list of three with serial comma', () => {
    const wrapper = mount(WarmUpBanner, {
      props: { missedConcepts: ['a', 'b', 'c'], partialConcepts: [] },
    })
    expect(wrapper.text()).toContain('a, b, and c')
  })
})
