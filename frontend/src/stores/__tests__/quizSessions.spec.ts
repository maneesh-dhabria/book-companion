import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import type {
  QuizLifetimeTally,
  QuizQuestion,
  QuizSessionListItem,
  QuizSessionListResponse,
  QuizStartResponse,
} from '@/types'

const apiMocks = vi.hoisted(() => ({
  listSessions: vi.fn(),
  getLifetimeTally: vi.fn(),
  startSession: vi.fn(),
  getSession: vi.fn(),
  nextQuestion: vi.fn(),
  submitAnswer: vi.fn(),
  recordSelfAssessment: vi.fn(),
  skipQuestion: vi.fn(),
  explainQuestion: vi.fn(),
  overrideQuestion: vi.fn(),
  discardQuestion: vi.fn(),
  stopSession: vi.fn(),
}))

vi.mock('@/api/quizSessions', () => apiMocks)

import { useQuizSessionsStore } from '@/stores/quizSessions'

function makeSession(overrides: Partial<QuizSessionListItem> = {}): QuizSessionListItem {
  return {
    id: 100,
    book_id: 7,
    scope: { mode: 'all_summaries' },
    theme: null,
    status: 'in_progress',
    created_at: '2026-05-09T00:00:00Z',
    ended_at: null,
    question_count: 0,
    tally: { got_it: 0, partial: 0, missed: 0, skipped: 0, discarded: 0 },
    is_warm_up_session: false,
    ...overrides,
  }
}

function makeQuestion(overrides: Partial<QuizQuestion> = {}): QuizQuestion {
  return {
    id: 200,
    session_id: 100,
    book_id: 7,
    stem: 'What is loss aversion?',
    concept_label: 'loss aversion',
    citation: { section_id: 1, section_title: 'Ch 1', snippet: '...' },
    shape: 'open',
    bloom_level: 'apply',
    explain_history: [],
    skip_count: 0,
    discarded: false,
    warm_up: false,
    is_pregen: false,
    is_stale: false,
    created_at: '2026-05-09T00:00:00Z',
    ...overrides,
  }
}

const LIFETIME_FROM_LIST: QuizLifetimeTally = {
  total_questions: 99,
  got_it: 99,
  partial: 0,
  missed: 0,
  session_count: 1,
  themes_summary: 'stale-from-list',
}

const LIFETIME_FROM_TALLY: QuizLifetimeTally = {
  total_questions: 5,
  got_it: 3,
  partial: 1,
  missed: 1,
  session_count: 2,
  themes_summary: 'fresh',
}

beforeEach(() => {
  setActivePinia(createPinia())
  Object.values(apiMocks).forEach((fn) => fn.mockReset())
})

describe('useQuizSessionsStore — loadForBook', () => {
  it('issues §9.1 and §9.9 in parallel', async () => {
    const order: string[] = []
    apiMocks.listSessions.mockImplementation(async () => {
      order.push('list:start')
      await Promise.resolve()
      order.push('list:end')
      return { sessions: [], lifetime_tally: LIFETIME_FROM_LIST } as QuizSessionListResponse
    })
    apiMocks.getLifetimeTally.mockImplementation(async () => {
      order.push('tally:start')
      await Promise.resolve()
      order.push('tally:end')
      return LIFETIME_FROM_TALLY
    })

    const store = useQuizSessionsStore()
    await store.loadForBook(7)

    // Both started before either ended (Promise.all parallelism).
    expect(order.indexOf('list:start')).toBeLessThan(order.indexOf('list:end'))
    expect(order.indexOf('tally:start')).toBeLessThan(order.indexOf('tally:end'))
    expect(order.indexOf('list:start')).toBeLessThan(order.indexOf('tally:end'))
    expect(order.indexOf('tally:start')).toBeLessThan(order.indexOf('list:end'))
  })

  it('lifetime tally from §9.9 wins over §9.1 mirror (G34)', async () => {
    apiMocks.listSessions.mockResolvedValue({
      sessions: [],
      lifetime_tally: LIFETIME_FROM_LIST,
    })
    apiMocks.getLifetimeTally.mockResolvedValue(LIFETIME_FROM_TALLY)

    const store = useQuizSessionsStore()
    await store.loadForBook(7)
    const state = store.byBook.get(7)!
    expect(state.lifetimeTally).toEqual(LIFETIME_FROM_TALLY)
    expect(state.themesSummary).toBe('fresh')
  })

  it('exposes the newest in_progress session as activeSession', async () => {
    const inProg = makeSession({ id: 11, status: 'in_progress' })
    const completed = makeSession({ id: 9, status: 'completed' })
    apiMocks.listSessions.mockResolvedValue({
      sessions: [completed, inProg],
      lifetime_tally: LIFETIME_FROM_LIST,
    })
    apiMocks.getLifetimeTally.mockResolvedValue(LIFETIME_FROM_TALLY)

    const store = useQuizSessionsStore()
    await store.loadForBook(7)
    expect(store.byBook.get(7)!.activeSession?.id).toBe(11)
  })
})

describe('useQuizSessionsStore — per-book isolation', () => {
  it('keeps separate state for different bookIds', async () => {
    apiMocks.listSessions.mockImplementation(async (bookId: number) => ({
      sessions: [makeSession({ id: bookId * 10, book_id: bookId, status: 'completed' })],
      lifetime_tally: LIFETIME_FROM_LIST,
    }))
    apiMocks.getLifetimeTally.mockImplementation(async (bookId: number) => ({
      ...LIFETIME_FROM_TALLY,
      total_questions: bookId,
    }))

    const store = useQuizSessionsStore()
    await store.loadForBook(7)
    await store.loadForBook(13)
    expect(store.byBook.get(7)!.lifetimeTally.total_questions).toBe(7)
    expect(store.byBook.get(13)!.lifetimeTally.total_questions).toBe(13)
    expect(store.byBook.get(7)!.sessions[0].id).toBe(70)
    expect(store.byBook.get(13)!.sessions[0].id).toBe(130)
  })
})

describe('useQuizSessionsStore — recordSelfAssessment optimistic + rollback', () => {
  async function seedActive(store: ReturnType<typeof useQuizSessionsStore>) {
    apiMocks.startSession.mockResolvedValue({
      session: makeSession(),
      first_question: makeQuestion(),
      warm_up_count: 0,
    } as QuizStartResponse)
    await store.startSession(7, { mode: 'all_summaries' }, null)
  }

  it('rolls back tally on 409 and shows toast with recorded value', async () => {
    const store = useQuizSessionsStore()
    await seedActive(store)
    const beforeTally = { ...store.byBook.get(7)!.activeSession!.tally }
    apiMocks.recordSelfAssessment.mockRejectedValue(
      new ApiError(409, 'Already recorded as got_it', 'CONFLICT'),
    )
    apiMocks.getSession.mockResolvedValue({
      session: makeSession(),
      questions: [makeQuestion()],
    })

    await store.recordSelfAssessment(7, 'partial')

    const after = store.byBook.get(7)!
    expect(after.activeSession!.tally).toEqual(beforeTally)
    expect(after.currentQuestion!.self_assessment ?? null).toBe(null)
    expect(store.lastToast?.kind).toBe('warn')
    expect(store.lastToast?.message).toMatch(/Already recorded as got_it/)
  })

  it('rolls back on 5xx with generic error toast', async () => {
    const store = useQuizSessionsStore()
    await seedActive(store)
    apiMocks.recordSelfAssessment.mockRejectedValue(
      new ApiError(500, 'boom', 'INTERNAL'),
    )
    apiMocks.getSession.mockResolvedValue({
      session: makeSession(),
      questions: [makeQuestion()],
    })

    await store.recordSelfAssessment(7, 'got_it')
    expect(store.byBook.get(7)!.currentQuestion!.self_assessment ?? null).toBe(null)
    expect(store.lastToast?.kind).toBe('error')
    expect(store.lastToast?.message).toMatch(/Couldn't save/)
  })

  it('keeps the optimistic value on success and reconciles from server', async () => {
    const store = useQuizSessionsStore()
    await seedActive(store)
    apiMocks.recordSelfAssessment.mockResolvedValue(
      makeQuestion({ self_assessment: 'got_it' }),
    )
    await store.recordSelfAssessment(7, 'got_it')
    const cur = store.byBook.get(7)!.currentQuestion!
    expect(cur.self_assessment).toBe('got_it')
    expect(store.lastToast).toBeNull()
  })
})
