import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const playSpy = vi.fn(async () => undefined)
const pauseSpy = vi.fn()
const nextSpy = vi.fn()
const prevSpy = vi.fn()
const seekSpy = vi.fn()
const terminateSpy = vi.fn()

vi.mock('@/composables/audio/useTtsEngine', () => ({
  useTtsEngine: () => ({
    load: vi.fn().mockResolvedValue({ kind: 'web-speech' }),
    terminate: terminateSpy,
    playActive: playSpy,
    pauseActive: pauseSpy,
    nextActive: nextSpy,
    prevActive: prevSpy,
    seekActive: seekSpy,
  }),
}))

import Playbar from '@/components/audio/Playbar.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('Playbar ↔ engine wiring (regression guard for FR-16)', () => {
  it('clicking Play after engine is attached invokes engine.play exactly once', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.status = 'paused'
    const wrap = mount(Playbar)
    await wrap.find('[data-testid="play-pause"]').trigger('click')
    expect(playSpy).toHaveBeenCalledTimes(1)
  })

  it('clicking Pause invokes engine.pause', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.status = 'playing'
    const wrap = mount(Playbar)
    await wrap.find('[data-testid="play-pause"]').trigger('click')
    expect(pauseSpy).toHaveBeenCalledTimes(1)
  })

  it('clicking Close terminates the engine', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    const wrap = mount(Playbar)
    await wrap.find('[aria-label="Close player"]').trigger('click')
    expect(terminateSpy).toHaveBeenCalledTimes(1)
  })
})
