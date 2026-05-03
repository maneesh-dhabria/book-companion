import { describe, expect, it, vi } from 'vitest'

import { Mp3Engine } from '@/composables/audio/mp3Engine'

function makeEngine() {
  return new Mp3Engine({
    url: '/api/v1/books/1/audio/section_summary/42.mp3',
    sentenceOffsetsSeconds: [0, 4.2, 9.7],
    durationSeconds: 12,
    sanitizedText: 'First. Second. Third.',
    sentenceOffsetsChars: [0, 7, 15],
  })
}

describe('Mp3Engine', () => {
  it('slices text by offsets', () => {
    const eng = makeEngine()
    expect(eng.sentences).toEqual(['First.', 'Second.', 'Third.'])
    expect(eng.totalSentences).toBe(3)
  })

  it('advances sentence on timeupdate crossing offset', () => {
    const eng = makeEngine()
    const onSentence = vi.fn()
    eng.onSentenceChange(onSentence)
    eng._fakeTime(5.0)
    expect(onSentence).toHaveBeenLastCalledWith(1)
    eng._fakeTime(10.0)
    expect(onSentence).toHaveBeenLastCalledWith(2)
  })

  it('emits onEnd when audio ends', () => {
    const eng = makeEngine()
    const onEnd = vi.fn()
    eng.onEnd(onEnd)
    eng._fakeEnd()
    expect(onEnd).toHaveBeenCalled()
  })

  it('seek(idx) sets currentTime to offset and emits highlight', () => {
    const eng = makeEngine()
    const onSentence = vi.fn()
    eng.onSentenceChange(onSentence)
    eng.seek(2)
    expect(eng.audio.currentTime).toBe(9.7)
    expect(onSentence).toHaveBeenLastCalledWith(2)
  })

  it('emits mp3_fetch_failed on audio error', () => {
    const eng = makeEngine()
    const errSpy = vi.fn()
    eng.onError(errSpy)
    eng._fakeError()
    expect(errSpy).toHaveBeenCalledWith('mp3_fetch_failed')
  })
})
