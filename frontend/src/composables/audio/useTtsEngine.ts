import { type AudioContentType, type AudioLookupResponse } from '@/api/audio'
import { useBooksStore } from '@/stores/books'
import { useSettingsStore } from '@/stores/settings'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

import { Mp3Engine } from './mp3Engine'
import * as preloadCache from './preloadCache'
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
  terminate(): TtsEngine | null
}

function terminate(): TtsEngine | null {
  if (!lastEngine) return null
  const eng = lastEngine
  try {
    eng.terminate()
  } catch {
    /* ignore */
  }
  lastEngine = null
  return eng
}

export function useTtsEngine(): UseTtsEngineApi {
  return {
    terminate,
    async load(args: LoadArgs) {
      const store = useTtsPlayerStore()
      // Terminate the previous engine so prior audio + queued utterances stop
      // before we attach a new one. Without this, switching sections leaves
      // the prior <audio> buffering and prior speechSynthesis utterances
      // queued, producing overlapping playback.
      if (lastEngine) {
        try {
          lastEngine.terminate()
        } catch {
          /* ignore */
        }
        lastEngine = null
      }
      let lookup: AudioLookupResponse
      try {
        // FR-24 / FR-25h / D16: route through preloadCache so a previously
        // populated entry resolves synchronously and the iOS Safari
        // user-gesture chain is preserved between click and engine.play().
        lookup = await preloadCache.preload({
          bookId: args.bookId,
          contentType: args.contentType,
          contentId: args.contentId,
          voice: args.voice,
        })
      } catch (err) {
        store.setError('lookup_failed')
        throw err
      }
      // FR-18 / plan T5: read persisted Web Speech voice + rate so saved
      // settings are honored. T18 will consume contentType + bookTitle for
      // mediaSession metadata; we pass them through today so the engine
      // constructor signatures are stable.
      const settingsStore = useSettingsStore()
      const ttsCfg = settingsStore.tts
      const wsVoice = args.voice ?? ttsCfg?.voice ?? undefined
      const wsRate = ttsCfg?.default_speed ?? 1.0
      const booksStore = useBooksStore()
      const bookTitle =
        booksStore.books.find((b) => b.id === args.bookId)?.title ?? ''
      let engine: TtsEngine
      if (lookup.pregenerated && lookup.url) {
        engine = new Mp3Engine({
          url: lookup.url,
          sentenceOffsetsSeconds: lookup.sentence_offsets_seconds ?? [0],
          durationSeconds: lookup.duration_seconds ?? 0,
          sanitizedText: lookup.sanitized_text,
          sentenceOffsetsChars: lookup.sentence_offsets_chars,
          contentType: args.contentType,
          bookTitle,
        })
      } else {
        engine = new WebSpeechEngine({
          sanitizedText: lookup.sanitized_text,
          sentenceOffsetsChars: lookup.sentence_offsets_chars,
          voice: wsVoice,
          rate: wsRate,
          contentType: args.contentType,
          bookTitle,
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
