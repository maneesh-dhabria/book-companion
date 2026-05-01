export const formatCompression = (raw: number | null | undefined): string => {
  if (raw === null || raw === undefined || Number.isNaN(raw)) return '—'
  const bucketed = Math.round(raw / 5) * 5
  return `~${bucketed}%`
}
