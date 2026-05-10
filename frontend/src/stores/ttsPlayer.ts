import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { useTtsEngine } from '@/composables/audio/useTtsEngine'
import type { AudioContentType } from '@/api/audio'

export type TtsContentType =
  | 'section_summary'
  | 'book_summary'
  | 'section_content'
  | 'annotation'
  | 'annotations_playlist'

export type TtsStatus =
  | 'idle'
  | 'loading'
  | 'starting'
  | 'playing'
  | 'paused'
  | 'ended'
  | 'error'

export type TtsEngineKind = 'mp3' | 'web-speech'

export type TtsErrorKind =
  | 'mp3_fetch_failed'
  | 'utterance_failed'
  | 'voice_unavailable'
  | 'sanitize_empty'
  | 'lookup_failed'
  | 'engine_unavailable'
  | 'network'
  | 'unknown'

export type StaleReason = 'source_changed' | 'sanitizer_upgraded' | 'segmenter_drift'

export type ActiveEngineReason =
  | 'pregenerated'
  | 'fallback_no_pregen'
  | 'user_setting'
  | 'kokoro_unavailable'

export interface OpenContentArgs {
  bookId: number
  contentType: TtsContentType
  contentId: number
  sentenceIndex?: number
}

export const useTtsPlayerStore = defineStore('ttsPlayer', () => {
  const isActive = ref(false)
  const bookId = ref<number | null>(null)
  const contentType = ref<TtsContentType | null>(null)
  const contentId = ref<number | null>(null)
  const sentenceIndex = ref(0)
  const totalSentences = ref(0)
  const status = ref<TtsStatus>('idle')
  const engine = ref<TtsEngineKind | null>(null)
  const voice = ref<string | null>(null)
  const mp3Url = ref<string | null>(null)
  const sentenceOffsets = ref<number[]>([])
  const sentenceOffsetsChars = ref<number[]>([])
  const sanitizedText = ref<string | null>(null)
  const stale = ref<{ reason: StaleReason } | null>(null)
  const mediaSessionEnabled = ref(true)
  const errorKind = ref<TtsErrorKind | null>(null)
  const defaultEngine = ref<TtsEngineKind | null>(null)
  const activeEngineReason = ref<ActiveEngineReason | null>(null)
  const pendingRegenBanner = ref(false)

  const canPlay = computed(() => status.value === 'paused' || status.value === 'ended')
  const isPlaying = computed(() => status.value === 'playing')
  const isError = computed(() => status.value === 'error')

  function open(args: OpenContentArgs) {
    bookId.value = args.bookId
    contentType.value = args.contentType
    contentId.value = args.contentId
    sentenceIndex.value = args.sentenceIndex ?? 0
    status.value = 'loading'
    isActive.value = true
    errorKind.value = null
    stale.value = null
  }

  function close() {
    try {
      useTtsEngine().terminate()
    } catch {
      /* ignore */
    }
    isActive.value = false
    bookId.value = null
    contentType.value = null
    contentId.value = null
    sentenceIndex.value = 0
    totalSentences.value = 0
    status.value = 'idle'
    engine.value = null
    voice.value = null
    mp3Url.value = null
    sentenceOffsets.value = []
    sentenceOffsetsChars.value = []
    sanitizedText.value = null
    stale.value = null
    errorKind.value = null
    activeEngineReason.value = null
  }

  function play() {
    status.value = 'playing'
    void useTtsEngine()
      .playActive()
      .catch(() => {
        // Engine errors flow through the wired onError -> setError path.
        // The .catch here is purely to silence unhandled-rejection warnings.
      })
  }

  function pause() {
    status.value = 'paused'
    useTtsEngine().pauseActive()
  }

  function nextSentence() {
    // No pre-update; engine.onSentenceChange will set sentenceIndex.
    useTtsEngine().nextActive()
  }

  function prevSentence() {
    useTtsEngine().prevActive()
  }

  function seek(idx: number) {
    useTtsEngine().seekActive(idx)
  }

  function setError(kind: TtsErrorKind) {
    status.value = 'error'
    errorKind.value = kind
  }

  async function retry() {
    if (
      contentType.value === null ||
      contentId.value === null ||
      bookId.value === null
    ) {
      errorKind.value = null
      return
    }
    const at = sentenceIndex.value
    const ct = contentType.value
    const ci = contentId.value
    const bid = bookId.value
    open({ bookId: bid, contentType: ct, contentId: ci, sentenceIndex: at })
    try {
      // 'annotation' is a runtime-only TtsContentType; retry only fires for
      // persisted content types, but guard for type-safety.
      await useTtsEngine().load({
        bookId: bid,
        contentType: ct as AudioContentType,
        contentId: ci,
      })
    } catch {
      // load() already calls setError on its own catch; nothing to do.
    }
  }

  // FR-11/FR-12: setEngine — toggle the active TTS engine. Full mid-playback
  // restart-section logic lives in T18; for now this stub flips the ref so
  // EnginePicker (T17) can drive the populated layout.
  function setEngine(kind: TtsEngineKind): void {
    engine.value = kind
  }

  return {
    isActive,
    bookId,
    contentType,
    contentId,
    sentenceIndex,
    totalSentences,
    status,
    engine,
    voice,
    mp3Url,
    sentenceOffsets,
    sentenceOffsetsChars,
    sanitizedText,
    stale,
    mediaSessionEnabled,
    errorKind,
    defaultEngine,
    activeEngineReason,
    pendingRegenBanner,
    canPlay,
    isPlaying,
    isError,
    setEngine,
    open,
    close,
    play,
    pause,
    nextSentence,
    prevSentence,
    seek,
    setError,
    retry,
  }
})
