import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import SpikeFindingsBlock from '@/components/settings/SpikeFindingsBlock.vue'

interface AudioCtorCalls {
  instance: { ended: (() => void) | null; play: ReturnType<typeof vi.fn> } | null
}

const audioCalls: AudioCtorCalls = { instance: null }

class MockAudio {
  src: string
  ended: (() => void) | null = null
  play = vi.fn().mockResolvedValue(undefined)
  constructor(src: string) {
    this.src = src
    audioCalls.instance = this
  }
  addEventListener(name: string, cb: () => void) {
    if (name === 'ended') this.ended = cb
  }
}

let speechSpeakCalls: SpeechSynthesisUtterance[] = []
const speechSynthMock = {
  speak: vi.fn((u: SpeechSynthesisUtterance) => {
    speechSpeakCalls.push(u)
  }),
  cancel: vi.fn(),
  getVoices: vi.fn().mockReturnValue([]),
}

beforeEach(() => {
  vi.useFakeTimers()
  audioCalls.instance = null
  speechSpeakCalls = []
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      if (url.includes('/spikes/tts')) {
        return Promise.resolve({ ok: true, json: async () => ({ available: false }) })
      }
      if (url.includes('/audio/sample')) {
        return Promise.resolve({ ok: true, blob: async () => new Blob([new Uint8Array([1])]) })
      }
      return Promise.resolve({ ok: false })
    }),
  )
  vi.stubGlobal('Audio', MockAudio)
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn().mockReturnValue('blob:test'),
    revokeObjectURL: vi.fn(),
  })
  vi.stubGlobal('speechSynthesis', speechSynthMock)
  // SpeechSynthesisUtterance shim — just an object that captures `.onend`.
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      text: string
      onend: (() => void) | null = null
      constructor(text: string) {
        this.text = text
      }
    },
  )
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('SpikeFindingsBlock — FR-18 engine chip transitions', () => {
  it('chip shows "Playing Kokoro…" while Kokoro plays, then "Playing Web Speech…" on ended, then clears 1s after Web Speech onend', async () => {
    const wrap = mount(SpikeFindingsBlock)
    await flushPromises() // resolve initial fetch

    await wrap.find('[data-testid="listen-comparison"]').trigger('click')
    await flushPromises()

    // Kokoro chip up
    let chip = wrap.find('[data-testid="engine-chip"]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toMatch(/^Playing Kokoro/)
    expect(chip.classes()).toContain('bc-chip--engine')

    // Fire Kokoro `ended` → chip transitions to Web Speech
    expect(audioCalls.instance).toBeTruthy()
    audioCalls.instance!.ended?.()
    await flushPromises()
    chip = wrap.find('[data-testid="engine-chip"]')
    expect(chip.text()).toMatch(/^Playing Web Speech/)
    expect(chip.classes()).toContain('bc-chip--engine')

    // Fire Web Speech `onend` → chip clears after 1s
    expect(speechSpeakCalls.length).toBe(1)
    speechSpeakCalls[0].onend?.()
    await flushPromises()
    expect(wrap.find('[data-testid="engine-chip"]').exists()).toBe(true) // not yet cleared
    vi.advanceTimersByTime(1000)
    await flushPromises()
    expect(wrap.find('[data-testid="engine-chip"]').exists()).toBe(false)
  })
})
