import { afterEach, describe, expect, it, vi } from 'vitest'

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

afterEach(() => {
  vi.useRealTimers()
})

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

  it('startWatchdog fires onTimeout when audio.paused stays true at 1000ms', async () => {
    vi.useFakeTimers()
    const eng = makeEngine()
    Object.defineProperty(eng.audio, 'paused', { value: true, configurable: true })
    Object.defineProperty(eng.audio, 'ended', { value: false, configurable: true })
    const cb = vi.fn()
    eng.startWatchdog(1000, cb)
    await vi.advanceTimersByTimeAsync(1000)
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('watchdog cancelled when audio fires "playing" event', async () => {
    vi.useFakeTimers()
    const eng = makeEngine()
    const cb = vi.fn()
    eng.startWatchdog(1000, cb)
    eng.audio.dispatchEvent(new Event('playing'))
    await vi.advanceTimersByTimeAsync(2000)
    expect(cb).not.toHaveBeenCalled()
  })

  it('cancelWatchdog stops the timer', async () => {
    vi.useFakeTimers()
    const eng = makeEngine()
    const cb = vi.fn()
    eng.startWatchdog(1000, cb)
    eng.cancelWatchdog()
    await vi.advanceTimersByTimeAsync(2000)
    expect(cb).not.toHaveBeenCalled()
  })

  it('onWaitingForVoices is a no-op (registers but never invokes)', () => {
    const eng = makeEngine()
    const cb = vi.fn()
    eng.onWaitingForVoices(cb)
    // No assertion possible beyond "doesn't throw"; MP3 engine never waits on voices.
    expect(cb).not.toHaveBeenCalled()
  })

  it('play() is idempotent — second call while playing is a no-op', async () => {
    const eng = makeEngine()
    Object.defineProperty(eng.audio, 'paused', { value: true, configurable: true, writable: true })
    Object.defineProperty(eng.audio, 'ended', { value: false, configurable: true, writable: true })
    const playSpy = vi.spyOn(eng.audio, 'play').mockImplementation(async () => {
      Object.defineProperty(eng.audio, 'paused', { value: false, configurable: true, writable: true })
    })
    await eng.play()
    await eng.play()
    expect(playSpy).toHaveBeenCalledTimes(1)
  })
})
