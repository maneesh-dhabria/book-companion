import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { audioApi } from '@/api/audio'
import {
  useBookAudioMap,
  _resetBookAudioMapCache,
} from '@/composables/useBookAudioMap'

beforeEach(() => {
  _resetBookAudioMapCache()
  vi.restoreAllMocks()
})

describe('useBookAudioMap (P14, FR-C20)', () => {
  it('fetches once per bookId across multiple call sites', async () => {
    const spy = vi.spyOn(audioApi, 'sectionsByBook').mockResolvedValue({
      book_id: 1,
      sections: [
        { section_id: 11, has_mp3: true, engine: 'kokoro' },
        { section_id: 12, has_mp3: false, engine: null },
      ],
    })
    const a = useBookAudioMap(1)
    const b = useBookAudioMap(1)
    await flushPromises()
    expect(spy).toHaveBeenCalledTimes(1)
    expect(a.ready.value).toBe(true)
    expect(b.ready.value).toBe(true)
    expect(a.map.value[11]).toEqual({ has_mp3: true, engine: 'kokoro' })
    expect(b.map.value[12]).toEqual({ has_mp3: false, engine: null })
  })

  it('a different bookId triggers a second fetch', async () => {
    const spy = vi.spyOn(audioApi, 'sectionsByBook').mockResolvedValue({
      book_id: 1,
      sections: [],
    })
    useBookAudioMap(1)
    useBookAudioMap(2)
    await flushPromises()
    expect(spy).toHaveBeenCalledTimes(2)
    expect(spy).toHaveBeenCalledWith(1)
    expect(spy).toHaveBeenCalledWith(2)
  })

  it('exposes failed=true and empty map when API errors', async () => {
    vi.spyOn(audioApi, 'sectionsByBook').mockRejectedValue(new Error('404'))
    const r = useBookAudioMap(1)
    await flushPromises()
    expect(r.failed.value).toBe(true)
    expect(r.map.value).toEqual({})
    expect(r.ready.value).toBe(true)
  })

  it('cached state is returned synchronously on subsequent calls', async () => {
    vi.spyOn(audioApi, 'sectionsByBook').mockResolvedValue({
      book_id: 5,
      sections: [{ section_id: 99, has_mp3: true, engine: 'kokoro' }],
    })
    useBookAudioMap(5)
    await flushPromises()
    const r = useBookAudioMap(5)
    expect(r.ready.value).toBe(true)
    expect(r.map.value[99]).toEqual({ has_mp3: true, engine: 'kokoro' })
  })
})
