import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import KokoroStatusIndicator from '@/components/settings/KokoroStatusIndicator.vue'

beforeEach(() => {
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubFetch(status: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status }) }),
  )
}

describe('KokoroStatusIndicator', () => {
  it.each([
    ['warm', 'Kokoro: warm'],
    ['cold', 'Kokoro: cold'],
    ['not_downloaded', 'Model not downloaded'],
    ['download_failed', 'Download failed'],
  ])('renders status=%s', async (status, label) => {
    stubFetch(status)
    const wrap = mount(KokoroStatusIndicator)
    await flushPromises()
    expect(wrap.text()).toContain(label)
    wrap.unmount()
  })

  it('Download button visible when not_downloaded', async () => {
    stubFetch('not_downloaded')
    const wrap = mount(KokoroStatusIndicator)
    await flushPromises()
    expect(wrap.find('button[data-testid="download-model"]').exists()).toBe(true)
    wrap.unmount()
  })

  it('Retry button visible when download_failed', async () => {
    stubFetch('download_failed')
    const wrap = mount(KokoroStatusIndicator)
    await flushPromises()
    expect(wrap.find('button[data-testid="retry-download"]').exists()).toBe(true)
    wrap.unmount()
  })
})
