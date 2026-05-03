import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: {
    lookup: vi.fn(),
    lookupAnnotation: vi.fn(),
  },
}))

import { audioApi } from '@/api/audio'
import * as cache from '@/composables/audio/preloadCache'

beforeEach(() => {
  setActivePinia(createPinia())
  cache._resetForTests()
  vi.clearAllMocks()
})

describe('preloadCache', () => {
  it('coalesces N parallel preloads for the same content (FR-25c)', async () => {
    vi.mocked(audioApi.lookup).mockResolvedValue({
      pregenerated: false,
      sanitized_text: 'A.',
      sentence_offsets_chars: [0],
    })
    const args = {
      bookId: 1,
      contentType: 'section_summary' as const,
      contentId: 5,
    }
    const [a, b, c] = await Promise.all([
      cache.preload(args),
      cache.preload(args),
      cache.preload(args),
    ])
    expect(audioApi.lookup).toHaveBeenCalledTimes(1)
    expect(a).toBe(b)
    expect(b).toBe(c)
  })

  it('stores error sentinel with 30s TTL on lookup failure (FR-25d)', async () => {
    vi.mocked(audioApi.lookup).mockRejectedValueOnce(new Error('boom'))
    const args = {
      bookId: 1,
      contentType: 'section_summary' as const,
      contentId: 6,
    }
    await expect(cache.preload(args)).rejects.toThrow('boom')
    const entry = cache._inspect('section_summary:6')
    expect(entry?.error).toBeInstanceOf(Error)
    expect(entry).toBeTruthy()
    expect((entry?.expiresAt ?? 0) - Date.now()).toBeLessThan(30_000 + 100)
  })

  it('discards preload result when invalidation timestamp is newer (FR-25e)', async () => {
    let resolveFn: (v: unknown) => void = () => {}
    vi.mocked(audioApi.lookup).mockReturnValueOnce(
      new Promise((r) => {
        resolveFn = r as typeof resolveFn
      }) as Promise<never>,
    )
    const args = {
      bookId: 1,
      contentType: 'section_summary' as const,
      contentId: 7,
    }
    const promise = cache.preload(args)
    cache.invalidate('section_summary:7')
    // Mock the retry lookup with fresh content first so the chain resolves to it.
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: true,
      url: '/audio/x.mp3',
      sanitized_text: 'Fresh.',
      sentence_offsets_chars: [0],
    })
    resolveFn({
      pregenerated: false,
      sanitized_text: 'Stale.',
      sentence_offsets_chars: [0],
    })
    const result = await promise
    expect(result.sanitized_text).toBe('Fresh.')
  })

  it('coalesces annotation preloads via lookupAnnotation', async () => {
    vi.mocked(audioApi.lookupAnnotation).mockResolvedValue({
      pregenerated: false,
      sanitized_text: 'Note.',
      sentence_offsets_chars: [0],
    })
    const args = {
      bookId: 0,
      contentType: 'annotation' as const,
      contentId: 9,
    }
    await Promise.all([cache.preload(args), cache.preload(args)])
    expect(audioApi.lookupAnnotation).toHaveBeenCalledTimes(1)
  })
})
