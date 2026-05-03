import type { TtsErrorKind } from '@/stores/ttsPlayer'

export type EngineKind = 'mp3' | 'web-speech'

export interface SentenceChangeHandler {
  (sentenceIndex: number): void
}

export interface ErrorHandler {
  (kind: TtsErrorKind): void
}

export interface EndHandler {
  (): void
}

export interface TtsEngine {
  kind: EngineKind
  sentences: string[]
  totalSentences: number
  durationSeconds: number
  play(): Promise<void> | void
  pause(): void
  nextSentence(): void
  prevSentence(): void
  seek(sentenceIndex: number): void
  onSentenceChange(cb: SentenceChangeHandler): void
  onEnd(cb: EndHandler): void
  onError(cb: ErrorHandler): void
  terminate(): void
  /** Test-only hook: simulate a fatal engine error. Real engines forward
   * underlying errors through `onError` automatically. */
  _fakeError?(kind: TtsErrorKind): void
}
