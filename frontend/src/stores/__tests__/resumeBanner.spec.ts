import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useResumeBannerStore } from '@/stores/resumeBanner'

beforeEach(() => {
  setActivePinia(createPinia())
})

function mockResp(body: object | null) {
  return new Response(body == null ? 'null' : JSON.stringify(body), { status: 200 })
}

describe('useResumeBannerStore (FR-B06, FR-B07)', () => {
  it('starts with chosen === null', () => {
    const s = useResumeBannerStore()
    expect(s.chosen).toBe(null)
  })

  it('hydrates with both null → chosen stays null', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResp({}))
    const s = useResumeBannerStore()
    await s.load()
    expect(s.chosen).toBe(null)
  })

  it('reading-only → chosen = reading', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResp({
      last_viewed_at: '2026-05-08T10:00:00Z',
      last_book_id: 1,
      last_section_id: 11,
    }))
    const s = useResumeBannerStore()
    await s.load()
    expect(s.chosen).toBe('reading')
  })

  it('audio-only → chosen = listening', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResp({
      last_audio_at: '2026-05-08T10:00:00Z',
      last_audio_content_type: 'section_summary',
      last_audio_content_id: 99,
    }))
    const s = useResumeBannerStore()
    await s.load()
    expect(s.chosen).toBe('listening')
  })

  it('audio more recent than reading → chosen = listening', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResp({
      last_viewed_at: '2026-05-08T09:00:00Z',
      last_audio_at: '2026-05-08T10:00:00Z',
      last_book_id: 1,
      last_audio_content_type: 'section_summary',
      last_audio_content_id: 99,
    }))
    const s = useResumeBannerStore()
    await s.load()
    expect(s.chosen).toBe('listening')
  })

  it('reading more recent than audio → chosen = reading', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResp({
      last_viewed_at: '2026-05-08T11:00:00Z',
      last_audio_at: '2026-05-08T10:00:00Z',
      last_book_id: 1,
      last_audio_content_type: 'section_summary',
      last_audio_content_id: 99,
    }))
    const s = useResumeBannerStore()
    await s.load()
    expect(s.chosen).toBe('reading')
  })

  it('equal timestamps → reading wins (deterministic tie-break)', async () => {
    const ts = '2026-05-08T10:00:00Z'
    vi.spyOn(global, 'fetch').mockResolvedValue(mockResp({
      last_viewed_at: ts,
      last_audio_at: ts,
      last_book_id: 1,
      last_audio_content_type: 'section_summary',
      last_audio_content_id: 99,
    }))
    const s = useResumeBannerStore()
    await s.load()
    expect(s.chosen).toBe('reading')
  })

  it('API throws → chosen stays null (no toast, no rethrow)', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('network'))
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const s = useResumeBannerStore()
    await s.load()
    expect(s.chosen).toBe(null)
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})
