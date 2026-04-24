import { describe, expect, it } from 'vitest'
import { contrastGrade, contrastRatio, relativeLuminance } from '../contrast'

describe('contrast', () => {
  it('computes max ratio for black on white', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBe(21)
  })

  it('computes 1:1 for same colour', () => {
    expect(contrastRatio('#888888', '#888888')).toBe(1)
  })

  it('accepts 3-digit hex', () => {
    expect(contrastRatio('#000', '#fff')).toBe(21)
  })

  it('grades AAA for ratios >= 7', () => {
    expect(contrastGrade(7.1)).toBe('AAA')
  })

  it('grades AA for 4.5 <= r < 7', () => {
    expect(contrastGrade(4.5)).toBe('AA')
  })

  it('grades AA-large for 3 <= r < 4.5', () => {
    expect(contrastGrade(3.5)).toBe('AA-large')
  })

  it('grades FAIL for < 3', () => {
    expect(contrastGrade(2.5)).toBe('FAIL')
  })

  it('luminance of white is 1, black is 0', () => {
    expect(Math.round(relativeLuminance('#ffffff') * 100) / 100).toBe(1)
    expect(relativeLuminance('#000000')).toBe(0)
  })

  it('throws on invalid hex', () => {
    expect(() => contrastRatio('#ggg', '#fff')).toThrow(/Invalid hex/)
  })
})
