/**
 * WCAG 2.x contrast ratio helper.
 *
 * Accepts two 6- or 3-digit hex colours (with or without the leading ``#``)
 * and returns a contrast ratio in the range [1, 21]. Rounded to 2 decimals.
 * Invalid input throws so call sites must catch or guard.
 */
function normalizeHex(hex: string): string {
  const h = hex.replace(/^#/, '').trim()
  if (h.length === 3) {
    return h
      .split('')
      .map((c) => c + c)
      .join('')
  }
  if (h.length !== 6) throw new Error(`Invalid hex colour: ${hex}`)
  return h
}

function hexToRgb(hex: string): [number, number, number] {
  const h = normalizeHex(hex)
  if (!/^[0-9a-fA-F]{6}$/.test(h)) throw new Error(`Invalid hex colour: ${hex}`)
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

function channelLinear(c: number): number {
  const s = c / 255
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
}

export function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex)
  return (
    0.2126 * channelLinear(r) + 0.7152 * channelLinear(g) + 0.0722 * channelLinear(b)
  )
}

export function contrastRatio(fg: string, bg: string): number {
  const l1 = relativeLuminance(fg)
  const l2 = relativeLuminance(bg)
  const [lighter, darker] = l1 > l2 ? [l1, l2] : [l2, l1]
  const ratio = (lighter + 0.05) / (darker + 0.05)
  return Math.round(ratio * 100) / 100
}

export type ContrastGrade = 'AAA' | 'AA' | 'AA-large' | 'FAIL'

export function contrastGrade(ratio: number): ContrastGrade {
  if (ratio >= 7) return 'AAA'
  if (ratio >= 4.5) return 'AA'
  if (ratio >= 3) return 'AA-large'
  return 'FAIL'
}
