import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const playSpy = vi.fn(async () => undefined)
const pauseSpy = vi.fn()
const nextSpy = vi.fn()
const prevSpy = vi.fn()
const seekSpy = vi.fn()
const terminateSpy = vi.fn()
const loadSpy = vi.fn(async () => ({ kind: 'web-speech' as const }))

vi.mock('@/composables/audio/useTtsEngine', () => ({
  useTtsEngine: () => ({
    load: loadSpy,
    terminate: terminateSpy,
    playActive: playSpy,
    pauseActive: pauseSpy,
    nextActive: nextSpy,
    prevActive: prevSpy,
    seekActive: seekSpy,
  }),
}))

import { useTtsPlayerStore } from '@/stores/ttsPlayer'

describe('ttsPlayerStore.setEngine — mid-playback restart-section (FR-12)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('updates engine ref to the requested kind', () => {
    const s = useTtsPlayerStore()
    s.setEngine('mp3')
    expect(s.engine).toBe('mp3')
    s.setEngine('web-speech')
    expect(s.engine).toBe('web-speech')
  })

  it('mid-playback toggle: stops current playback, resets sentenceIndex, re-plays in new engine', async () => {
    const s = useTtsPlayerStore()
    s.open({ bookId: 1, contentType: 'section_summary', contentId: 42, sentenceIndex: 5 })
    s.engine = 'mp3'
    s.status = 'playing'

    s.setEngine('web-speech')

    // Engine flipped
    expect(s.engine).toBe('web-speech')
    // Position reset — no word-position carryover (FR-12)
    expect(s.sentenceIndex).toBe(0)
    // Old engine paused (engine-aware via useTtsEngine().pauseActive)
    expect(pauseSpy).toHaveBeenCalled()
    // Re-issued via useTtsEngine — it routes to the now-active engine.
    expect(playSpy).toHaveBeenCalled()
  })

  it('idle toggle: only flips engine ref, does not invoke playActive', () => {
    const s = useTtsPlayerStore()
    s.engine = 'mp3'
    s.status = 'idle'

    s.setEngine('web-speech')

    expect(s.engine).toBe('web-speech')
    expect(playSpy).not.toHaveBeenCalled()
  })
})
