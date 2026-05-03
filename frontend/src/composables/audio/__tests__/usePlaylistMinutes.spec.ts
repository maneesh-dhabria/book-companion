import { describe, expect, it } from 'vitest'

import { estimatePlaylistMinutes } from '@/composables/audio/usePlaylistMinutes'

describe('estimatePlaylistMinutes', () => {
  it('formula = ceil((highlights*30 + notes*30)/60)', () => {
    expect(estimatePlaylistMinutes(18, 6)).toBe(Math.ceil((18 * 30 + 6 * 30) / 60))
    expect(estimatePlaylistMinutes(0, 0)).toBe(0)
    expect(estimatePlaylistMinutes(1, 0)).toBe(1)
  })
})
