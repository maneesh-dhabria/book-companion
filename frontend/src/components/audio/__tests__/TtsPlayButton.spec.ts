import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TtsPlayButton from '@/components/audio/TtsPlayButton.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('TtsPlayButton', () => {
  it('renders enabled when section has summary', () => {
    const wrap = mount(TtsPlayButton, {
      props: { contentType: 'section_summary', contentId: 42, hasSummary: true },
    })
    const btn = wrap.find('button')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('renders disabled with tooltip when no summary', () => {
    const wrap = mount(TtsPlayButton, {
      props: { contentType: 'section_summary', contentId: 42, hasSummary: false },
    })
    const btn = wrap.find('button')
    expect(btn.attributes('aria-disabled')).toBe('true')
    expect(btn.attributes('title')).toContain('Audio is only generated for summaries')
  })

  it('clicking calls store.open with the right content', async () => {
    const store = useTtsPlayerStore()
    const spy = vi.spyOn(store, 'open')
    const wrap = mount(TtsPlayButton, {
      props: { contentType: 'section_summary', contentId: 42, hasSummary: true },
    })
    await wrap.find('button').trigger('click')
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ contentType: 'section_summary', contentId: 42 }),
    )
  })
})
