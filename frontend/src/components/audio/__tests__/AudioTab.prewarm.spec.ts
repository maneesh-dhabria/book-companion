import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import AudioTab from '../AudioTab.vue'

vi.mock('@/api/audio', () => ({
  audioApi: {
    inventory: vi.fn().mockResolvedValue({ files: [], coverage: { total: 0, generated: 0 } }),
  },
}))

type VoicesChangedCb = () => void

interface SynthStub {
  getVoices: ReturnType<typeof vi.fn>
  addEventListener: ReturnType<typeof vi.fn>
  removeEventListener: ReturnType<typeof vi.fn>
  speak: ReturnType<typeof vi.fn>
  cancel: ReturnType<typeof vi.fn>
  __fireVoicesChanged?: VoicesChangedCb
}

function installSpeechSynth(initialVoices: unknown[]): SynthStub {
  const cbs: VoicesChangedCb[] = []
  const stub: SynthStub = {
    getVoices: vi.fn(() => initialVoices),
    addEventListener: vi.fn((evt: string, cb: VoicesChangedCb) => {
      if (evt === 'voiceschanged') cbs.push(cb)
    }),
    removeEventListener: vi.fn(),
    speak: vi.fn(),
    cancel: vi.fn(),
  }
  stub.__fireVoicesChanged = () => cbs.forEach((cb) => cb())
  Object.defineProperty(window, 'speechSynthesis', {
    value: stub,
    configurable: true,
    writable: true,
  })
  return stub
}

describe('AudioTab voice-list pre-warm (FR-08 / D10)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    delete (window as unknown as { speechSynthesis?: unknown }).speechSynthesis
  })

  function mountTab() {
    return mount(AudioTab, {
      props: { bookId: 1 },
      global: {
        stubs: {
          EngineChip: true,
          DifferencePopover: true,
          GenerateAudioModal: true,
        },
      },
    })
  }

  it('voicesReady true immediately when getVoices() returns non-empty', async () => {
    installSpeechSynth([{ name: 'Samantha' }])
    const wrapper = mountTab()
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()
    expect(wrapper.vm.voicesReady).toBe(true)
  })

  it('voicesReady true after voiceschanged fires before timeout', async () => {
    const stub = installSpeechSynth([])
    const wrapper = mountTab()
    await flushPromises()
    expect(wrapper.vm.voicesReady).toBe(false)
    stub.getVoices.mockReturnValue([{ name: 'Karen' }])
    stub.__fireVoicesChanged?.()
    await flushPromises()
    expect(wrapper.vm.voicesReady).toBe(true)
  })

  it('voicesReady true at 500ms timeout when voiceschanged never fires', async () => {
    installSpeechSynth([])
    const wrapper = mountTab()
    await flushPromises()
    expect(wrapper.vm.voicesReady).toBe(false)
    await vi.advanceTimersByTimeAsync(499)
    expect(wrapper.vm.voicesReady).toBe(false)
    await vi.advanceTimersByTimeAsync(2)
    expect(wrapper.vm.voicesReady).toBe(true)
  })
})
