import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import SettingsTtsPanel from '@/components/settings/SettingsTtsPanel.vue'

beforeEach(() => {
  vi.stubGlobal('speechSynthesis', {
    getVoices: () => [{ name: 'Samantha' }, { name: 'Alex' }],
    speak: vi.fn(),
    cancel: vi.fn(),
  })
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubFetch() {
  const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (url === '/api/v1/settings/tts' && (!init || init.method === undefined)) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          engine: 'web-speech',
          voice: 'Samantha',
          default_speed: 1.0,
          auto_advance: true,
        }),
      })
    }
    if (url === '/api/v1/settings/tts/status') {
      return Promise.resolve({ ok: true, json: async () => ({ status: 'cold' }) })
    }
    if (url === '/api/v1/spikes/tts') {
      return Promise.resolve({ ok: true, json: async () => ({ available: false }) })
    }
    if (url === '/api/v1/settings/tts' && init?.method === 'PUT') {
      return Promise.resolve({ ok: true, json: async () => ({}) })
    }
    return Promise.resolve({ ok: true, json: async () => ({}) })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('SettingsTtsPanel', () => {
  it('renders engine radios', async () => {
    stubFetch()
    const wrap = mount(SettingsTtsPanel)
    await flushPromises()
    expect(wrap.find('input[type="radio"][value="web-speech"]').exists()).toBe(true)
    expect(wrap.find('input[type="radio"][value="kokoro"]').exists()).toBe(true)
  })

  it('PUT settings on save', async () => {
    const fetchMock = stubFetch()
    const wrap = mount(SettingsTtsPanel)
    await flushPromises()
    await wrap.find('input[type="radio"][value="kokoro"]').trigger('change')
    await wrap.find('button[data-testid="save"]').trigger('click')
    await flushPromises()
    const putCall = fetchMock.mock.calls.find(
      ([u, init]) =>
        u === '/api/v1/settings/tts' && (init as RequestInit | undefined)?.method === 'PUT',
    )
    expect(putCall).toBeTruthy()
  })
})
