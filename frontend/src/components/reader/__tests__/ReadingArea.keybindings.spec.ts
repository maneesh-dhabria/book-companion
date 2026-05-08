import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const nextSpy = vi.fn()
const prevSpy = vi.fn()

vi.mock('@/composables/audio/useTtsEngine', () => ({
  useTtsEngine: () => ({
    load: vi.fn().mockResolvedValue({ kind: 'web-speech' }),
    terminate: vi.fn(),
    playActive: vi.fn(async () => undefined),
    pauseActive: vi.fn(),
    nextActive: nextSpy,
    prevActive: prevSpy,
    seekActive: vi.fn(),
  }),
}))

import ReadingArea from '@/components/reader/ReadingArea.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

function dispatch(key: string) {
  const ev = new KeyboardEvent('keydown', { key, cancelable: true })
  document.dispatchEvent(ev)
  return ev
}

describe('ReadingArea keybindings', () => {
  it('ArrowLeft delegates to engine.prevSentence when player active', () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.totalSentences = 10
    store.sentenceIndex = 5
    mount(ReadingArea, {
      props: { content: 'x', hasPrev: true, hasNext: true },
    })
    dispatch('ArrowLeft')
    expect(prevSpy).toHaveBeenCalled()
  })

  it('ArrowRight delegates to engine.nextSentence when player active', () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.totalSentences = 10
    store.sentenceIndex = 2
    mount(ReadingArea, {
      props: { content: 'x', hasPrev: true, hasNext: true },
    })
    dispatch('ArrowRight')
    expect(nextSpy).toHaveBeenCalled()
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

  it('Space is NOT handled by ReadingArea (T10 / FR-14b — AppShell owns it globally)', () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.status = 'paused'
    mount(ReadingArea, {
      props: { content: 'x', hasPrev: true, hasNext: true },
    })
    dispatch(' ')
    // ReadingArea does not toggle anymore; status stays 'paused'.
    expect(store.status).toBe('paused')
  })
})
