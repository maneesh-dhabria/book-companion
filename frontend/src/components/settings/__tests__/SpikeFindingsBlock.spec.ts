import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import SpikeFindingsBlock from '@/components/settings/SpikeFindingsBlock.vue'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('SpikeFindingsBlock', () => {
  it('renders spike findings when available', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          available: true,
          path: 'docs/spikes/2026-05-15-tts-engine-spike.md',
          content_md: '# Findings\n\nKokoro sounded richer.',
        }),
      }),
    )
    const wrap = mount(SpikeFindingsBlock)
    await flushPromises()
    expect(wrap.text()).toContain('Kokoro sounded richer')
    expect(wrap.find('button[data-testid="listen-comparison"]').exists()).toBe(true)
  })

  it('renders run-spike message when not available', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ available: false }) }),
    )
    const wrap = mount(SpikeFindingsBlock)
    await flushPromises()
    expect(wrap.text()).toContain('Spike not yet run')
    expect(wrap.text()).toContain('bookcompanion spike tts')
  })
})
