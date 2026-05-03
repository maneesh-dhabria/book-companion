/**
 * FR-25 family: preload cache for audio lookups.
 *
 * Module-level singleton (D5). Goals:
 * - Coalesce N parallel preloads for the same content (FR-25c).
 * - Cache successful lookups for 5 min; failures for 30 s (FR-25d).
 * - Discard a preload result if invalidated mid-flight; refire once (FR-25e).
 * - Subscribe to audioJob.recordContentCompletion (D1, FR-25f) so completed
 *   per-content audio jobs evict the matching cache entry.
 *
 * Consumed by `TtsPlayButton` (visibility predicate + click) and
 * `useTtsEngine.load()` (gesture-preserving fast path).
 */
import { audioApi, type AudioLookupResponse } from '@/api/audio'
import type { AudioContentType } from '@/api/audio'
import { useAudioJobStore } from '@/stores/audioJob'

export type PreloadContentType = AudioContentType | 'annotation'

export interface CacheEntry {
  result?: AudioLookupResponse
  promise?: Promise<AudioLookupResponse>
  error?: Error
  createdAt: number
  expiresAt: number
}

export interface PreloadArgs {
  bookId: number
  contentType: PreloadContentType
  contentId: number
  voice?: string
}

const TTL_OK = 5 * 60 * 1000
const TTL_ERR = 30 * 1000

const cache = new Map<string, CacheEntry>()
// Per-key monotonic invalidation counter. Using a counter (not Date.now())
// avoids tied-millisecond races in fast environments / fake timers.
const invalidationCount = new Map<string, number>()
let subscriptionInstalled = false

function key(args: { contentType: PreloadContentType; contentId: number }): string {
  return `${args.contentType}:${args.contentId}`
}

function fetchOnce(args: PreloadArgs): Promise<AudioLookupResponse> {
  if (args.contentType === 'annotation') {
    return audioApi.lookupAnnotation(args.contentId)
  }
  return audioApi.lookup({
    book_id: args.bookId,
    content_type: args.contentType,
    content_id: args.contentId,
    voice: args.voice,
  })
}

export function getCached(k: string): CacheEntry | undefined {
  const e = cache.get(k)
  if (!e) return undefined
  if (e.expiresAt < Date.now()) {
    cache.delete(k)
    return undefined
  }
  return e
}

export function preload(args: PreloadArgs): Promise<AudioLookupResponse> {
  const k = key(args)
  const existing = cache.get(k)
  if (existing && existing.expiresAt >= Date.now()) {
    if (existing.result) return Promise.resolve(existing.result)
    if (existing.promise) return existing.promise
    if (existing.error) return Promise.reject(existing.error)
  }
  const startedAt = Date.now()
  const startCount = invalidationCount.get(k) ?? 0
  const fetchPromise = fetchOnce(args)
  const wrapped: Promise<AudioLookupResponse> = fetchPromise.then(
    (result) => {
      const currentCount = invalidationCount.get(k) ?? 0
      if (currentCount > startCount) {
        // Invalidated mid-flight; discard and re-fire once.
        cache.delete(k)
        return preload(args)
      }
      cache.set(k, {
        result,
        createdAt: Date.now(),
        expiresAt: Date.now() + TTL_OK,
      })
      return result
    },
    (err: Error) => {
      cache.set(k, {
        error: err,
        createdAt: Date.now(),
        expiresAt: Date.now() + TTL_ERR,
      })
      throw err
    },
  )
  cache.set(k, {
    promise: wrapped,
    createdAt: startedAt,
    expiresAt: startedAt + TTL_OK,
  })
  return wrapped
}

export function invalidate(k: string): void {
  invalidationCount.set(k, (invalidationCount.get(k) ?? 0) + 1)
  cache.delete(k)
}

export function initCacheSubscription(): void {
  if (subscriptionInstalled) return
  subscriptionInstalled = true
  const store = useAudioJobStore()
  store.$onAction(({ name, args }) => {
    if (name !== 'recordContentCompletion') return
    const [contentType, contentId] = args as [string, number]
    invalidate(`${contentType}:${contentId}`)
    // Section-level completions invalidate sibling view (G2 / D1).
    if (contentType === 'section_summary') invalidate(`section_content:${contentId}`)
    if (contentType === 'section_content') invalidate(`section_summary:${contentId}`)
  })
}

export function _resetForTests(): void {
  cache.clear()
  invalidationCount.clear()
  subscriptionInstalled = false
}

export function _inspect(k: string): CacheEntry | undefined {
  return cache.get(k)
}
