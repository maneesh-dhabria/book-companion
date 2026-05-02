import { audioApi, type AudioContentType, type AudioLookupResponse } from '@/api/audio'

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
      const lookup = await audioApi.lookup({
        book_id: args.bookId,
        content_type: args.contentType,
        content_id: args.contentId,
        voice: args.voice,
      })
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
      return Object.assign(engine, { lookup })
    },
  }
}
