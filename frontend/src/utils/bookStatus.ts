export function bookStatusToneClass(status: string | null | undefined): string {
  switch (status) {
    case 'completed':
      return 'chip--accent'
    case 'parsed':
      return 'chip--info'
    case 'summarizing':
    case 'parsing':
      return 'chip--warn'
    case 'failed':
      return 'chip--warn'
    default:
      return 'chip--neutral'
  }
}
