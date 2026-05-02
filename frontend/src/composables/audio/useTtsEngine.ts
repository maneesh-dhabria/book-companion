import { audioApi, type AudioContentType, type AudioLookupResponse } from '@/api/audio'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

import { Mp3Engine } from './mp3Engine'
import type { TtsEngine } from './types'
import { WebSpeechEngine } from './webSpeechEngine'

export interface LoadArgs {
  bookId: number
  contentType: AudioContentType
  contentId: number
  voice?: string
}

export interface UseTtsEngineApi {
  load(args: LoadArgs): Promise<TtsEngine & { lookup: AudioLookupResponse }>
}

export function useTtsEngine(): UseTtsEngineApi {
  return {
    async load(args: LoadArgs) {
      const store = useTtsPlayerStore()
      let lookup: AudioLookupResponse
      try {
        lookup = await audioApi.lookup({
          book_id: args.bookId,
          content_type: args.contentType,
          content_id: args.contentId,
          voice: args.voice,
        })
      } catch (err) {
        store.setError('lookup_failed')
        throw err
      }
      let engine: TtsEngine
      if (lookup.pregenerated && lookup.url) {
        engine = new Mp3Engine({
          url: lookup.url,
          sentenceOffsetsSeconds: lookup.sentence_offsets_seconds ?? [0],
          durationSeconds: lookup.duration_seconds ?? 0,
          sanitizedText: lookup.sanitized_text,
          sentenceOffsetsChars: lookup.sentence_offsets_chars,
        })
      } else {
        engine = new WebSpeechEngine({
          sanitizedText: lookup.sanitized_text,
          sentenceOffsetsChars: lookup.sentence_offsets_chars,
          voice: args.voice,
        })
      }
      // Wire engine events into the store.
      engine.onError((kind) => store.setError(kind))
      engine.onSentenceChange((idx) => {
        store.sentenceIndex = idx
      })
      engine.onEnd(() => {
        store.status = 'ended'
      })
      store.engine = engine.kind
      store.voice = lookup.voice ?? args.voice ?? null
      store.totalSentences = engine.totalSentences
      store.sanitizedText = lookup.sanitized_text
      store.sentenceOffsets = lookup.sentence_offsets_seconds ?? []
      store.sentenceOffsetsChars = lookup.sentence_offsets_chars
      store.mp3Url = lookup.url ?? null
      store.stale = lookup.stale ?? null
      store.activeEngineReason =
        engine.kind === 'mp3' ? 'pregenerated' : 'fallback_no_pregen'
      return Object.assign(engine, { lookup })
    },
  }
}
