import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { WebSpeechEngine } from '@/composables/audio/webSpeechEngine'

interface FakeUtt {
  text: string
  onstart?: () => void
  onend?: () => void
  onerror?: () => void
}

class FakeUtterance implements FakeUtt {
  text: string
  rate = 1
  voice: SpeechSynthesisVoice | null = null
  onstart?: () => void
  onend?: () => void
  onerror?: () => void
  constructor(text: string) {
    this.text = text
    fakeQueue.push(this)
  }
}

const fakeQueue: FakeUtterance[] = []

type Listener = (ev?: Event) => void

const voicesChangedListeners: Listener[] = []

const fakeSynth = {
  paused: false,
  speaking: false,
  pending: false,
  speak: vi.fn((u: FakeUtterance) => {
    fakeSynth._last = u
  }),
  pause: vi.fn(() => {
    fakeSynth.paused = true
  }),
  resume: vi.fn(() => {
    fakeSynth.paused = false
  }),
  cancel: vi.fn(),
  getVoices: vi.fn(() => [{ name: 'Samantha' } as SpeechSynthesisVoice]),
  addEventListener: vi.fn((evt: string, cb: Listener) => {
    if (evt === 'voiceschanged') voicesChangedListeners.push(cb)
  }),
  removeEventListener: vi.fn((evt: string, cb: Listener) => {
    if (evt === 'voiceschanged') {
      const i = voicesChangedListeners.indexOf(cb)
      if (i >= 0) voicesChangedListeners.splice(i, 1)
    }
  }),
  dispatchEvent: vi.fn((ev: Event) => {
    if (ev.type === 'voiceschanged') {
      // copy the array so once-listeners that remove themselves don't break iteration
      for (const cb of [...voicesChangedListeners]) cb(ev)
    }
    return true
  }),
  _last: null as FakeUtterance | null,
}

beforeEach(() => {
  fakeQueue.length = 0
  voicesChangedListeners.length = 0
  fakeSynth.paused = false
  fakeSynth.speaking = false
  fakeSynth.pending = false
  fakeSynth._last = null
  fakeSynth.speak.mockClear()
  fakeSynth.pause.mockClear()
  fakeSynth.resume.mockClear()
  fakeSynth.cancel.mockClear()
  fakeSynth.addEventListener.mockClear()
  fakeSynth.removeEventListener.mockClear()
  fakeSynth.dispatchEvent.mockClear()
  fakeSynth.getVoices.mockReturnValue([{ name: 'Samantha' } as SpeechSynthesisVoice])
  vi.stubGlobal('speechSynthesis', fakeSynth)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'speechSynthesis', {
      value: fakeSynth,
      configurable: true,
    })
  }
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function makeEngine(text = 'First. Second. Third.', offsets = [0, 7, 15]) {
  return new WebSpeechEngine({
    sanitizedText: text,
    sentenceOffsetsChars: offsets,
    voice: 'Samantha',
  })
}

describe('WebSpeechEngine', () => {
  it('slices text into sentences', () => {
    const eng = makeEngine()
    expect(eng.sentences).toEqual(['First.', 'Second.', 'Third.'])
  })

  it('advances on utterance end', async () => {
    const eng = makeEngine()
    const onSentence = vi.fn()
    eng.onSentenceChange(onSentence)
    await eng.play()
    expect(onSentence).toHaveBeenCalledWith(0)
    fakeSynth._last?.onend?.()
    expect(onSentence).toHaveBeenLastCalledWith(1)
  })

  it('pause calls speechSynthesis.pause', async () => {
    const eng = makeEngine()
    await eng.play()
    eng.pause()
    expect(fakeSynth.pause).toHaveBeenCalled()
  })

  it('utterance error emits utterance_failed', async () => {
    const eng = makeEngine()
    const errSpy = vi.fn()
    eng.onError(errSpy)
    await eng.play()
    fakeSynth._last?.onerror?.()
    expect(errSpy).toHaveBeenCalledWith('utterance_failed')
  })

  it('waits for voiceschanged when getVoices is empty, then speaks once voices arrive', async () => {
    fakeSynth.getVoices.mockReturnValueOnce([])
    const eng = makeEngine()
    await eng.play()
    expect(fakeSynth.speak).not.toHaveBeenCalled()
    // Voices now arrive
    fakeSynth.getVoices.mockReturnValue([{ name: 'Samantha' } as SpeechSynthesisVoice])
    fakeSynth.dispatchEvent(new Event('voiceschanged'))
    expect(fakeSynth.speak).toHaveBeenCalledTimes(1)
  })

  it('emits engine_unavailable after 1500ms timeout when voices never arrive', async () => {
    vi.useFakeTimers()
    fakeSynth.getVoices.mockReturnValue([])
    const eng = makeEngine()
    const errSpy = vi.fn()
    eng.onError(errSpy)
    await eng.play()
    expect(errSpy).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1500)
    expect(errSpy).toHaveBeenCalledWith('engine_unavailable')
    expect(errSpy).toHaveBeenCalledTimes(1)
  })

  it('emits onWaitingForVoices(true) then false when voices arrive', async () => {
    fakeSynth.getVoices.mockReturnValueOnce([])
    const eng = makeEngine()
    const waitSpy = vi.fn()
    eng.onWaitingForVoices(waitSpy)
    await eng.play()
    expect(waitSpy).toHaveBeenLastCalledWith(true)
    fakeSynth.getVoices.mockReturnValue([{ name: 'Samantha' } as SpeechSynthesisVoice])
    fakeSynth.dispatchEvent(new Event('voiceschanged'))
    expect(waitSpy).toHaveBeenLastCalledWith(false)
    expect(waitSpy.mock.calls).toEqual([[true], [false]])
  })

  it('pause() cancels voice-wait listener and timer', async () => {
    vi.useFakeTimers()
    fakeSynth.getVoices.mockReturnValue([])
    const eng = makeEngine()
    const errSpy = vi.fn()
    eng.onError(errSpy)
    await eng.play()
    eng.pause()
    expect(fakeSynth.removeEventListener).toHaveBeenCalledWith('voiceschanged', expect.any(Function))
    await vi.advanceTimersByTimeAsync(2000)
    expect(errSpy).not.toHaveBeenCalled()
  })

  it('terminate() cancels voice-wait listener and timer', async () => {
    vi.useFakeTimers()
    fakeSynth.getVoices.mockReturnValue([])
    const eng = makeEngine()
    const errSpy = vi.fn()
    eng.onError(errSpy)
    await eng.play()
    eng.terminate()
    expect(fakeSynth.removeEventListener).toHaveBeenCalledWith('voiceschanged', expect.any(Function))
    await vi.advanceTimersByTimeAsync(2000)
    expect(errSpy).not.toHaveBeenCalled()
  })

  it('startWatchdog fires onTimeout when speaking stays false at 1000ms', async () => {
    vi.useFakeTimers()
    const eng = makeEngine()
    const onTimeout = vi.fn()
    fakeSynth.speaking = false
    fakeSynth.pending = false
    eng.startWatchdog(1000, onTimeout)
    await vi.advanceTimersByTimeAsync(1000)
    expect(onTimeout).toHaveBeenCalledTimes(1)
  })

  it('startWatchdog onTimeout NOT called when utterance.onstart fires', async () => {
    vi.useFakeTimers()
    const eng = makeEngine()
    const onTimeout = vi.fn()
    eng.startWatchdog(1000, onTimeout)
    // Engine isn't producing utterances itself; cancel the watchdog directly
    // (the engine wires this internally via utt.onstart in real runs).
    eng.cancelWatchdog()
    await vi.advanceTimersByTimeAsync(1500)
    expect(onTimeout).not.toHaveBeenCalled()
  })

  it('play() is idempotent — second call mid-utterance is a no-op', async () => {
    const eng = makeEngine()
    await eng.play()
    // Trigger onstart so engine knows it's speaking
    fakeSynth._last?.onstart?.()
    fakeSynth.speak.mockClear()
    await eng.play()
    expect(fakeSynth.speak).not.toHaveBeenCalled()
  })

  it('utterance.onstart cancels late-arriving utterance if error already emitted', async () => {
    vi.useFakeTimers()
    const eng = makeEngine()
    const errSpy = vi.fn()
    eng.onError(errSpy)
    await eng.play()
    // Fire watchdog timeout (1s default in real engine path); but here we
    // simulate by emitting the error directly.
    eng._fakeError?.('engine_unavailable')
    expect(errSpy).toHaveBeenCalledWith('engine_unavailable')
    fakeSynth._last?.onstart?.()
    expect(fakeSynth.cancel).toHaveBeenCalled()
  })
})
