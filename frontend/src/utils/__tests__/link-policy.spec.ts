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
    // After T23 the EPUB patterns are explicitly internal-anchor; both
    // classes still map to the same 'strip to span' behavior in
    // MarkdownRenderer.applyLinkPolicy.
    ['./ch2.xhtml', 'internal-anchor'],
    ['../appendix.xhtml', 'internal-anchor'],
    ['./part1.htm', 'internal-anchor'],
    ['CR!1234_split_004.htm.xhtml#filepos2205', 'internal-anchor'],
    ['javascript:alert(1)', 'other'],
    ['data:text/html,...', 'other'],
    ['', 'other'],
    ['   ', 'other'],
  ]
  it.each(cases)('classifies %s as %s', (href, expected) => {
    expect(classifyLink(href)).toBe(expected)
  })
})
