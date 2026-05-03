import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Playbar from '@/components/audio/Playbar.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('Playbar', () => {
  it('does not render when store is idle', () => {
    const wrap = mount(Playbar)
    expect(wrap.find('.bc-playbar').exists()).toBe(false)
  })

  it('renders when store.isActive', async () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    const wrap = mount(Playbar)
    expect(wrap.find('.bc-playbar').exists()).toBe(true)
  })

  it('shows sentence index and elapsed/total', async () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.engine = 'mp3'
    store.voice = 'af_sarah'
    store.totalSentences = 47
    store.sentenceIndex = 16
    store.sentenceOffsets = Array.from({ length: 48 }, (_, i) => (i * 368) / 47)
    const wrap = mount(Playbar)
    expect(wrap.text()).toContain('sentence 17 of 47')
    expect(wrap.text()).toMatch(/\d+:\d{2} \/ \d+:\d{2}/)
  })

  it('shows Limited controls pill when engine=web-speech', () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.engine = 'web-speech'
    const wrap = mount(Playbar)
    expect(wrap.find('[data-testid="limited-controls"]').exists()).toBe(true)
  })

  it('renders Retry on status=error and calls store.retry', async () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.setError('mp3_fetch_failed')
    const wrap = mount(Playbar)
    const retry = wrap.find('button[data-testid="retry"]')
    expect(retry.exists()).toBe(true)
    const spy = vi.spyOn(store, 'retry')
    await retry.trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('clicking play/pause toggles store.status', async () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.status = 'paused'
    const wrap = mount(Playbar)
    const btn = wrap.find('[data-testid="play-pause"]')
    await btn.trigger('click')
    expect(store.status).toBe('playing')
    await btn.trigger('click')
    expect(store.status).toBe('paused')
  })
})
