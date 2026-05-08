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
    // Spy on the constructor and forward to the real one so engine wiring
    // still works inside useTtsEngine.load(). Cast through `any` because
    // vi.spyOn typing of class members vs. construct signatures diverges.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const wsCtorSpy = vi.spyOn(wsMod as any, 'WebSpeechEngine').mockImplementation(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ((opts: any) => new RealCtor(opts)) as any,
    )
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

  it('load() sets store.status to paused on success', async () => {
    const { useTtsPlayerStore } = await import('@/stores/ttsPlayer')
    const store = useTtsPlayerStore()
    store.status = 'loading'
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0],
      sanitized_text: 'Hi.',
    })
    await useTtsEngine().load({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    expect(store.status).toBe('paused')
  })

  it('load() does not overwrite a pre-existing error status (FR-20 race)', async () => {
    const { useTtsPlayerStore } = await import('@/stores/ttsPlayer')
    const store = useTtsPlayerStore()
    store.status = 'error'
    store.errorKind = 'engine_unavailable'
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0],
      sanitized_text: 'Hi.',
    })
    await useTtsEngine().load({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    expect(store.status).toBe('error')
  })

  it('playActive() calls engine.play() when lastEngine is set', async () => {
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0],
      sanitized_text: 'Hi.',
    })
    const api = useTtsEngine()
    const engine = await api.load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 1,
    })
    const playSpy = vi.spyOn(engine, 'play')
    await api.playActive()
    expect(playSpy).toHaveBeenCalledTimes(1)
  })

  it('playActive() sets store.error to engine_unavailable when no engine', async () => {
    const { useTtsPlayerStore } = await import('@/stores/ttsPlayer')
    const store = useTtsPlayerStore()
    const api = useTtsEngine()
    api.terminate()
    await api.playActive()
    expect(store.errorKind).toBe('engine_unavailable')
    expect(store.status).toBe('error')
  })

  it('pauseActive/nextActive/prevActive/seekActive forward to engine', async () => {
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0, 3],
      sanitized_text: 'Hi. Bye.',
    })
    const api = useTtsEngine()
    const engine = await api.load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 1,
    })
    const pauseSpy = vi.spyOn(engine, 'pause')
    const nextSpy = vi.spyOn(engine, 'nextSentence')
    const prevSpy = vi.spyOn(engine, 'prevSentence')
    const seekSpy = vi.spyOn(engine, 'seek')
    api.pauseActive()
    api.nextActive()
    api.prevActive()
    api.seekActive(1)
    expect(pauseSpy).toHaveBeenCalled()
    expect(nextSpy).toHaveBeenCalled()
    expect(prevSpy).toHaveBeenCalled()
    expect(seekSpy).toHaveBeenCalledWith(1)
  })

  it('onWaitingForVoices(true) sets store.status to starting; (false) restores', async () => {
    const { useTtsPlayerStore } = await import('@/stores/ttsPlayer')
    const store = useTtsPlayerStore()
    vi.mocked(audioApi.lookup).mockResolvedValueOnce({
      pregenerated: false,
      sentence_offsets_chars: [0],
      sanitized_text: 'Hi.',
    })
    const engine = await useTtsEngine().load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 1,
    })
    // Trigger waiting=true via the engine's wired callback
    ;(engine as unknown as { waitingCb: ((w: boolean) => void) | null }).waitingCb?.(true)
    expect(store.status).toBe('starting')
    ;(engine as unknown as { waitingCb: ((w: boolean) => void) | null }).waitingCb?.(false)
    expect(['playing', 'paused']).toContain(store.status)
  })
})
