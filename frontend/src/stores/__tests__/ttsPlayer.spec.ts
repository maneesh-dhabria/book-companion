import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useTtsPlayerStore } from '@/stores/ttsPlayer'

describe('ttsPlayerStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts idle', () => {
    const s = useTtsPlayerStore()
    expect(s.status).toBe('idle')
    expect(s.isActive).toBe(false)
  })

  it('open(content) transitions to loading and sets isActive', () => {
    const s = useTtsPlayerStore()
    s.open({ contentType: 'section_summary', contentId: 42 })
    expect(s.status).toBe('loading')
    expect(s.isActive).toBe(true)
    expect(s.contentType).toBe('section_summary')
    expect(s.contentId).toBe(42)
  })

  it('setError moves to error with errorKind', () => {
    const s = useTtsPlayerStore()
    s.open({ contentType: 'section_summary', contentId: 42 })
    s.setError('mp3_fetch_failed')
    expect(s.status).toBe('error')
    expect(s.errorKind).toBe('mp3_fetch_failed')
  })

  it('retry resets error and re-opens at sentenceIndex', () => {
    const s = useTtsPlayerStore()
    s.open({ contentType: 'section_summary', contentId: 42 })
    s.sentenceIndex = 5
    s.setError('utterance_failed')
    s.retry()
    expect(s.errorKind).toBe(null)
    expect(s.status).toBe('loading')
    expect(s.contentId).toBe(42)
    expect(s.sentenceIndex).toBe(5)
  })

  it('close resets to idle', () => {
    const s = useTtsPlayerStore()
    s.open({ contentType: 'section_summary', contentId: 42 })
    s.close()
    expect(s.status).toBe('idle')
    expect(s.isActive).toBe(false)
    expect(s.contentId).toBe(null)
  })

  it('play / pause transitions status', () => {
    const s = useTtsPlayerStore()
    s.open({ contentType: 'section_summary', contentId: 1 })
    s.play()
    expect(s.status).toBe('playing')
    s.pause()
    expect(s.status).toBe('paused')
  })

  it('nextSentence / prevSentence clamp to totalSentences', () => {
    const s = useTtsPlayerStore()
    s.open({ contentType: 'section_summary', contentId: 1 })
    s.totalSentences = 3
    s.sentenceIndex = 0
    s.nextSentence()
    expect(s.sentenceIndex).toBe(1)
    s.sentenceIndex = 2
    s.nextSentence()
    expect(s.sentenceIndex).toBe(2)
    s.prevSentence()
    expect(s.sentenceIndex).toBe(1)
    s.sentenceIndex = 0
    s.prevSentence()
    expect(s.sentenceIndex).toBe(0)
  })
})
