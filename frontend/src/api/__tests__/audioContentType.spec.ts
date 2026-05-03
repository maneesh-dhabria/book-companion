import { describe, expect, it } from 'vitest'

import type { AudioContentType } from '@/api/audio'
import type { TtsContentType } from '@/stores/ttsPlayer'

describe('AudioContentType ↔ TtsContentType compatibility', () => {
  it('every TtsContentType value is assignable to AudioContentType (regression)', () => {
    // Compile-time guarantee via assignment — if the union diverges, tsc fails.
    const allTtsValues: TtsContentType[] = [
      'section_summary',
      'book_summary',
      'annotation',
      'section',
      'annotations_playlist',
    ]
    for (const v of allTtsValues) {
      const _coerced: AudioContentType = v
      expect(typeof _coerced).toBe('string')
    }
  })

  it('annotations_playlist round-trips through both unions', () => {
    const ttsType: TtsContentType = 'annotations_playlist'
    const apiType: AudioContentType = ttsType
    expect(apiType).toBe('annotations_playlist')
  })
})
