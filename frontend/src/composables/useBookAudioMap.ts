// FR-C20 / P14 — shared in-memory cache of the per-book audio-availability
// map. SectionListTable (T19) and TOCDropdown (T21) both read it; we want
// at most one /audio/sections/by-book/{id} fetch per bookId per session.
//
// Cache strategy:
//   - cache:    bookId -> { map, failed }   (resolved state)
//   - inflight: bookId -> Promise            (in-progress fetch dedupe)
//
// Both are module-scoped; they survive component mount/unmount but reset
// on full page reload, which matches the "session-scoped cache" target.
import { ref, type Ref } from 'vue'

import { audioApi } from '@/api/audio'

export interface AudioMapEntry {
  has_mp3: boolean
  engine: string | null
}

export type AudioMap = Record<number, AudioMapEntry>

interface CacheEntry {
  map: AudioMap
  failed: boolean
}

const cache = new Map<number, CacheEntry>()
const inflight = new Map<number, Promise<void>>()

export interface UseBookAudioMap {
  map: Ref<AudioMap>
  failed: Ref<boolean>
  ready: Ref<boolean>
}

// Test-only: clear the module-scoped cache between cases.
export function _resetBookAudioMapCache(): void {
  cache.clear()
  inflight.clear()
}

export function useBookAudioMap(bookId: number): UseBookAudioMap {
  const cached = cache.get(bookId)
  const map = ref<AudioMap>(cached?.map ?? {})
  const failed = ref<boolean>(cached?.failed ?? false)
  const ready = ref<boolean>(cache.has(bookId))

  if (cache.has(bookId)) return { map, failed, ready }

  let p = inflight.get(bookId)
  if (!p) {
    p = audioApi
      .sectionsByBook(bookId)
      .then(
        (res) => {
          const m: AudioMap = {}
          for (const e of res.sections) {
            m[e.section_id] = { has_mp3: e.has_mp3, engine: e.engine }
          }
          cache.set(bookId, { map: m, failed: false })
        },
        () => {
          cache.set(bookId, { map: {}, failed: true })
        },
      )
      .finally(() => {
        inflight.delete(bookId)
      })
    inflight.set(bookId, p)
  }

  p.then(() => {
    const entry = cache.get(bookId)
    map.value = entry?.map ?? {}
    failed.value = entry?.failed ?? false
    ready.value = true
  })

  return { map, failed, ready }
}
