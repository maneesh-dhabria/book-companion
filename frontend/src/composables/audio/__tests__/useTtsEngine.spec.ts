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
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const cache = await import('@/composables/audio/preloadCache')
    cache._resetForTests()
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

  it('lookup failure raises lookup_failed and sets store error', async () => {
    const { useTtsPlayerStore } = await import('@/stores/ttsPlayer')
    const store = useTtsPlayerStore()
    vi.mocked(audioApi.lookup).mockRejectedValueOnce(new Error('boom'))
    await expect(
      useTtsEngine().load({ bookId: 1, contentType: 'section_summary', contentId: 42 }),
    ).rejects.toThrow()
    expect(store.errorKind).toBe('lookup_failed')
  })

  it('engine error transitions store to error', async () => {
    const { useTtsPlayerStore } = await import('@/stores/ttsPlayer')
    const store = useTtsPlayerStore()
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: true,
      url: '/x.mp3',
      duration_seconds: 30,
      sentence_offsets_seconds: [0, 4, 9],
      sentence_offsets_chars: [0, 7, 15],
      sanitized_text: 'A. B. C.',
      voice: 'af_sarah',
    })
    const eng = await useTtsEngine().load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 42,
    })
    eng._fakeError?.('mp3_fetch_failed')
    expect(store.status).toBe('error')
    expect(store.errorKind).toBe('mp3_fetch_failed')
  })

  it('passes settingsStore.tts.voice + default_speed to WebSpeechEngine', async () => {
    const { useSettingsStore } = await import('@/stores/settings')
    const settings = useSettingsStore()
    settings.tts = {
      engine: 'web-speech',
      voice: 'Daniel',
      default_speed: 1.5,
      auto_advance: true,
    }
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0, 3],
      sanitized_text: 'Hi there.',
    })
    const wsMod = await import('@/composables/audio/webSpeechEngine')
    const RealCtor = wsMod.WebSpeechEngine
    const wsCtorSpy = vi
      .spyOn(wsMod, 'WebSpeechEngine')
      .mockImplementation(function (
        this: unknown,
        opts: ConstructorParameters<typeof wsMod.WebSpeechEngine>[0],
      ) {
        // Forward to the real ctor so engine.onError/onEnd wiring still works.
        return new RealCtor(opts)
      } as unknown as typeof wsMod.WebSpeechEngine)
    await useTtsEngine().load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 1,
    })
    expect(wsCtorSpy).toHaveBeenCalledWith(
      expect.objectContaining({ voice: 'Daniel', rate: 1.5 }),
    )
  })

  it('exposes terminate() that clears lastEngine and is idempotent', async () => {
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0],
      sanitized_text: 'Hi.',
    })
    const api = useTtsEngine()
    await api.load({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    const terminated = api.terminate()
    expect(terminated).not.toBeNull()
    expect(api.terminate()).toBeNull()
  })
})
