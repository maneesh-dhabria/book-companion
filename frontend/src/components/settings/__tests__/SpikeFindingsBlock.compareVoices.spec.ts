import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SpikeFindingsBlock from '@/components/settings/SpikeFindingsBlock.vue'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('SpikeFindingsBlock — FR-17 Compare voices rename + fallback rewrite', () => {
  it('renders the "Compare voices" heading and contains no "Spike" substring', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ available: false }) }),
    )
    const wrap = mount(SpikeFindingsBlock)
    await flushPromises()

    const html = wrap.html()
    expect(html).toContain('Compare voices')
    expect(html).not.toContain('Spike')
    expect(html).not.toContain('spike')
  })

  it('listen-comparison button is mounted even when no spike data is available', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ available: false }) }),
    )
    const wrap = mount(SpikeFindingsBlock)
    await flushPromises()

    const btn = wrap.find('[data-testid="listen-comparison"]')
    expect(btn.exists()).toBe(true)
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('fallback paragraph contains the user-facing copy (not the dev-only `bookcompanion spike tts` reference)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ available: false }) }),
    )
    const wrap = mount(SpikeFindingsBlock)
    await flushPromises()

    const text = wrap.text()
    expect(text).toMatch(/hear .* both engines|click to compare|kokoro.*web speech/i)
    expect(text.toLowerCase()).not.toContain('bookcompanion spike tts')
  })
})
