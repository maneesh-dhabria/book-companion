import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { WebSpeechEngine } from '@/composables/audio/webSpeechEngine'

interface FakeUtt {
  text: string
  onend?: () => void
  onerror?: () => void
}

class FakeUtterance implements FakeUtt {
  text: string
  rate = 1
  voice: SpeechSynthesisVoice | null = null
  onend?: () => void
  onerror?: () => void
  constructor(text: string) {
    this.text = text
    fakeQueue.push(this)
  }
}

const fakeQueue: FakeUtterance[] = []

const fakeSynth = {
  paused: false,
  speak: vi.fn((u: FakeUtterance) => {
    // Defer end callback: tests trigger manually.
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
  _last: null as FakeUtterance | null,
}

beforeEach(() => {
  fakeQueue.length = 0
  fakeSynth.paused = false
  fakeSynth._last = null
  fakeSynth.speak.mockClear()
  fakeSynth.pause.mockClear()
  fakeSynth.cancel.mockClear()
  fakeSynth.getVoices.mockReturnValue([{ name: 'Samantha' } as SpeechSynthesisVoice])
  vi.stubGlobal('speechSynthesis', fakeSynth)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  // jsdom window
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'speechSynthesis', {
      value: fakeSynth,
      configurable: true,
    })
  }
})

afterEach(() => {
  vi.unstubAllGlobals()
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

  it('emits engine_unavailable when getVoices returns empty', async () => {
    fakeSynth.getVoices.mockReturnValueOnce([])
    const eng = makeEngine()
    const errSpy = vi.fn()
    eng.onError(errSpy)
    await eng.play()
    expect(errSpy).toHaveBeenCalledWith('engine_unavailable')
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
})
