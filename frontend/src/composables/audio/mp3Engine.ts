import type {
  EndHandler,
  ErrorHandler,
  SentenceChangeHandler,
  TtsEngine,
} from './types'
import type { TtsErrorKind } from '@/stores/ttsPlayer'

export interface Mp3EngineOpts {
  url: string
  sentenceOffsetsSeconds: number[]
  durationSeconds: number
  sanitizedText: string
  sentenceOffsetsChars: number[]
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

export class Mp3Engine implements TtsEngine {
  readonly kind = 'mp3' as const
  readonly sentences: string[]
  readonly totalSentences: number
  readonly durationSeconds: number
  readonly audio: HTMLAudioElement
  private offsets: number[]
  private idx = 0
  private sentenceCb: SentenceChangeHandler | null = null
  private endCb: EndHandler | null = null
  private errorCb: ErrorHandler | null = null

  constructor(opts: Mp3EngineOpts) {
    this.sentences = sliceSentences(opts.sanitizedText, opts.sentenceOffsetsChars)
    this.totalSentences = this.sentences.length
    this.durationSeconds = opts.durationSeconds
    this.offsets = opts.sentenceOffsetsSeconds.length > 0 ? opts.sentenceOffsetsSeconds : [0]
    const audio = typeof Audio !== 'undefined' ? new Audio(opts.url) : ({
      currentTime: 0,
      play: () => Promise.resolve(),
      pause: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    } as unknown as HTMLAudioElement)
    this.audio = audio
    this.audio.preload = 'auto'
    this.audio.addEventListener('timeupdate', this.onTimeUpdate)
    this.audio.addEventListener('ended', this.onEnded)
    this.audio.addEventListener('error', this.onAudioError)
  }

  private onTimeUpdate = (): void => {
    const t = this.audio.currentTime
    let next = this.idx
    while (next + 1 < this.offsets.length && t >= this.offsets[next + 1]) {
      next += 1
    }
    if (next !== this.idx) {
      this.idx = next
      this.sentenceCb?.(this.idx)
    }
  }

  private onEnded = (): void => {
    this.endCb?.()
  }

  private onAudioError = (): void => {
    this.errorCb?.('mp3_fetch_failed')
  }

  async play(): Promise<void> {
    try {
      await this.audio.play()
    } catch {
      this.errorCb?.('mp3_fetch_failed')
    }
  }

  pause(): void {
    this.audio.pause()
  }

  nextSentence(): void {
    this.seek(Math.min(this.idx + 1, this.totalSentences - 1))
  }

  prevSentence(): void {
    this.seek(Math.max(this.idx - 1, 0))
  }

  seek(idx: number): void {
    if (idx < 0 || idx >= this.offsets.length) return
    this.idx = idx
    this.audio.currentTime = this.offsets[idx]
    this.sentenceCb?.(this.idx)
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
    this.audio.removeEventListener('timeupdate', this.onTimeUpdate)
    this.audio.removeEventListener('ended', this.onEnded)
    this.audio.removeEventListener('error', this.onAudioError)
    this.audio.pause()
  }

  _fakeTime(t: number): void {
    Object.defineProperty(this.audio, 'currentTime', { value: t, configurable: true, writable: true })
    this.onTimeUpdate()
  }

  _fakeEnd(): void {
    this.onEnded()
  }

  _fakeError(_kind?: TtsErrorKind): void {
    this.onAudioError()
  }
}
