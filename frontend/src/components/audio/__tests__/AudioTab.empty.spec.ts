import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import AudioTab from '../AudioTab.vue'

vi.mock('@/api/audio', () => ({
  audioApi: {
    inventory: vi.fn().mockResolvedValue({ files: [], coverage: { total: 0, generated: 0 } }),
  },
}))

function installSpeechSynth(initialVoices: unknown[]) {
  Object.defineProperty(window, 'speechSynthesis', {
    value: {
      getVoices: vi.fn(() => initialVoices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      speak: vi.fn(),
      cancel: vi.fn(),
    },
    configurable: true,
    writable: true,
  })
}

const stubs = { EngineChip: true, DifferencePopover: true, GenerateAudioModal: true }

describe('AudioTab empty-state verb-led + parallel CTAs (FR-10)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    installSpeechSynth([{ name: 'Samantha' } as unknown])
  })

  afterEach(() => {
    delete (window as unknown as { speechSynthesis?: unknown }).speechSynthesis
  })

  it('renders verb-led H2 + parallel Listen and Generate CTAs + caption', async () => {
    const wrapper = mount(AudioTab, { props: { bookId: 1 }, global: { stubs } })
    await flushPromises()

    const heading = wrapper.find('[data-testid="audio-empty-heading"]')
    expect(heading.text()).toBe('Listen to this book')

    const subtitle = wrapper.find('[data-testid="audio-empty-subtitle"]')
    expect(subtitle.exists()).toBe(true)
    expect(subtitle.text()).toBe(
      'Instant playback via your browser, or generate MP3s for offline listening.',
    )

    const listen = wrapper.find('[data-testid="listen-cta"]')
    const generate = wrapper.find('[data-testid="generate-cta"]')
    expect(listen.exists()).toBe(true)
    expect(generate.exists()).toBe(true)
    // Siblings: same parent element
    expect(listen.element.parentElement).toBe(generate.element.parentElement)

    const caption = wrapper.find('[data-testid="audio-empty-caption"]')
    expect(caption.exists()).toBe(true)
    expect(caption.text()).toBe('No audio files yet — generate to enable seek/scrub.')
    expect(caption.classes()).toContain('text-slate-500')
  })
})
