// Read-time formatters. ~250 wpm × 4.5 chars/word ≈ 1100 chars/minute.
const CHARS_PER_MINUTE = 1100

export function formatReadTime(chars: number): string {
  if (!chars || chars <= 0) return '<1 min'
  const minutes = Math.ceil(chars / CHARS_PER_MINUTE)
  return `${minutes} min`
}

export function formatReadTimeSum(charsList: ReadonlyArray<number>): string {
  const total = charsList.reduce((acc, c) => acc + (c > 0 ? c : 0), 0)
  if (total <= 0) return '<1 min'
  const minutes = Math.ceil(total / CHARS_PER_MINUTE)
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}
