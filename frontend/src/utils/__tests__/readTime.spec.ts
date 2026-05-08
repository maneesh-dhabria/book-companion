import { describe, it, expect } from 'vitest'
import { formatReadTime, formatReadTimeSum } from '@/utils/readTime'

describe('formatReadTime', () => {
  it.each([
    [0, '<1 min'],
    [-1, '<1 min'],
    [1, '1 min'],
    [1100, '1 min'],
    [1101, '2 min'],
    [6600, '6 min'],
  ])('formatReadTime(%i) === %s', (input, expected) => {
    expect(formatReadTime(input)).toBe(expected)
  })
})

describe('formatReadTimeSum', () => {
  it('empty array → <1 min', () => {
    expect(formatReadTimeSum([])).toBe('<1 min')
  })

  it('all zero → <1 min', () => {
    expect(formatReadTimeSum([0, 0])).toBe('<1 min')
  })

  it('negative values are clamped to zero', () => {
    expect(formatReadTimeSum([-1, -100])).toBe('<1 min')
  })

  it('[60001] → 55 min (< 60min, ceil)', () => {
    // 60001 / 1100 = 54.55 → ceil 55
    expect(formatReadTimeSum([60001])).toBe('55 min')
  })

  it('[3300, 3300] → 6 min', () => {
    expect(formatReadTimeSum([3300, 3300])).toBe('6 min')
  })

  it('[66000] → 1h (exact 60 min boundary)', () => {
    expect(formatReadTimeSum([66000])).toBe('1h')
  })

  it('[66001] → 1h 1m', () => {
    expect(formatReadTimeSum([66001])).toBe('1h 1m')
  })

  it('[60001, 60001] → 1h 50m', () => {
    // 120002 / 1100 = 109.09 → ceil 110 → 1h 50m
    expect(formatReadTimeSum([60001, 60001])).toBe('1h 50m')
  })
})
