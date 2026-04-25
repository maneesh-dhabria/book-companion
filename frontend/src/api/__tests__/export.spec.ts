import { describe, it, expect, vi, beforeEach } from 'vitest'
import { exportBookSummary, exportLibrary } from '@/api/export'

describe('exportBookSummary', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('builds default URL with format=markdown only', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('# X', {
        status: 200,
        headers: {
          'content-disposition': 'attachment; filename="x-summary-20260425.md"',
          'x-empty-export': 'false',
        },
      }),
    )
    const r = await exportBookSummary(3)
    expect(fetchMock).toHaveBeenCalledOnce()
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toBe('/api/v1/export/book/3?format=markdown')
    expect(r.filename).toBe('x-summary-20260425.md')
    expect(r.isEmpty).toBe(false)
    expect(r.text).toBe('# X')
  })

  it('builds URL with selection params', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('# x', { status: 200, headers: { 'x-empty-export': 'true' } }),
    )
    await exportBookSummary(7, {
      include_toc: false,
      include_annotations: false,
      exclude_section_ids: [14, 15],
    })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('format=markdown')
    expect(url).toContain('include_toc=false')
    expect(url).toContain('include_annotations=false')
    expect(url).toMatch(/exclude_section=14/)
    expect(url).toMatch(/exclude_section=15/)
  })

  it('returns isEmpty=true when header is "true"', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('# t', { status: 200, headers: { 'x-empty-export': 'true' } }),
    )
    const r = await exportBookSummary(1)
    expect(r.isEmpty).toBe(true)
  })

  it('falls back to book-{id}-summary-{YYYYMMDD}.md when content-disposition is missing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('# t', { status: 200 }))
    const r = await exportBookSummary(42)
    expect(r.filename).toMatch(/^book-42-summary-\d{8}\.md$/)
  })

  it('throws on non-OK response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 400 }))
    await expect(exportBookSummary(1)).rejects.toThrow()
  })
})

describe('exportLibrary', () => {
  it('rejects format=markdown at runtime', async () => {
    // @ts-expect-error -- markdown is no longer a valid format
    await expect(exportLibrary({ format: 'markdown' })).rejects.toThrow(/json/i)
  })
})
