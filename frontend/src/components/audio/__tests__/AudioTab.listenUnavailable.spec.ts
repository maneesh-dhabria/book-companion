import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import AudioTab from '../AudioTab.vue'

vi.mock('@/api/audio', () => ({
  audioApi: {
    inventory: vi.fn().mockResolvedValue({ files: [], coverage: { total: 0, generated: 0 } }),
  },
}))

function withoutSpeechSynth() {
  delete (window as unknown as { speechSynthesis?: unknown }).speechSynthesis
}

function withEmptySpeechSynth() {
  Object.defineProperty(window, 'speechSynthesis', {
    value: {
      getVoices: vi.fn(() => []),
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

describe('AudioTab listen-unavailable morph (FR-09)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    delete (window as unknown as { speechSynthesis?: unknown }).speechSynthesis
  })

  it('no speechSynthesis: H2 morphs, Listen disabled, sr-only tip rendered', async () => {
    withoutSpeechSynth()
    const wrapper = mount(AudioTab, { props: { bookId: 1 }, global: { stubs } })
    await flushPromises()

    const heading = wrapper.find('[data-testid="audio-empty-heading"]')
    expect(heading.text()).toBe('Generate MP3s to listen to this book')

    const listen = wrapper.find('[data-testid="listen-cta"]')
    expect(listen.exists()).toBe(true)
    expect(listen.attributes('disabled')).toBeDefined()
    expect(listen.attributes('aria-describedby')).toBe('listen-tip')

    const tip = wrapper.find('#listen-tip')
    expect(tip.exists()).toBe(true)
    expect(tip.classes()).toContain('sr-only')
    expect(tip.text()).toMatch(/Web Speech is unavailable/i)
  })

  it('speechSynthesis present but getVoices() empty after timeout: same morph', async () => {
    withEmptySpeechSynth()
    const wrapper = mount(AudioTab, { props: { bookId: 1 }, global: { stubs } })
    await flushPromises()
    // timeout flushes voicesReady true with no voices populated
    await vi.advanceTimersByTimeAsync(501)
    await flushPromises()

    const heading = wrapper.find('[data-testid="audio-empty-heading"]')
    expect(heading.text()).toBe('Generate MP3s to listen to this book')
    expect(wrapper.find('[data-testid="listen-cta"]').attributes('disabled')).toBeDefined()
  })
})
