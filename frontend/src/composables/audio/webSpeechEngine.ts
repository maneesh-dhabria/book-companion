import type {
  EndHandler,
  ErrorHandler,
  SentenceChangeHandler,
  TtsEngine,
} from './types'
import type { TtsErrorKind } from '@/stores/ttsPlayer'

export interface WebSpeechEngineOpts {
  sanitizedText: string
  sentenceOffsetsChars: number[]
  voice?: string
  rate?: number
}

function sliceSentences(text: string, offsets: number[]): string[] {
  if (offsets.length === 0) return [text]
  const result: string[] = []
  for (let i = 0; i < offsets.length; i++) {
    const start = offsets[i]
    const end = i + 1 < offsets.length ? offsets[i + 1] : text.length
    result.push(text.slice(start, end).trim())
  }
  return result
}

export class WebSpeechEngine implements TtsEngine {
  readonly kind = 'web-speech' as const
  readonly sentences: string[]
  readonly totalSentences: number
  readonly durationSeconds = 0
  private idx = 0
  private rate: number
  private voiceName?: string
  private currentUtterance: SpeechSynthesisUtterance | null = null
  private sentenceCb: SentenceChangeHandler | null = null
  private errorCb: ErrorHandler | null = null
  private endCb: EndHandler | null = null
  private terminated = false

  constructor(opts: WebSpeechEngineOpts) {
    this.sentences = sliceSentences(opts.sanitizedText, opts.sentenceOffsetsChars)
    this.totalSentences = this.sentences.length
    this.rate = opts.rate ?? 1.0
    this.voiceName = opts.voice
  }

  private getSynth(): SpeechSynthesis | null {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null
    return window.speechSynthesis
  }

  private speakAt(idx: number): void {
    const synth = this.getSynth()
    if (!synth) {
      this.emitError('engine_unavailable')
      return
    }
    const voices = synth.getVoices()
    if (!voices || voices.length === 0) {
      this.emitError('engine_unavailable')
      return
    }
    const text = this.sentences[idx]
    if (!text) {
      this.endCb?.()
      return
    }
    const utt = new SpeechSynthesisUtterance(text)
    utt.rate = this.rate
    if (this.voiceName) {
      const v = voices.find((vc) => vc.name === this.voiceName)
      if (v) utt.voice = v
    }
    utt.onend = () => {
      if (this.terminated) return
      const next = this.idx + 1
      if (next >= this.totalSentences) {
        this.endCb?.()
        return
      }
      this.idx = next
      this.sentenceCb?.(this.idx)
      this.speakAt(this.idx)
    }
    utt.onerror = () => this.emitError('utterance_failed')
    this.currentUtterance = utt
    synth.speak(utt)
  }

  private emitError(kind: TtsErrorKind): void {
    this.errorCb?.(kind)
  }

  async play(): Promise<void> {
    const synth = this.getSynth()
    if (!synth) {
      this.emitError('engine_unavailable')
      return
    }
    if (synth.paused) {
      synth.resume()
      return
    }
    this.sentenceCb?.(this.idx)
    this.speakAt(this.idx)
  }

  pause(): void {
    this.getSynth()?.pause()
  }

  nextSentence(): void {
    if (this.idx + 1 >= this.totalSentences) return
    this.idx += 1
    this.getSynth()?.cancel()
    this.sentenceCb?.(this.idx)
    this.speakAt(this.idx)
  }

  prevSentence(): void {
    if (this.idx === 0) return
    this.idx -= 1
    this.getSynth()?.cancel()
    this.sentenceCb?.(this.idx)
    this.speakAt(this.idx)
  }

  seek(idx: number): void {
    if (idx < 0 || idx >= this.totalSentences) return
    this.idx = idx
    this.getSynth()?.cancel()
    this.sentenceCb?.(this.idx)
    this.speakAt(this.idx)
  }

  onSentenceChange(cb: SentenceChangeHandler): void {
    this.sentenceCb = cb
  }

  onEnd(cb: EndHandler): void {
    this.endCb = cb
  }

  onError(cb: ErrorHandler): void {
    this.errorCb = cb
  }

  terminate(): void {
    this.terminated = true
    this.getSynth()?.cancel()
    this.currentUtterance = null
  }

  _fakeError(kind: TtsErrorKind): void {
    this.emitError(kind)
  }
}
