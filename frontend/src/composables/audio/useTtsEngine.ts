import { audioApi, type AudioContentType, type AudioLookupResponse } from '@/api/audio'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

import { Mp3Engine } from './mp3Engine'
import type { TtsEngine } from './types'
import { WebSpeechEngine } from './webSpeechEngine'

const TAB_ID =
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `tab-${Date.now()}-${Math.random().toString(36).slice(2)}`

let channel: BroadcastChannel | null = null
let lastEngine: TtsEngine | null = null

function getChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === 'undefined') return null
  if (channel) return channel
  channel = new BroadcastChannel('bc-tts-player')
  channel.addEventListener('message', (ev) => {
    const data = ev.data as { type?: string; tabId?: string } | null
    if (!data) return
    if (data.type === 'opening' && data.tabId !== TAB_ID && lastEngine) {
      lastEngine.pause()
    }
  })
  return channel
}

function broadcastOpen(): void {
  getChannel()?.postMessage({ type: 'opening', tabId: TAB_ID })
}

export interface LoadArgs {
  bookId: number
  contentType: AudioContentType
  contentId: number
  voice?: string
  nextContentId?: number
  autoAdvance?: boolean
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
      const api: UseTtsEngineApi = this
      engine.onEnd(() => {
        store.status = 'ended'
        if (args.autoAdvance && args.nextContentId) {
          void api.load({
            bookId: args.bookId,
            contentType: args.contentType,
            contentId: args.nextContentId,
            voice: args.voice,
            autoAdvance: args.autoAdvance,
          })
        }
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
      lastEngine = engine
      broadcastOpen()
      return Object.assign(engine, { lookup })
    },
  }
}
