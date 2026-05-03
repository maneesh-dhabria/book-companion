import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AudioInventoryItem } from '@/api/audio'

vi.mock('@/api/audio', () => ({
  audioApi: {
    deleteOne: vi.fn(),
    mp3Url: (bookId: number, ct: string, cid: number) =>
      `/api/v1/books/${bookId}/audio/${ct}/${cid}.mp3`,
  },
}))

import { audioApi } from '@/api/audio'
import AudioFileRow from '@/components/audio/AudioFileRow.vue'
import { useUiStore } from '@/stores/ui'

const SAMPLE: AudioInventoryItem = {
  content_type: 'section_summary',
  content_id: 42,
  voice: 'af_sarah',
  engine: 'kokoro',
  url: '/api/v1/books/1/audio/section_summary/42.mp3',
  size_bytes: 100000,
  duration_seconds: 120,
  sentence_count: 30,
  source_hash: 'abc',
  generated_at: '2026-05-03T00:00:00Z',
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('AudioFileRow', () => {
  it('renders Play, Download, Delete', () => {
    const wrap = mount(AudioFileRow, { props: { bookId: 1, file: SAMPLE } })
    expect(wrap.find('[data-testid="play"]').exists()).toBe(true)
    const dl = wrap.find('a[data-testid="download"]')
    expect(dl.exists()).toBe(true)
    expect(dl.attributes('href')).toContain('section_summary/42.mp3')
    expect(wrap.find('button[data-testid="delete-row"]').exists()).toBe(true)
  })

  it('Delete success calls API and emits removed', async () => {
    ;(audioApi.deleteOne as ReturnType<typeof vi.fn>).mockResolvedValueOnce(undefined)
    const wrap = mount(AudioFileRow, { props: { bookId: 1, file: SAMPLE } })
    await wrap.find('button[data-testid="delete-row"]').trigger('click')
    await wrap.find('button[data-testid="confirm-delete"]').trigger('click')
    await flushPromises()
    expect(audioApi.deleteOne).toHaveBeenCalledWith(1, 'section_summary', 42)
    expect(wrap.emitted().removed).toBeTruthy()
  })

  it('Delete 409 does not emit removed and shows toast', async () => {
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    ;(audioApi.deleteOne as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      status: 409,
      message: 'audio_job_in_progress',
    })
    const wrap = mount(AudioFileRow, { props: { bookId: 1, file: SAMPLE } })
    await wrap.find('button[data-testid="delete-row"]').trigger('click')
    await wrap.find('button[data-testid="confirm-delete"]').trigger('click')
    await flushPromises()
    expect(wrap.emitted().removed).toBeFalsy()
    expect(toastSpy).toHaveBeenCalled()
  })

  it('clicking Play emits play with file', async () => {
    const wrap = mount(AudioFileRow, { props: { bookId: 1, file: SAMPLE } })
    await wrap.find('[data-testid="play"]').trigger('click')
    expect(wrap.emitted().play).toBeTruthy()
  })
})
