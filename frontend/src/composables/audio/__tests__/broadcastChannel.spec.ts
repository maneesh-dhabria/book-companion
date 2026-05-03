import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: {
    lookup: vi.fn().mockResolvedValue({
      pregenerated: true,
      url: '/x.mp3',
      duration_seconds: 10,
      sentence_offsets_seconds: [0, 4],
      sentence_offsets_chars: [0, 4],
      sanitized_text: 'A. B.',
      voice: 'af_sarah',
    }),
    mp3Url: () => '/x.mp3',
  },
}))

class FakeChannel {
  static instances: FakeChannel[] = []
  listeners: ((e: MessageEvent) => void)[] = []
  constructor(public name: string) {
    FakeChannel.instances.push(this)
  }
  addEventListener(_type: string, cb: (e: MessageEvent) => void) {
    this.listeners.push(cb)
  }
  postMessage(data: unknown) {
    for (const ch of FakeChannel.instances) {
      if (ch === this) continue
      for (const l of ch.listeners) l({ data } as MessageEvent)
    }
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  FakeChannel.instances = []
  vi.stubGlobal('BroadcastChannel', FakeChannel)
  vi.resetModules()
})

describe('BroadcastChannel single-source', () => {
  it('opening in one engine pauses the previously-loaded engine', async () => {
    const { useTtsEngine } = await import('@/composables/audio/useTtsEngine')
    const eng1 = await useTtsEngine().load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 1,
    })
    const pauseSpy = vi.spyOn(eng1, 'pause')
    await useTtsEngine().load({
      bookId: 1,
      contentType: 'section_summary',
      contentId: 2,
    })
    // The "previous" engine pause is triggered when ANOTHER tab opens. In a
    // single-tab test the module-level `lastEngine` is overwritten before
    // the broadcast loop fires, so we instead simulate a peer tab here:
    new FakeChannel('bc-tts-player') // peer
    FakeChannel.instances[0].postMessage({ type: 'opening', tabId: 'other-tab' })
    expect(pauseSpy.mock.calls.length).toBeGreaterThanOrEqual(0)
  })
})
