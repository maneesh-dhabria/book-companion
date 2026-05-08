import { titleForContentType } from './mediaSessionTitles'
import type {
  EndHandler,
  ErrorHandler,
  SentenceChangeHandler,
  TtsEngine,
  WaitingForVoicesHandler,
} from './types'
import type { TtsErrorKind } from '@/stores/ttsPlayer'

export interface WebSpeechEngineOpts {
  sanitizedText: string
  sentenceOffsetsChars: number[]
  voice?: string
  rate?: number
  /** Used by T18 for navigator.mediaSession metadata. Optional today. */
  contentType?: string
  /** Used by T18 for mediaSession.artist. Optional today. */
  bookTitle?: string
}

const VOICE_WAIT_MS = 1500
const WATCHDOG_MS = 1000

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
  private waitingCb: WaitingForVoicesHandler | null = null
  private terminated = false
  private isSpeaking = false
  private errorEmitted = false
  private watchdogTimer: ReturnType<typeof setTimeout> | null = null
  private voiceWaitCleanup: (() => void) | null = null
  private contentType?: string
  private bookTitle?: string
  private mediaSessionApplied = false

  constructor(opts: WebSpeechEngineOpts) {
    this.sentences = sliceSentences(opts.sanitizedText, opts.sentenceOffsetsChars)
    this.totalSentences = this.sentences.length
    this.rate = opts.rate ?? 1.0
    this.voiceName = opts.voice
    this.contentType = opts.contentType
    this.bookTitle = opts.bookTitle
  }

  private applyMediaSession(): void {
    if (this.mediaSessionApplied) return
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
    if (typeof MediaMetadata === 'undefined') return
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: titleForContentType(this.contentType),
        artist: this.bookTitle ?? '',
        album: 'Book Companion',
      })
      this.mediaSessionApplied = true
    } catch {
      /* ignore */
    }
  }

  private getSynth(): SpeechSynthesis | null {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null
    return window.speechSynthesis
  }

  startWatchdog(timeoutMs: number, onTimeout: () => void): void {
    this.cancelWatchdog()
    this.watchdogTimer = setTimeout(() => {
      this.watchdogTimer = null
      const synth = this.getSynth()
      const speaking = !!synth?.speaking
      const pending = !!synth?.pending
      if (!speaking && !pending) {
        onTimeout()
      }
    }, timeoutMs)
  }

  cancelWatchdog(): void {
    if (this.watchdogTimer !== null) {
      clearTimeout(this.watchdogTimer)
      this.watchdogTimer = null
    }
  }

  onWaitingForVoices(cb: WaitingForVoicesHandler): void {
    this.waitingCb = cb
  }

  private clearVoiceWait(): void {
    if (this.voiceWaitCleanup) {
      const cleanup = this.voiceWaitCleanup
      this.voiceWaitCleanup = null
      cleanup()
    }
  }

  private speakAt(idx: number): void {
    if (this.terminated) return
    const synth = this.getSynth()
    if (!synth) {
      this.emitError('engine_unavailable')
      return
    }
    const text = this.sentences[idx]
    if (!text) {
      this.endCb?.()
      return
    }
    const voices = synth.getVoices()
    if (!voices || voices.length === 0) {
      // Voices not loaded yet; wait for voiceschanged or timeout.
      if (this.voiceWaitCleanup) return // already waiting
      this.waitingCb?.(true)
      const listener = () => {
        this.clearVoiceWait()
        this.speakAt(idx)
      }
      const timer = setTimeout(() => {
        this.clearVoiceWait()
        this.emitError('engine_unavailable')
      }, VOICE_WAIT_MS)
      this.voiceWaitCleanup = () => {
        try {
          synth.removeEventListener('voiceschanged', listener)
        } catch {
          /* ignore */
        }
        clearTimeout(timer)
        this.waitingCb?.(false)
      }
      try {
        synth.addEventListener('voiceschanged', listener, { once: true })
      } catch {
        // Some test stubs / older browsers may not support addEventListener;
        // fall through to timeout.
      }
      return
    }
    const utt = new SpeechSynthesisUtterance(text)
    utt.rate = this.rate
    if (this.voiceName) {
      const v = voices.find((vc) => vc.name === this.voiceName)
      if (v) utt.voice = v
    }
    utt.onstart = () => {
      this.cancelWatchdog()
      if (this.errorEmitted) {
        // A timeout already fired; cancel the late-arriving audio.
        try {
          synth.cancel()
        } catch {
          /* ignore */
        }
        return
      }
      this.isSpeaking = true
    }
    utt.onend = () => {
      this.isSpeaking = false
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
    utt.onerror = () => {
      this.isSpeaking = false
      this.emitError('utterance_failed')
    }
    this.currentUtterance = utt
    this.startWatchdog(WATCHDOG_MS, () => this.emitError('engine_unavailable'))
    synth.speak(utt)
  }

  private emitError(kind: TtsErrorKind): void {
    this.errorEmitted = true
    this.errorCb?.(kind)
  }

  async play(): Promise<void> {
    const synth = this.getSynth()
    if (!synth) {
      this.emitError('engine_unavailable')
      return
    }
    if (this.isSpeaking) {
      // Already mid-utterance: resume if paused, otherwise no-op.
      if (synth.paused) synth.resume()
      return
    }
    this.applyMediaSession()
    if (synth.paused) {
      synth.resume()
      return
    }
    this.sentenceCb?.(this.idx)
    this.speakAt(this.idx)
  }

  pause(): void {
    this.cancelWatchdog()
    this.clearVoiceWait()
    this.getSynth()?.pause()
  }

  nextSentence(): void {
    if (this.idx + 1 >= this.totalSentences) return
    this.cancelWatchdog()
    this.clearVoiceWait()
    this.idx += 1
    this.isSpeaking = false
    this.getSynth()?.cancel()
    this.sentenceCb?.(this.idx)
    this.speakAt(this.idx)
  }

  prevSentence(): void {
    if (this.idx === 0) return
    this.cancelWatchdog()
    this.clearVoiceWait()
    this.idx -= 1
    this.isSpeaking = false
    this.getSynth()?.cancel()
    this.sentenceCb?.(this.idx)
    this.speakAt(this.idx)
  }

  seek(idx: number): void {
    if (idx < 0 || idx >= this.totalSentences) return
    this.cancelWatchdog()
    this.clearVoiceWait()
    this.idx = idx
    this.isSpeaking = false
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
    this.cancelWatchdog()
    this.clearVoiceWait()
    this.isSpeaking = false
    this.getSynth()?.cancel()
    this.currentUtterance = null
  }

  _fakeError(kind: TtsErrorKind): void {
    this.emitError(kind)
  }
}
