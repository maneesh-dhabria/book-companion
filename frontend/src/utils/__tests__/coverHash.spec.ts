import { describe, expect, it } from 'vitest'
import { COVER_GRADIENTS, coverGradientFor } from '../coverHash'

describe('coverHash', () => {
  it('returns one of the 8 shipped gradients', () => {
    const ids = new Set(COVER_GRADIENTS.map((g) => g.id))
    expect(ids.size).toBe(8)
    expect(ids.has(coverGradientFor('A Title').id)).toBe(true)
  })

  it('is deterministic for the same input', () => {
    expect(coverGradientFor('Porter')).toEqual(coverGradientFor('Porter'))
  })

  it('falls back to "untitled" for null/empty', () => {
    expect(coverGradientFor('')).toEqual(coverGradientFor(null))
    expect(coverGradientFor(undefined)).toEqual(coverGradientFor('   '))
  })

  it('distributes across gradients for different titles', () => {
    const ids = new Set<string>()
    for (let i = 0; i < 50; i++) ids.add(coverGradientFor(`Book ${i}`).id)
    expect(ids.size).toBeGreaterThan(1)
  })
})
