/**
 * Deterministic selector for a cover-fallback gradient from a book title.
 *
 * Emits one of 8 fixed gradients so the same book always shows the same
 * colours across reloads.
 */

export const COVER_GRADIENTS: ReadonlyArray<{ id: string; from: string; to: string }> = [
  { id: 'indigo-rose', from: '#4f46e5', to: '#e11d48' },
  { id: 'teal-lime', from: '#0d9488', to: '#65a30d' },
  { id: 'amber-orange', from: '#f59e0b', to: '#ea580c' },
  { id: 'sky-indigo', from: '#0284c7', to: '#4338ca' },
  { id: 'emerald-teal', from: '#059669', to: '#0d9488' },
  { id: 'violet-fuchsia', from: '#7c3aed', to: '#c026d3' },
  { id: 'rose-amber', from: '#e11d48', to: '#f59e0b' },
  { id: 'slate-zinc', from: '#475569', to: '#52525b' },
]

function hashString(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) >>> 0
  }
  return h
}

export function coverGradientFor(title: string | null | undefined) {
  const key = (title || '').trim() || 'untitled'
  const idx = hashString(key) % COVER_GRADIENTS.length
  return COVER_GRADIENTS[idx]
}
