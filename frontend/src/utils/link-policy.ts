export type LinkClass = 'internal-anchor' | 'external' | 'other'

// Regex catalog for F2 — EPUB-specific in-book links that should be
// stripped (rendered as <span>), not turned into clickable hrefs that
// 404 or navigate outside the reader. These patterns match the raw href
// before link normalization; the MarkdownRenderer's applyLinkPolicy
// replaces any matching anchor with a plain span.
const EPUB_INTERNAL_PATTERNS: RegExp[] = [
  /\.xhtml(#|$)/i,
  /\.htm(#|$)/i,
  /^#?filepos\d+/i,
  /^#?chap\d+/i,
  /^#?pref\d+/i,
  /^#?sect\d+/i,
]

export function classifyLink(href: string): LinkClass {
  const h = (href ?? '').trim()
  if (!h) return 'other'
  if (h.startsWith('#')) return 'internal-anchor'
  if (EPUB_INTERNAL_PATTERNS.some((re) => re.test(h))) return 'internal-anchor'
  if (/^https?:\/\//i.test(h)) return 'external'
  if (h.toLowerCase().startsWith('mailto:')) return 'external'
  if (h.startsWith('//')) return 'external'
  return 'other'
}
