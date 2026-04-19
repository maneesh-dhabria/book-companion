export type LinkClass = 'internal-anchor' | 'external' | 'other'

export function classifyLink(href: string): LinkClass {
  const h = (href ?? '').trim()
  if (!h) return 'other'
  if (h.startsWith('#')) return 'internal-anchor'
  if (/^https?:\/\//i.test(h)) return 'external'
  if (h.toLowerCase().startsWith('mailto:')) return 'external'
  if (h.startsWith('//')) return 'external'
  return 'other'
}
