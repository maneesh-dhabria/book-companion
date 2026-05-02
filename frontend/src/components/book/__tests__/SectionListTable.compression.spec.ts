import { describe, it, expect } from 'vitest'
import { formatCompression } from '../SectionListTable.formatters'

describe('formatCompression', () => {
  it('rounds 15.5 to ~15%', () => expect(formatCompression(15.5)).toBe('~15%'))
  it('rounds 47.8 to ~50%', () => expect(formatCompression(47.8)).toBe('~50%'))
  it('rounds 3.1 to ~5%', () => expect(formatCompression(3.1)).toBe('~5%'))
  it('rounds 0 to ~0%', () => expect(formatCompression(0)).toBe('~0%'))
  it('rounds 62 to ~60%', () => expect(formatCompression(62)).toBe('~60%'))
  it('rounds 2.4 to ~0%', () => expect(formatCompression(2.4)).toBe('~0%'))
  it('returns em-dash for null/undefined', () => {
    expect(formatCompression(null)).toBe('—')
    expect(formatCompression(undefined)).toBe('—')
  })
})
