import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ReadingArea from '@/components/reader/ReadingArea.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
})

function dispatch(key: string) {
  const ev = new KeyboardEvent('keydown', { key, cancelable: true })
  document.dispatchEvent(ev)
  return ev
}

describe('ReadingArea keybindings', () => {
  it('ArrowLeft skips sentence when player active', () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.totalSentences = 10
    store.sentenceIndex = 5
    mount(ReadingArea, {
      props: { content: 'x', hasPrev: true, hasNext: true },
    })
    dispatch('ArrowLeft')
    expect(store.sentenceIndex).toBe(4)
  })

  it('ArrowRight skips forward when player active', () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.totalSentences = 10
    store.sentenceIndex = 2
    mount(ReadingArea, {
      props: { content: 'x', hasPrev: true, hasNext: true },
    })
    dispatch('ArrowRight')
    expect(store.sentenceIndex).toBe(3)
  })

  it('ArrowLeft navigates section when player inactive', () => {
    const wrap = mount(ReadingArea, {
      props: { content: 'x', hasPrev: true, hasNext: true },
    })
    dispatch('ArrowLeft')
    const events = wrap.emitted('navigate') ?? []
    expect(events.length).toBeGreaterThan(0)
    expect(events[0]).toEqual(['prev'])
  })

  it('Space toggles play/pause when player active', () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.status = 'paused'
    mount(ReadingArea, {
      props: { content: 'x', hasPrev: true, hasNext: true },
    })
    dispatch(' ')
    expect(store.status).toBe('playing')
    dispatch(' ')
    expect(store.status).toBe('paused')
  })
})
