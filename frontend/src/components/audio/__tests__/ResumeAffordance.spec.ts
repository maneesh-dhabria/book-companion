import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audioPosition', () => ({
  audioPositionApi: { get: vi.fn(), put: vi.fn() },
  getBrowserId: () => 'test-browser',
}))

import { audioPositionApi } from '@/api/audioPosition'
import ResumeAffordance from '@/components/audio/ResumeAffordance.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('ResumeAffordance', () => {
  it('shows resume + start when position exists and audio complete', async () => {
    vi.mocked(audioPositionApi.get).mockResolvedValueOnce({
      sentence_index: 16,
      updated_at: '2026-05-01T00:00:00Z',
      has_other_browser: false,
    })
    const wrap = mount(ResumeAffordance, {
      props: {
        contentType: 'section_summary',
        contentId: 42,
        audioStatus: 'complete',
        totalSentences: 47,
      },
    })
    await flushPromises()
    expect(wrap.text()).toContain('Resume from sentence 17 of 47')
    expect(wrap.find('[data-testid="start-from-beginning"]').exists()).toBe(true)
  })

  it('hides when no position', async () => {
    vi.mocked(audioPositionApi.get).mockResolvedValueOnce(null)
    const wrap = mount(ResumeAffordance, {
      props: {
        contentType: 'section_summary',
        contentId: 42,
        audioStatus: 'complete',
        totalSentences: 47,
      },
    })
    await flushPromises()
    expect(wrap.find('.bc-resume').exists()).toBe(false)
  })

  it('shows other-browser hint when has_other_browser', async () => {
    vi.mocked(audioPositionApi.get).mockResolvedValueOnce({
      sentence_index: 16,
      updated_at: '2026-05-01T00:00:00Z',
      has_other_browser: true,
      other_browser_updated_at: '2026-05-01T22:10:00Z',
    })
    const wrap = mount(ResumeAffordance, {
      props: {
        contentType: 'section_summary',
        contentId: 42,
        audioStatus: 'complete',
        totalSentences: 47,
      },
    })
    await flushPromises()
    expect(wrap.text()).toContain('different browser')
  })
})
