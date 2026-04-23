/**
 * Hybrid date formatter — relative for the last 7 days, absolute otherwise.
 *
 * Output examples:
 *   - Under 1 minute:  "just now"
 *   - Under 1 hour:    "23 minutes ago"
 *   - Under 24 hours:  "4 hours ago"
 *   - Under 7 days:    "2 days ago"
 *   - 7 days or more:  "Apr 10, 2026"
 *
 * Mode can be forced via `mode: 'relative' | 'absolute' | 'auto'` (default).
 */

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

function formatAbsolute(d: Date): string {
  return `${MONTH_NAMES[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
}

function formatRelative(delta: number): string {
  if (delta < 60_000) return 'just now'
  const minutes = Math.floor(delta / 60_000)
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(delta / 3_600_000)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(delta / 86_400_000)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

export function formatDate(
  input: string | Date | null | undefined,
  opts: { mode?: 'auto' | 'relative' | 'absolute'; now?: Date } = {},
): string {
  if (input == null || input === '') return ''
  const d = input instanceof Date ? input : new Date(input)
  if (Number.isNaN(d.getTime())) return typeof input === 'string' ? input : ''
  const mode = opts.mode ?? 'auto'
  const now = opts.now ?? new Date()
  if (mode === 'absolute') return formatAbsolute(d)
  const delta = now.getTime() - d.getTime()
  if (mode === 'relative') return formatRelative(delta)
  // auto — relative under 7 days, absolute otherwise.
  return delta >= 0 && delta < WEEK_MS
    ? formatRelative(delta)
    : formatAbsolute(d)
}
