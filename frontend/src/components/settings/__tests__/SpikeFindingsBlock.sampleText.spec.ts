import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import SpikeFindingsBlock from '@/components/settings/SpikeFindingsBlock.vue'

const audioBodies: string[] = []

const speechSynthMock = {
  speak: vi.fn(),
  cancel: vi.fn(),
  getVoices: vi.fn().mockReturnValue([]),
}

beforeEach(() => {
  audioBodies.length = 0
  vi.useFakeTimers()
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes('/spikes/tts')) {
        return Promise.resolve({ ok: true, json: async () => ({ available: false }) })
      }
      if (url.includes('/books/1') && !url.includes('/audio')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            sections: [
              {
                id: 1,
                content_md:
                  '**The First Principle** is that you _must not fool yourself_, and you are the easiest person to fool. Continue with extra prose to comfortably exceed the 280 char limit so we can verify the slice operation does its job correctly across multiple sentences and additional fluff text right here.',
              },
            ],
          }),
        })
      }
      if (url.includes('/audio/sample')) {
        if (init?.body) audioBodies.push(String(init.body))
        return Promise.resolve({ ok: false })
      }
      return Promise.resolve({ ok: false })
    }),
  )
  // Class-stubs for new Audio + utterance, plus URL helpers (so the click
  // handler doesn't crash even though we make /audio/sample fail and skip
  // straight to Web Speech).
  vi.stubGlobal('Audio', class { addEventListener() {} play() { return Promise.resolve() } })
  vi.stubGlobal('URL', { createObjectURL: vi.fn(), revokeObjectURL: vi.fn() })
  vi.stubGlobal('speechSynthesis', speechSynthMock)
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

describe('SpikeFindingsBlock — FR-19 sample text from book.sections[0]', () => {
  it('with bookId prop, fetches book and uses markdown-stripped section[0] (≤280 chars)', async () => {
    const wrap = mount(SpikeFindingsBlock, { props: { bookId: 1 } })
    await flushPromises()

    await wrap.find('[data-testid="listen-comparison"]').trigger('click')
    await flushPromises()

    expect(audioBodies.length).toBe(1)
    const body = JSON.parse(audioBodies[0]) as { text: string }
    expect(body.text.length).toBeLessThanOrEqual(280)
    expect(body.text).toMatch(/^The First Principle is that you must not fool yourself/)
    // Markdown markers stripped:
    expect(body.text).not.toContain('**')
    expect(body.text).not.toContain('_must not fool yourself_')
  })

  it('without bookId prop, uses pangram fallback', async () => {
    const wrap = mount(SpikeFindingsBlock)
    await flushPromises()

    await wrap.find('[data-testid="listen-comparison"]').trigger('click')
    await flushPromises()

    expect(audioBodies.length).toBe(1)
    const body = JSON.parse(audioBodies[0]) as { text: string }
    expect(body.text.toLowerCase()).toContain('the quick brown fox')
  })
})
