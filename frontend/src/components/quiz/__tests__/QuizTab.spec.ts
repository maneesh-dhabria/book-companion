import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import QuizTab from '@/components/quiz/QuizTab.vue'
import { COPY } from '@/components/quiz/copy'
import type {
  QuizLifetimeTally,
  QuizQuestion,
  QuizSessionListItem,
  QuizSessionListResponse,
} from '@/types'

// ── Mocks ────────────────────────────────────────────────────────────

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

const settingsMocks = vi.hoisted(() => ({
  getLlmStatus: vi.fn(),
}))
vi.mock('@/api/settings', () => settingsMocks)

// ── Helpers ──────────────────────────────────────────────────────────

const EMPTY_LIFETIME: QuizLifetimeTally = {
  total_questions: 0,
  got_it: 0,
  partial: 0,
  missed: 0,
  session_count: 0,
  themes_summary: null,
}

function makeSession(overrides: Partial<QuizSessionListItem> = {}): QuizSessionListItem {
  return {
    id: 1,
    book_id: 7,
    scope: { mode: 'all_summaries' },
    theme: null,
    status: 'completed',
    created_at: '2026-05-09T00:00:00Z',
    ended_at: '2026-05-09T00:30:00Z',
    question_count: 3,
    tally: { got_it: 2, partial: 1, missed: 0, skipped: 0, discarded: 0 },
    is_warm_up_session: false,
    ...overrides,
  }
}

function makeQuestion(overrides: Partial<QuizQuestion> = {}): QuizQuestion {
  return {
    id: 100,
    session_id: 50,
    book_id: 7,
    stem: '?',
    concept_label: 'x',
    citation: { section_id: 1, section_title: '', snippet: '' },
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

function setApiState(opts: {
  llmOk?: boolean
  sessions?: QuizSessionListItem[]
  currentQuestion?: QuizQuestion | null
}) {
  settingsMocks.getLlmStatus.mockResolvedValue({
    configured_provider: 'auto',
    provider: 'claude',
    preflight: {
      ok: opts.llmOk ?? true,
      provider: opts.llmOk ?? true ? 'claude' : null,
      binary: null,
      binary_resolved: opts.llmOk ?? true,
      version: null,
      version_ok: opts.llmOk ?? true,
      reason: null,
    },
  })
  const sessions = opts.sessions ?? []
  const listResp: QuizSessionListResponse = { sessions, lifetime_tally: EMPTY_LIFETIME }
  apiMocks.listSessions.mockResolvedValue(listResp)
  apiMocks.getLifetimeTally.mockResolvedValue(EMPTY_LIFETIME)
}

async function mountTab(props: { bookId?: number; hasSummaries?: boolean } = {}) {
  const wrapper = mount(QuizTab, {
    props: { bookId: 7, hasSummaries: true, ...props },
  })
  await flushPromises()
  return wrapper
}

// ── Tests ────────────────────────────────────────────────────────────

beforeEach(() => {
  setActivePinia(createPinia())
  Object.values(apiMocks).forEach((fn) => fn.mockReset())
  Object.values(settingsMocks).forEach((fn) => fn.mockReset())
})

describe('QuizTab — state machine', () => {
  it('renders no-LLM banner when preflight.ok is false', async () => {
    setApiState({ llmOk: false })
    const wrapper = await mountTab()
    expect(wrapper.attributes('data-mode')).toBe('no-llm')
    expect(wrapper.find('[data-test="no-llm-banner"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(COPY.noLLMBanner)
  })

  it('renders no-summaries gate when hasSummaries is false', async () => {
    setApiState({ llmOk: true })
    const wrapper = await mountTab({ hasSummaries: false })
    expect(wrapper.attributes('data-mode')).toBe('no-summaries')
    expect(wrapper.find('[data-test="no-summaries-gate"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(COPY.noSummariesGate)
  })

  it('renders scope picker (ready mode) when ready and no active session', async () => {
    setApiState({ llmOk: true, sessions: [] })
    const wrapper = await mountTab()
    expect(wrapper.attributes('data-mode')).toBe('ready')
    expect(wrapper.find('[data-test="scope-picker"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="past-qa-panel"]').exists()).toBe(false)
  })

  it('renders resume banner when an in_progress session exists for this book', async () => {
    setApiState({
      llmOk: true,
      sessions: [makeSession({ id: 11, status: 'in_progress' })],
    })
    const wrapper = await mountTab()
    expect(wrapper.attributes('data-mode')).toBe('resume')
    expect(wrapper.find('[data-test="resume-banner"]').exists()).toBe(true)
  })

  it('renders past-Q&A panel alongside scope-picker when prior history exists', async () => {
    setApiState({
      llmOk: true,
      sessions: [makeSession({ id: 9, status: 'completed' })],
    })
    const wrapper = await mountTab()
    expect(wrapper.attributes('data-mode')).toBe('ready')
    expect(wrapper.find('[data-test="scope-picker"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="past-qa-panel"]').exists()).toBe(true)
  })

  it('mounts ThemesCoveredPanel in ready mode when lifetime themes_summary is present (FR-63 wiring)', async () => {
    settingsMocks.getLlmStatus.mockResolvedValue({
      configured_provider: 'auto',
      provider: 'claude',
      preflight: {
        ok: true,
        provider: 'claude',
        binary: null,
        binary_resolved: true,
        version: null,
        version_ok: true,
        reason: null,
      },
    })
    apiMocks.listSessions.mockResolvedValue({
      sessions: [],
      lifetime_tally: EMPTY_LIFETIME,
    })
    apiMocks.getLifetimeTally.mockResolvedValue({
      ...EMPTY_LIFETIME,
      themes_summary: 'Loss aversion and anchoring dominate.',
    })
    const wrapper = await mountTab()
    expect(wrapper.attributes('data-mode')).toBe('ready')
    expect(wrapper.find('[data-test="themes-covered"]').exists()).toBe(true)
  })
})
