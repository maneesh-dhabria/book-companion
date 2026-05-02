import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: { start: vi.fn().mockResolvedValue({ job_id: 187, scope: 'sections', total_units: 1 }) },
}))

import { audioApi } from '@/api/audio'
import StaleSourceBanner from '@/components/audio/StaleSourceBanner.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

const cases: [string, string][] = [
  ['source_changed', 'Source updated since audio generated'],
  ['sanitizer_upgraded', 'Audio engine updated'],
  ['segmenter_drift', 'Sentence boundaries shifted'],
]

describe('StaleSourceBanner', () => {
  it.each(cases)('renders correct copy for stale_reason=%s', (reason, expected) => {
    const wrap = mount(StaleSourceBanner, {
      props: {
        staleReason: reason as 'source_changed',
        bookId: 1,
        contentType: 'section_summary',
        contentId: 42,
      },
    })
    expect(wrap.text()).toContain(expected)
  })

  it('Regenerate click queues audio job', async () => {
    const wrap = mount(StaleSourceBanner, {
      props: {
        staleReason: 'source_changed',
        bookId: 1,
        contentType: 'section_summary',
        contentId: 42,
      },
    })
    await wrap.find('button[data-testid="regenerate"]').trigger('click')
    expect(audioApi.start).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ scope: 'sections', section_ids: [42] }),
    )
  })
})
