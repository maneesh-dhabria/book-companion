import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: {
    inventory: vi.fn().mockResolvedValue({
      book_id: 1,
      files: [],
      coverage: { total: 47, generated: 0 },
    }),
  },
}))

import AudioTab from '@/components/audio/AudioTab.vue'
import { useAudioJobStore } from '@/stores/audioJob'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('AudioTab cancel-job', () => {
  it('Cancel button POSTs /jobs/{id}/cancel', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response('', { status: 200 }))
    vi.stubGlobal('fetch', fetchSpy)

    const jobStore = useAudioJobStore()
    jobStore.setActiveJob({ id: 187, status: 'RUNNING', completed: 12, total: 47 })

    const wrap = mount(AudioTab, { props: { bookId: 1 } })
    await flushPromises()

    await wrap.find('button[data-testid="cancel-job"]').trigger('click')
    await flushPromises()

    const calls = fetchSpy.mock.calls
    const cancelCall = calls.find((c) => String(c[0]).includes('/jobs/187/cancel'))
    expect(cancelCall).toBeTruthy()
    expect((cancelCall![1] as RequestInit).method).toBe('POST')
  })
})
