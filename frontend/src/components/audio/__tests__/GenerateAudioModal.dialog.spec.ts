import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: { start: vi.fn() },
}))

import GenerateAudioModal from '@/components/audio/GenerateAudioModal.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('GenerateAudioModal — FR-14 dialog semantics + close affordances', () => {
  const baseProps = {
    open: true,
    bookId: 1,
    totalUnits: 17,
    totalAnnotations: 0,
  }

  it('exposes role=dialog with aria-modal and aria-labelledby pointing at the title', () => {
    const wrap = mount(GenerateAudioModal, { props: baseProps })
    const dlg = wrap.find('[role="dialog"]')
    expect(dlg.exists()).toBe(true)
    expect(dlg.attributes('aria-modal')).toBe('true')
    expect(dlg.attributes('aria-labelledby')).toBe('gen-audio-title')
    expect(wrap.find('#gen-audio-title').exists()).toBe(true)
  })

  it('renders close-X icon button with aria-label and emits close on click', async () => {
    const wrap = mount(GenerateAudioModal, { props: baseProps })
    const btn = wrap.find('button[aria-label="Close generate audio dialog"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    expect(wrap.emitted('close')).toBeTruthy()
    expect(wrap.emitted('close')).toHaveLength(1)
  })

  it('Esc keypress on the dialog emits close', async () => {
    const wrap = mount(GenerateAudioModal, { props: baseProps, attachTo: document.body })
    await wrap.find('[role="dialog"]').trigger('keydown', { key: 'Escape' })
    expect(wrap.emitted('close')).toBeTruthy()
    wrap.unmount()
  })
})
