import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const playSpy = vi.fn(async () => undefined)
const pauseSpy = vi.fn()
const nextSpy = vi.fn()
const prevSpy = vi.fn()
const seekSpy = vi.fn()
const terminateSpy = vi.fn()
const loadSpy = vi.fn(async () => ({ kind: 'web-speech' as const }))

vi.mock('@/composables/audio/useTtsEngine', () => ({
  useTtsEngine: () => ({
    load: loadSpy,
    terminate: terminateSpy,
    playActive: playSpy,
    pauseActive: pauseSpy,
    nextActive: nextSpy,
    prevActive: prevSpy,
    seekActive: seekSpy,
  }),
}))

import { useTtsPlayerStore } from '@/stores/ttsPlayer'

describe('ttsPlayerStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts idle', () => {
    const s = useTtsPlayerStore()
    expect(s.status).toBe('idle')
    expect(s.isActive).toBe(false)
  })

  it('open(content) transitions to loading and sets isActive', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 42 })
    expect(s.status).toBe('loading')
    expect(s.isActive).toBe(true)
    expect(s.contentType).toBe('section_summary')
    expect(s.contentId).toBe(42)
  })

  it('open() captures bookId in store', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 7, contentType: 'section_summary', contentId: 1 })
    expect(s.bookId).toBe(7)
  })

  it('setError moves to error with errorKind', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 42 })
    s.setError('mp3_fetch_failed')
    expect(s.status).toBe('error')
    expect(s.errorKind).toBe('mp3_fetch_failed')
  })

  it('retry re-invokes useTtsEngine.load with captured bookId/type/id', async () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 7, contentType: 'section_summary', contentId: 42 })
    s.sentenceIndex = 5
    s.setError('utterance_failed')
    await s.retry()
    expect(loadSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        bookId: 7,
        contentType: 'section_summary',
        contentId: 42,
      }),
    )
    expect(s.contentId).toBe(42)
    expect(s.sentenceIndex).toBe(5)
  })

  it('close calls useTtsEngine.terminate and resets to idle', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 42 })
    s.close()
    expect(terminateSpy).toHaveBeenCalledTimes(1)
    expect(s.status).toBe('idle')
    expect(s.isActive).toBe(false)
    expect(s.contentId).toBe(null)
    expect(s.bookId).toBe(null)
  })

  it('play() calls useTtsEngine.playActive', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    s.play()
    expect(playSpy).toHaveBeenCalledTimes(1)
    expect(s.status).toBe('playing')
  })

  it('pause() calls useTtsEngine.pauseActive', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    s.pause()
    expect(pauseSpy).toHaveBeenCalledTimes(1)
    expect(s.status).toBe('paused')
  })

  it('nextSentence() calls nextActive without pre-updating sentenceIndex', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    s.sentenceIndex = 5
    s.nextSentence()
    expect(nextSpy).toHaveBeenCalledTimes(1)
    expect(s.sentenceIndex).toBe(5)
  })

  it('prevSentence() calls prevActive', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    s.prevSentence()
    expect(prevSpy).toHaveBeenCalledTimes(1)
  })

  it('seek(idx) calls seekActive', () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    s.seek(3)
    expect(seekSpy).toHaveBeenCalledWith(3)
  })

  it('isPlaying is false during starting status', () => {
    const s = useTtsPlayerStore()
    s.status = 'starting'
    expect(s.isPlaying).toBe(false)
  })
})
