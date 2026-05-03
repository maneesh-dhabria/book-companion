import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import VoiceSampleButton from '@/components/settings/VoiceSampleButton.vue'

beforeEach(() => {
  vi.stubGlobal('speechSynthesis', {
    speak: vi.fn(),
    cancel: vi.fn(),
    getVoices: () => [],
  })
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    vi.fn(function (this: { text: string }, t: string) {
      this.text = t
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('VoiceSampleButton', () => {
  it('Web Speech sample uses speechSynthesis directly', async () => {
    const wrap = mount(VoiceSampleButton, {
      props: { engine: 'web-speech', voice: 'Samantha' },
    })
    await wrap.find('button').trigger('click')
    expect(window.speechSynthesis.speak).toHaveBeenCalled()
  })

  it('Kokoro sample POSTs /audio/sample', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => new Blob([new Uint8Array([0x49, 0x44, 0x33])], { type: 'audio/mpeg' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    // Audio API stub
    vi.stubGlobal(
      'Audio',
      vi.fn(function () {
        return {
          play: vi.fn().mockResolvedValue(undefined),
          pause: vi.fn(),
          addEventListener: vi.fn(),
        }
      }),
    )
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })

    const wrap = mount(VoiceSampleButton, {
      props: { engine: 'kokoro', voice: 'af_sarah' },
    })
    await wrap.find('button').trigger('click')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/audio/sample',
      expect.objectContaining({ method: 'POST' }),
    )
    const body = JSON.parse((fetchMock.mock.calls[0][1] as { body: string }).body)
    expect(body.voice).toBe('af_sarah')
  })
})
