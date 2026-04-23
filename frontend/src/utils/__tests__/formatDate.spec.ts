import { describe, expect, it } from 'vitest'
import { formatDate } from '../formatDate'

describe('formatDate', () => {
  const now = new Date('2026-04-22T12:00:00Z')

  it('renders "just now" within a minute', () => {
    expect(formatDate(new Date(now.getTime() - 30_000), { now })).toBe('just now')
  })

  it('renders minutes for < 1 hour', () => {
    expect(formatDate(new Date(now.getTime() - 23 * 60_000), { now })).toBe(
      '23 minutes ago',
    )
  })

  it('renders hours for < 1 day', () => {
    expect(formatDate(new Date(now.getTime() - 4 * 3_600_000), { now })).toBe(
      '4 hours ago',
    )
  })

  it('renders days for < 7 days', () => {
    expect(
      formatDate(new Date(now.getTime() - 2 * 86_400_000), { now }),
    ).toBe('2 days ago')
  })

  it('renders absolute for ≥ 7 days', () => {
    expect(formatDate('2026-04-10T00:00:00Z', { now })).toBe('Apr 10, 2026')
  })

  it('respects explicit absolute mode', () => {
    expect(
      formatDate('2026-04-22T11:00:00Z', { now, mode: 'absolute' }),
    ).toBe('Apr 22, 2026')
  })

  it('returns empty string for nullish input', () => {
    expect(formatDate(null)).toBe('')
    expect(formatDate(undefined)).toBe('')
  })

  it('passes through unparseable strings', () => {
    expect(formatDate('not a date')).toBe('not a date')
  })
})
