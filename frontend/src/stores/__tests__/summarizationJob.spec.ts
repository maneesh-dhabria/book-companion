import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/processing', () => ({
  startProcessing: vi.fn(async () => ({ job_id: 42 })),
  connectSSE: vi.fn(() => ({ close: vi.fn() })),
  getProcessingStatus: vi.fn(async () => ({
    progress: { completed: 5, failed: 1, skipped: 0 },
  })),
}))

vi.mock('@/api/books', () => ({
  getBook: vi.fn(async () => ({
    id: 1,
    title: 't',
    summary_progress: { summarized: 0, total: 0 },
  })),
}))

vi.mock('@/api/sections', () => ({
  getSection: vi.fn(async (_: number, id: number) => ({
    id,
    book_id: 1,
    title: `S${id}`,
    has_summary: true,
  })),
}))

describe('summarizationJob store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initial state is inactive', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    expect(s.isActive).toBe(false)
    expect(s.activeJobSectionId).toBeNull()
    expect(s.getFailedError(1)).toBeUndefined()
  })

  it('onSectionStarted sets activeJobSectionId', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    s.onSectionStarted({ section_id: 5 })
    expect(s.activeJobSectionId).toBe(5)
  })

  it('onSectionFailed records error + clears active', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    s.onSectionStarted({ section_id: 5 })
    s.onSectionFailed({
      section_id: 5,
      title: 'S5',
      index: 1,
      total: 1,
      error: 'LLM timeout',
    })
    expect(s.activeJobSectionId).toBeNull()
    expect(s.getFailedError(5)).toBe('LLM timeout')
  })

  it('retry via startJob clears previous failedSections entry for that section', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    s.onSectionFailed({
      section_id: 5,
      title: 'S5',
      index: 1,
      total: 1,
      error: 'oops',
    })
    expect(s.getFailedError(5)).toBe('oops')
    await s.startJob(1, { scope: 'section', section_id: 5 })
    expect(s.getFailedError(5)).toBeUndefined()
  })

  it('reset clears job-session state but preserves failedSections', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    s.onSectionStarted({ section_id: 5 })
    s.onSectionFailed({
      section_id: 5,
      title: 'S5',
      index: 1,
      total: 1,
      error: 'x',
    })
    s.reset()
    expect(s.isActive).toBe(false)
    expect(s.activeJobSectionId).toBeNull()
    expect(s.getFailedError(5)).toBe('x')
  })

  it('starts grace-polling when no SSE events arrive within 30s', async () => {
    vi.useFakeTimers()
    const getBookMod = await import('@/api/books')
    const getBookMock = vi.mocked(getBookMod.getBook)
    getBookMock.mockResolvedValue({
      id: 1,
      title: 't',
      summary_progress: { summarized: 5, total: 5 },
    } as never)
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    await s.startJob(1, { scope: 'pending' })
    getBookMock.mockClear()
    await vi.advanceTimersByTimeAsync(30_000)
    await vi.advanceTimersByTimeAsync(5_000)
    expect(getBookMock).toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('duplicate section_completed is a no-op', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    s.bookId = 1
    await s.onSectionCompleted({ section_id: 42 })
    expect(s.completedCount).toBe(1)
    await s.onSectionCompleted({ section_id: 42 }) // replay
    expect(s.completedCount).toBe(1)
  })

  it('duplicate section_failed is a no-op', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    const payload = {
      section_id: 7,
      title: 'S7',
      index: 1,
      total: 1,
      error: 'boom',
    }
    s.onSectionFailed(payload)
    expect(s.failedCount).toBe(1)
    s.onSectionFailed(payload)
    expect(s.failedCount).toBe(1)
  })

  it('duplicate section_skipped is a no-op', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    const payload = {
      section_id: 9,
      title: 'S9',
      index: 1,
      total: 1,
      reason: 'already summarized',
    }
    s.onSectionSkipped(payload)
    s.onSectionSkipped(payload)
    expect(s.skippedCount).toBe(1)
  })

  it('onSSEError reconciles counts via GET /processing/:id', async () => {
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    await s.startJob(1, { scope: 'pending' })
    await s.onSSEError()
    expect(s.completedCount).toBe(5)
    expect(s.failedCount).toBe(1)
    expect(s.skippedCount).toBe(0)
  })

  it('grace-polling cancels when a real SSE event arrives', async () => {
    vi.useFakeTimers()
    const getBookMod = await import('@/api/books')
    const getBookMock = vi.mocked(getBookMod.getBook)
    const { useSummarizationJobStore } = await import('../summarizationJob')
    const s = useSummarizationJobStore()
    await s.startJob(1, { scope: 'pending' })
    getBookMock.mockClear()
    await vi.advanceTimersByTimeAsync(10_000)
    s.onSectionStarted({ section_id: 7 })
    await vi.advanceTimersByTimeAsync(25_000)
    expect(getBookMock).not.toHaveBeenCalled()
    vi.useRealTimers()
  })
})
