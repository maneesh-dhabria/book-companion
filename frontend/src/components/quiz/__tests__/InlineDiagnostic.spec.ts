import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'

import InlineDiagnostic from '../InlineDiagnostic.vue'

describe('InlineDiagnostic (FR-05)', () => {
  it('renders nothing when diag is null', () => {
    const wrapper = mount(InlineDiagnostic, { props: { diag: null } })
    expect(wrapper.find('[data-testid="inline-diagnostic"]').exists()).toBe(false)
  })

  it('renders reason text and toggleable details with stderrTail', async () => {
    const wrapper = mount(InlineDiagnostic, {
      props: { diag: { reason: 'LLM provider error: boom', stderrTail: 'trace data' } },
    })
    const region = wrapper.find('[data-testid="inline-diagnostic"]')
    expect(region.exists()).toBe(true)
    expect(region.text()).toContain('LLM provider error: boom')
    const details = region.find('details')
    expect(details.exists()).toBe(true)
    expect(details.find('pre').text()).toBe('trace data')
  })

  it('omits <details> when stderrTail is null', () => {
    const wrapper = mount(InlineDiagnostic, {
      props: { diag: { reason: 'oops', stderrTail: null } },
    })
    expect(wrapper.find('details').exists()).toBe(false)
  })

  it('Dismiss link emits dismiss event', async () => {
    const wrapper = mount(InlineDiagnostic, {
      props: { diag: { reason: 'oops', stderrTail: null } },
    })
    await wrapper.find('button.bc-link').trigger('click')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })
})
