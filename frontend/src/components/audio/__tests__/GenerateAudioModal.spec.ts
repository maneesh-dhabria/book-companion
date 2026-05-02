import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: { start: vi.fn() },
}))

import { audioApi } from '@/api/audio'
import GenerateAudioModal from '@/components/audio/GenerateAudioModal.vue'
import { useAudioJobStore } from '@/stores/audioJob'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('GenerateAudioModal', () => {
  it('default state: 3 checkboxes ON, includes Annotations + recommended', () => {
    const wrap = mount(GenerateAudioModal, {
      props: { open: true, bookId: 1, totalUnits: 47, totalAnnotations: 5 },
    })
    const checkboxes = wrap.findAll('input[type="checkbox"]')
    expect(checkboxes.length).toBe(3)
    expect(checkboxes.every((c) => (c.element as HTMLInputElement).checked)).toBe(true)
    expect(wrap.text()).toContain('Annotations')
    expect(wrap.text().toLowerCase()).toContain('recommended')
  })

  it('shows cost estimate inline', () => {
    const wrap = mount(GenerateAudioModal, {
      props: { open: true, bookId: 1, totalUnits: 47, totalAnnotations: 0 },
    })
    expect(wrap.text()).toMatch(/min/i)
    expect(wrap.text()).toMatch(/MB/i)
    expect(wrap.text()).toContain('47')
  })

  it('confirm POST joins job on success', async () => {
    ;(audioApi.start as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 187,
      scope: 'all',
      total_units: 47,
    })
    const wrap = mount(GenerateAudioModal, {
      props: { open: true, bookId: 1, totalUnits: 47, totalAnnotations: 0 },
    })
    await wrap.find('button[data-testid="confirm"]').trigger('click')
    await flushPromises()
    expect(useAudioJobStore().activeJob?.id).toBe(187)
  })

  it('409 transparently joins existing job (no error toast)', async () => {
    ;(audioApi.start as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      status: 409,
      body: {
        error: 'audio_job_in_progress',
        existing_job_id: 187,
        scope: 'all',
        started_at: '2026-05-02T14:11:00Z',
      },
    })
    const wrap = mount(GenerateAudioModal, {
      props: { open: true, bookId: 1, totalUnits: 47, totalAnnotations: 0 },
    })
    await wrap.find('button[data-testid="confirm"]').trigger('click')
    await flushPromises()
    expect(useAudioJobStore().activeJob?.id).toBe(187)
  })

  it('renders model-download-required state', () => {
    const wrap = mount(GenerateAudioModal, {
      props: {
        open: true,
        bookId: 1,
        totalUnits: 47,
        totalAnnotations: 0,
        kokoroStatus: 'not_downloaded',
      },
    })
    expect(wrap.find('button[data-testid="download-model"]').exists()).toBe(true)
    expect(wrap.text()).toMatch(/download/i)
  })

  it('renders error state on 503', async () => {
    ;(audioApi.start as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      status: 503,
      body: { error: 'ffmpeg_missing' },
    })
    const wrap = mount(GenerateAudioModal, {
      props: { open: true, bookId: 1, totalUnits: 47, totalAnnotations: 0 },
    })
    await wrap.find('button[data-testid="confirm"]').trigger('click')
    await flushPromises()
    expect(wrap.text()).toMatch(/ffmpeg/i)
  })
})
