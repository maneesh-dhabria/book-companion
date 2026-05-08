import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'

import DifferencePopover from '@/components/audio/DifferencePopover.vue'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/settings/:section?', component: { template: '<div/>' } },
    ],
  })
}

describe('DifferencePopover', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('does not render when open=false', () => {
    const wrap = mount(DifferencePopover, {
      props: { open: false },
      global: { plugins: [makeRouter()] },
    })
    expect(wrap.find('[data-testid="difference-popover"]').exists()).toBe(false)
  })

  it('renders dialog content + settings link when open=true', async () => {
    const wrap = mount(DifferencePopover, {
      props: { open: true },
      global: { plugins: [makeRouter()] },
    })
    await flushPromises()
    const root = wrap.find('[data-testid="difference-popover"]')
    expect(root.exists()).toBe(true)
    expect(root.attributes('role')).toBe('dialog')
    expect(root.text()).toContain('Kokoro')
    expect(root.text()).toContain('Web Speech')
    const link = wrap.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/settings/tts#audio')
  })

  it('emits close on Escape', async () => {
    const wrap = mount(DifferencePopover, {
      props: { open: true },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrap.emitted('close')).toBeTruthy()
    wrap.unmount()
  })
})
