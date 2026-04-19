import { describe, expect, it } from 'vitest'
import { classifyLink, type LinkClass } from '../link-policy'

describe('classifyLink', () => {
  const cases: Array<[string, LinkClass]> = [
    ['#', 'internal-anchor'],
    ['#section-5', 'internal-anchor'],
    ['http://a.com', 'external'],
    ['https://a.com', 'external'],
    ['mailto:x@y', 'external'],
    ['//cdn.com/x', 'external'],
    ['./ch2.xhtml', 'other'],
    ['../appendix.xhtml', 'other'],
    ['javascript:alert(1)', 'other'],
    ['data:text/html,...', 'other'],
    ['', 'other'],
    ['   ', 'other'],
  ]
  it.each(cases)('classifies %s as %s', (href, expected) => {
    expect(classifyLink(href)).toBe(expected)
  })
})
