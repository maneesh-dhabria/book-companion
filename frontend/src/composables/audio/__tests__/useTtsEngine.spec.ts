import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: {
    lookup: vi.fn(),
    mp3Url: (b: number, ct: string, ci: number) => `/api/v1/books/${b}/audio/${ct}/${ci}.mp3`,
  },
}))

import { audioApi } from '@/api/audio'
import { useTtsEngine } from '@/composables/audio/useTtsEngine'

describe('useTtsEngine', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('routes to Mp3Engine when pregenerated=true', async () => {
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: true,
      url: '/api/v1/books/1/audio/section_summary/42.mp3',
      voice: 'af_sarah',
      engine: 'kokoro',
      duration_seconds: 30,
      sentence_offsets_seconds: [0, 4, 9],
      sentence_offsets_chars: [0, 7, 15],
      sanitized_text: 'A. B. C.',
      stale: null,
    })
    const engine = await useTtsEngine().load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 42,
    })
    expect(engine.kind).toBe('mp3')
  })

  it('routes to WebSpeechEngine when pregenerated=false', async () => {
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0],
      sanitized_text: 'Hello world.',
    })
    const engine = await useTtsEngine().load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 42,
    })
    expect(engine.kind).toBe('web-speech')
  })

  it('lookup failure raises lookup_failed', async () => {
    vi.mocked(audioApi.lookup).mockRejectedValueOnce(new Error('boom'))
    await expect(
      useTtsEngine().load({ bookId: 1, contentType: 'section_summary', contentId: 42 }),
    ).rejects.toThrow()
  })
})
