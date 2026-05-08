import { titleForContentType } from './mediaSessionTitles'
import type {
  EndHandler,
  ErrorHandler,
  SentenceChangeHandler,
  TtsEngine,
  WaitingForVoicesHandler,
} from './types'
import type { TtsErrorKind } from '@/stores/ttsPlayer'

export interface MediaChapter {
  title: string
  startTime: number
}

export interface MediaInfo {
  title?: string
  artist?: string
  album?: string
  artwork?: { src: string; sizes?: string; type?: string }[]
  chapterInfo?: MediaChapter[]
}

export interface Mp3EngineOpts {
  url: string
  sentenceOffsetsSeconds: number[]
  durationSeconds: number
  sanitizedText: string
  sentenceOffsetsChars: number[]
  media?: MediaInfo
  /** Used by T18 for navigator.mediaSession metadata title. Optional today. */
  contentType?: string
  /** Used by T18 for mediaSession.artist. Optional today. */
  bookTitle?: string
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
  private media?: MediaInfo
  private contentType?: string
  private bookTitle?: string
  private watchdogTimer: ReturnType<typeof setTimeout> | null = null
  private watchdogPlayingHandler: (() => void) | null = null
  private errorEmitted = false

  constructor(opts: Mp3EngineOpts) {
    this.media = opts.media
    this.contentType = opts.contentType
    this.bookTitle = opts.bookTitle
    this.sentences = sliceSentences(opts.sanitizedText, opts.sentenceOffsetsChars)
    this.totalSentences = this.sentences.length
    this.durationSeconds = opts.durationSeconds
    this.offsets = opts.sentenceOffsetsSeconds.length > 0 ? opts.sentenceOffsetsSeconds : [0]
    const audio = typeof Audio !== 'undefined' ? new Audio(opts.url) : ({
      currentTime: 0,
      paused: true,
      ended: false,
      play: () => Promise.resolve(),
      pause: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => true,
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
    this.errorEmitted = true
    this.errorCb?.('mp3_fetch_failed')
  }

  startWatchdog(timeoutMs: number, onTimeout: () => void): void {
    this.cancelWatchdog()
    const playingHandler = () => {
      this.cancelWatchdog()
    }
    this.watchdogPlayingHandler = playingHandler
    try {
      this.audio.addEventListener('playing', playingHandler, { once: true })
    } catch {
      /* ignore */
    }
    this.watchdogTimer = setTimeout(() => {
      this.watchdogTimer = null
      if (this.errorEmitted) return
      if (this.audio.paused && !this.audio.ended) {
        onTimeout()
      }
    }, timeoutMs)
  }

  cancelWatchdog(): void {
    if (this.watchdogTimer !== null) {
      clearTimeout(this.watchdogTimer)
      this.watchdogTimer = null
    }
    if (this.watchdogPlayingHandler) {
      try {
        this.audio.removeEventListener('playing', this.watchdogPlayingHandler)
      } catch {
        /* ignore */
      }
      this.watchdogPlayingHandler = null
    }
  }

  onWaitingForVoices(_cb: WaitingForVoicesHandler): void {
    // MP3 engine never waits on voices; no-op by design.
    void _cb
  }

  async play(): Promise<void> {
    // Idempotent: if already playing, no-op.
    if (!this.audio.paused && !this.audio.ended) return
    try {
      this.startWatchdog(1000, () => this.errorCb?.('engine_unavailable'))
      await this.audio.play()
      this.applyMediaSession()
    } catch {
      this.cancelWatchdog()
      this.errorEmitted = true
      this.errorCb?.('mp3_fetch_failed')
    }
  }

  private applyMediaSession(): void {
    const ms = (typeof navigator !== 'undefined' ? navigator.mediaSession : undefined) as
      | (MediaSession & {
          metadata: MediaMetadata | null
          setActionHandler?: (
            action: string,
            handler: ((details?: unknown) => void) | null,
          ) => void
          setPositionState?: (state: {
            duration?: number
            position?: number
            playbackRate?: number
          }) => void
        })
      | undefined
    if (!ms || typeof MediaMetadata === 'undefined') return
    const m = this.media ?? {}
    const fallbackTitle = titleForContentType(this.contentType)
    const meta = new MediaMetadata({
      title: m.title ?? fallbackTitle,
      artist: m.artist ?? this.bookTitle ?? '',
      album: m.album ?? 'Book Companion',
      artwork: m.artwork ?? [],
    })
    if (m.chapterInfo) {
      ;(meta as unknown as { chapterInfo: MediaChapter[] }).chapterInfo = m.chapterInfo
    }
    ms.metadata = meta
    ms.playbackState = 'playing'
    ms.setActionHandler?.('play', () => {
      void this.play()
    })
    ms.setActionHandler?.('pause', () => this.pause())
    ms.setActionHandler?.('previoustrack', () => this.prevSentence())
    ms.setActionHandler?.('nexttrack', () => this.nextSentence())
    ms.setActionHandler?.('seekto', (d: unknown) => {
      const time = (d as { seekTime?: number } | undefined)?.seekTime
      if (typeof time === 'number') {
        this.audio.currentTime = time
        this.onTimeUpdate()
      }
    })
    ms.setPositionState?.({
      duration: this.durationSeconds,
      position: this.audio.currentTime,
      playbackRate: 1,
    })
  }

  pause(): void {
    this.cancelWatchdog()
    this.audio.pause()
  }

  nextSentence(): void {
    this.cancelWatchdog()
    this.seek(Math.min(this.idx + 1, this.totalSentences - 1))
  }

  prevSentence(): void {
    this.cancelWatchdog()
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
    this.cancelWatchdog()
    this.audio.removeEventListener('timeupdate', this.onTimeUpdate)
    this.audio.removeEventListener('ended', this.onEnded)
    this.audio.removeEventListener('error', this.onAudioError)
    try {
      this.audio.pause()
      this.audio.removeAttribute('src')
      this.audio.load()
    } catch {
      /* ignore */
    }
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
