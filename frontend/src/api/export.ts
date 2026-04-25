export interface SummaryExportSelection {
  include_book_summary?: boolean
  include_toc?: boolean
  include_annotations?: boolean
  exclude_section_ids?: number[]
}

export interface SummaryExportResult {
  blob: Blob
  filename: string
  text: string
  isEmpty: boolean
}

export async function exportBookSummary(
  bookId: number,
  selection?: SummaryExportSelection
): Promise<SummaryExportResult> {
  const params = new URLSearchParams({ format: 'markdown' })
  if (selection?.include_book_summary === false) params.set('include_book_summary', 'false')
  if (selection?.include_toc === false) params.set('include_toc', 'false')
  if (selection?.include_annotations === false) params.set('include_annotations', 'false')
  for (const id of selection?.exclude_section_ids ?? []) {
    params.append('exclude_section', String(id))
  }
  const url = `/api/v1/export/book/${bookId}?${params}`
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Export failed: ${response.status}`)

  const cd = response.headers.get('content-disposition') || ''
  const m = cd.match(/filename="([^"]+)"/)
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const filename = m ? m[1] : `book-${bookId}-summary-${today}.md`
  const isEmpty = response.headers.get('x-empty-export') === 'true'

  const blob = await response.blob()
  const text = await blob.text()
  return { blob, filename, text, isEmpty }
}

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
  return triggerDownload(
    response,
    `book_${bookId}.${options.format === 'json' ? 'json' : 'md'}`
  )
}

export async function exportLibrary(options: { format: 'json' }) {
  if ((options.format as string) !== 'json') {
    throw new Error('Library Markdown export was removed in v1.6 -- use format: "json".')
  }
  const params = new URLSearchParams({ format: 'json' })
  const response = await fetch(`/api/v1/export/library?${params}`)
  if (!response.ok) throw new Error('Export failed')
  return triggerDownload(response, 'library_export.json')
}

export async function triggerDownload(response: Response, fallbackFilename: string) {
  const blob = await response.blob()
  const cd = response.headers.get('content-disposition') || ''
  const m = cd.match(/filename="([^"]+)"/)
  const filename = m ? m[1] : fallbackFilename
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
