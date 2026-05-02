export function estimatePlaylistMinutes(highlights: number, notes: number): number {
  const seconds = highlights * 30 + notes * 30
  return Math.ceil(seconds / 60)
}
