import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AudioInventoryItem } from '@/api/audio'

vi.mock('@/api/audio', () => ({
  audioApi: { inventory: vi.fn() },
}))

import { audioApi } from '@/api/audio'
import AudioTab from '@/components/audio/AudioTab.vue'
import { useAudioJobStore } from '@/stores/audioJob'

const SAMPLE_FILE: AudioInventoryItem = {
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

describe('AudioTab', () => {
  it('renders no-audio state with Generate CTA when inventory empty', async () => {
    ;(audioApi.inventory as ReturnType<typeof vi.fn>).mockResolvedValue({
      book_id: 1,
      files: [],
      coverage: { total: 47, generated: 0 },
    })
    const wrap = mount(AudioTab, { props: { bookId: 1 } })
    await flushPromises()
    expect(wrap.text()).toContain('No audio yet')
    expect(wrap.find('button[data-testid="generate-audio"]').exists()).toBe(true)
  })

  it('renders partial state with coverage bar', async () => {
    ;(audioApi.inventory as ReturnType<typeof vi.fn>).mockResolvedValue({
      book_id: 1,
      files: Array.from({ length: 3 }, (_, i) => ({ ...SAMPLE_FILE, content_id: i })),
      coverage: { total: 47, generated: 12 },
    })
    const wrap = mount(AudioTab, { props: { bookId: 1 } })
    await flushPromises()
    expect(wrap.text()).toContain('12 of 47')
    expect(wrap.find('[data-testid="coverage-bar"]').exists()).toBe(true)
  })

  it('renders full state', async () => {
    ;(audioApi.inventory as ReturnType<typeof vi.fn>).mockResolvedValue({
      book_id: 1,
      files: Array.from({ length: 47 }, (_, i) => ({ ...SAMPLE_FILE, content_id: i })),
      coverage: { total: 47, generated: 47 },
    })
    const wrap = mount(AudioTab, { props: { bookId: 1 } })
    await flushPromises()
    expect(wrap.text()).toContain('All 47')
  })

  it('renders generating state with progress + Cancel button', async () => {
    ;(audioApi.inventory as ReturnType<typeof vi.fn>).mockResolvedValue({
      book_id: 1,
      files: [],
      coverage: { total: 47, generated: 0 },
    })
    const jobStore = useAudioJobStore()
    jobStore.setActiveJob({ id: 187, status: 'RUNNING', completed: 12, total: 47 })
    const wrap = mount(AudioTab, { props: { bookId: 1 } })
    await flushPromises()
    expect(wrap.text()).toContain('12 / 47')
    expect(wrap.find('button[data-testid="cancel-job"]').exists()).toBe(true)
  })
})
