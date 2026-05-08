import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/composables/audio/useTtsEngine', () => ({
  useTtsEngine: () => ({
    load: vi.fn().mockResolvedValue({ kind: 'web-speech' }),
    terminate: vi.fn(),
    playActive: vi.fn(async () => undefined),
    pauseActive: vi.fn(),
    nextActive: vi.fn(),
    prevActive: vi.fn(),
    seekActive: vi.fn(),
  }),
}))

import Playbar from '@/components/audio/Playbar.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('Playbar', () => {
  it('does not render when store is idle', () => {
    const wrap = mount(Playbar)
    expect(wrap.find('.bc-playbar').exists()).toBe(false)
  })

  it('renders when store.isActive', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    const wrap = mount(Playbar)
    expect(wrap.find('.bc-playbar').exists()).toBe(true)
  })

  it('shows sentence index and elapsed/total', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.engine = 'mp3'
    store.voice = 'af_sarah'
    store.totalSentences = 47
    store.sentenceIndex = 16
    store.sentenceOffsets = Array.from({ length: 48 }, (_, i) => (i * 368) / 47)
    const wrap = mount(Playbar)
    expect(wrap.text()).toContain('sentence 17 of 47')
    expect(wrap.text()).toMatch(/\d+:\d{2} \/ \d+:\d{2}/)
  })

  it('shows Limited controls pill when engine=web-speech', () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.engine = 'web-speech'
    const wrap = mount(Playbar)
    expect(wrap.find('[data-testid="limited-controls"]').exists()).toBe(true)
  })

  it('renders Retry on status=error and calls store.retry', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.setError('mp3_fetch_failed')
    const wrap = mount(Playbar)
    const retry = wrap.find('button[data-testid="retry"]')
    expect(retry.exists()).toBe(true)
    const spy = vi.spyOn(store, 'retry')
    await retry.trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('clicking play/pause toggles store.status', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.status = 'paused'
    const wrap = mount(Playbar)
    const btn = wrap.find('[data-testid="play-pause"]')
    await btn.trigger('click')
    expect(store.status).toBe('playing')
    await btn.trigger('click')
    expect(store.status).toBe('paused')
  })

  it('renders spinner glyph and aria-label="Starting" when status === "starting"', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.status = 'starting'
    const wrap = mount(Playbar)
    const btn = wrap.find('[data-testid="play-pause"]')
    expect(btn.attributes('aria-label')).toBe('Starting')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('aria-disabled')).toBe('true')
    expect(btn.find('svg.animate-spin').exists()).toBe(true)
  })

  it('error template shows generic copy and Retry with errorKind in title', async () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.setError('engine_unavailable')
    const wrap = mount(Playbar)
    expect(wrap.text()).toContain("Audio couldn't start. Try again or check your settings.")
    expect(wrap.find('[data-testid="retry"]').exists()).toBe(true)
    const errSpan = wrap.find('[data-testid="audio-error-message"]')
    expect(errSpan.attributes('title') ?? '').toContain('engine_unavailable')
  })

  it('hides timestamp on Web Speech (FR-E01)', () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.engine = 'web-speech'
    const wrap = mount(Playbar)
    expect(wrap.find('[data-testid="timestamp"]').exists()).toBe(false)
  })

  it('shows timestamp on Kokoro/mp3 engine (FR-E01)', () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.engine = 'mp3'
    store.totalSentences = 5
    store.sentenceIndex = 0
    store.sentenceOffsets = [0, 10, 20, 30, 40, 50]
    const wrap = mount(Playbar)
    const ts = wrap.find('[data-testid="timestamp"]')
    expect(ts.exists()).toBe(true)
    expect(ts.text()).toMatch(/\d+:\d{2} \/ \d+:\d{2}/)
  })

  it('Limited-controls badge has tooltip + settings link (FR-E03)', () => {
    const store = useTtsPlayerStore()
    store.open({ bookId: 1, contentType: 'section_summary', contentId: 1 })
    store.engine = 'web-speech'
    const wrap = mount(Playbar)
    const badge = wrap.find('[data-testid="limited-controls"]')
    expect(badge.exists()).toBe(true)
    const tooltip = wrap.find('[data-testid="limited-controls-tooltip"]')
    expect(tooltip.exists()).toBe(true)
    expect(tooltip.text()).toContain("Web Speech can't seek/scrub")
    const link = tooltip.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/settings#audio')
  })
})
