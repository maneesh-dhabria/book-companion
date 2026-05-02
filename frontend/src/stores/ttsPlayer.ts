import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type TtsContentType = 'section_summary' | 'book_summary' | 'annotation' | 'section'

export type TtsStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'ended' | 'error'

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
  contentType: TtsContentType
  contentId: number
  sentenceIndex?: number
}

export const useTtsPlayerStore = defineStore('ttsPlayer', () => {
  const isActive = ref(false)
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

  const canPlay = computed(() => status.value === 'paused' || status.value === 'ended')
  const isPlaying = computed(() => status.value === 'playing')
  const isError = computed(() => status.value === 'error')

  function open(args: OpenContentArgs) {
    contentType.value = args.contentType
    contentId.value = args.contentId
    sentenceIndex.value = args.sentenceIndex ?? 0
    status.value = 'loading'
    isActive.value = true
    errorKind.value = null
    stale.value = null
  }

  function close() {
    isActive.value = false
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
  }

  function pause() {
    status.value = 'paused'
  }

  function nextSentence() {
    if (totalSentences.value === 0) {
      sentenceIndex.value += 1
      return
    }
    if (sentenceIndex.value < totalSentences.value - 1) {
      sentenceIndex.value += 1
    }
  }

  function prevSentence() {
    if (sentenceIndex.value > 0) {
      sentenceIndex.value -= 1
    }
  }

  function setError(kind: TtsErrorKind) {
    status.value = 'error'
    errorKind.value = kind
  }

  function retry() {
    if (contentType.value === null || contentId.value === null) {
      errorKind.value = null
      return
    }
    const at = sentenceIndex.value
    open({
      contentType: contentType.value,
      contentId: contentId.value,
      sentenceIndex: at,
    })
  }

  return {
    isActive,
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
    canPlay,
    isPlaying,
    isError,
    open,
    close,
    play,
    pause,
    nextSentence,
    prevSentence,
    setError,
    retry,
  }
})
