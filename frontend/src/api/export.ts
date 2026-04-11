export interface ExportOptions {
  format: 'json' | 'markdown'
  include_summaries?: boolean
  include_annotations?: boolean
  include_concepts?: boolean
  include_eval?: boolean
}

export async function exportBook(bookId: number, options: ExportOptions) {
  const params = new URLSearchParams({ format: options.format })
  const response = await fetch(`/api/v1/export/book/${bookId}?${params}`)
  if (!response.ok) throw new Error('Export failed')
  return triggerDownload(response, `book_${bookId}.${options.format === 'json' ? 'json' : 'md'}`)
}

export async function exportLibrary(options: ExportOptions) {
  const params = new URLSearchParams({ format: options.format })
  const response = await fetch(`/api/v1/export/library?${params}`)
  if (!response.ok) throw new Error('Export failed')
  return triggerDownload(response, `library_export.${options.format === 'json' ? 'json' : 'md'}`)
}

async function triggerDownload(response: Response, filename: string) {
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
