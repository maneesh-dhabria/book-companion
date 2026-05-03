import { describe, expect, it } from 'vitest'

import type { AudioContentType } from '@/api/audio'
import type { TtsContentType } from '@/stores/ttsPlayer'

/**
 * Regression: the persistable subset (`AudioContentType`) is narrower than
 * the runtime engine-routing union (`TtsContentType`). The intersection must
 * round-trip cleanly so any code that does engine routing then persists state
 * (lookup, position) doesn't get a backend 400 on `'annotation'`.
 *
 * Subset relationship: every AudioContentType is also a TtsContentType, but
 * not the reverse — `'annotation'` is runtime-only (Web Speech, no persist).
 */
describe('AudioContentType ⊂ TtsContentType (regression)', () => {
  it('every AudioContentType is assignable to TtsContentType', () => {
    const allPersisted: AudioContentType[] = [
      'section_summary',
      'book_summary',
      'section_content',
      'annotations_playlist',
    ]
    for (const v of allPersisted) {
      const _coerced: TtsContentType = v
      expect(typeof _coerced).toBe('string')
    }
  })

  it('annotations_playlist round-trips through both unions', () => {
    const ttsType: TtsContentType = 'annotations_playlist'
    const apiType: AudioContentType = ttsType as AudioContentType
    expect(apiType).toBe('annotations_playlist')
  })
})
