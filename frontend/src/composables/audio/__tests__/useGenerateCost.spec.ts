import { describe, expect, it } from 'vitest'

import { estimateGenerateCost } from '@/composables/audio/useGenerateCost'

describe('estimateGenerateCost', () => {
  it('formula: minutes = total*0.20, megabytes = total*3.0', () => {
    const r = estimateGenerateCost({ totalUnits: 47 })
    expect(r.minutes).toBeCloseTo(47 * 0.2, 5)
    expect(r.megabytes).toBe(47 * 3.0)
  })

  it('zero units → zeros', () => {
    expect(estimateGenerateCost({ totalUnits: 0 })).toEqual({ minutes: 0, megabytes: 0 })
  })
})
