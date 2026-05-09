import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import SessionTally from '@/components/quiz/SessionTally.vue'
import PastQAPanel from '@/components/quiz/PastQAPanel.vue'
import PastSessionGroup from '@/components/quiz/PastSessionGroup.vue'
import PastQuestionRow from '@/components/quiz/PastQuestionRow.vue'
import ThemesCoveredPanel from '@/components/quiz/ThemesCoveredPanel.vue'
import type { QuizQuestion, QuizSessionListItem, QuizLifetimeTally } from '@/types'

vi.mock('@/api/quizSessions', () => ({
  getSession: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})
afterEach(() => {
  vi.restoreAllMocks()
})

function makeSession(over: Partial<QuizSessionListItem> = {}): QuizSessionListItem {
  return {
    id: 1,
    book_id: 1,
    scope: { mode: 'all_summaries', section_ids: null },
    theme: null,
    status: 'completed',
    created_at: '2026-05-09T00:00:00Z',
    ended_at: '2026-05-09T00:30:00Z',
    question_count: 3,
    tally: { got_it: 1, partial: 1, missed: 1, skipped: 0, discarded: 0 },
    is_warm_up_session: false,
    ...over,
  }
}

function makeQ(over: Partial<QuizQuestion> = {}): QuizQuestion {
  return {
    id: 100,
    session_id: 1,
    book_id: 1,
    stem: 'What is X?',
    concept_label: 'x',
    citation: { section_id: 1, section_title: 'Ch1', snippet: 's' },
    shape: 'open',
    bloom_level: 'understand',
    mcq_options: null,
    intended_error: null,
    error_explanation: null,
    user_answer: 'my answer',
    feedback: { correct: 'a', missing: 'b', actual: 'c' },
    self_assessment: 'got_it',
    override_note: null,
    explain_history: [],
    skip_count: 0,
    discarded: false,
    warm_up: false,
    is_pregen: false,
    is_stale: false,
    created_at: '2026-05-09T00:00:00Z',
    answered_at: '2026-05-09T00:01:00Z',
    ...over,
  }
}

describe('SessionTally', () => {
  it('renders session + lifetime line with sessions count', () => {
    const lifetime: QuizLifetimeTally = {
      total_questions: 30,
      got_it: 15,
      partial: 10,
      missed: 5,
      session_count: 4,
      themes_summary: null,
    }
    const sessionTally = { got_it: 1, partial: 1, missed: 1, skipped: 0, discarded: 0 }
    const wrapper = mount(SessionTally, {
      props: { sessionTally, lifetime, sessionSkipped: 2 },
    })
    const text = wrapper.text()
    expect(text).toContain('Session: 1 / 1 / 1')
    expect(text).toContain('(2 skipped)')
    expect(text).toContain('Lifetime: 15 / 10 / 5')
    expect(text).toContain('4 sessions')
  })

  it('is hidden when no completed sessions exist (E24)', () => {
    const lifetime: QuizLifetimeTally = {
      total_questions: 0,
      got_it: 0,
      partial: 0,
      missed: 0,
      session_count: 0,
      themes_summary: null,
    }
    const sessionTally = { got_it: 0, partial: 0, missed: 0, skipped: 0, discarded: 0 }
    const wrapper = mount(SessionTally, {
      props: { sessionTally, lifetime, sessionSkipped: 0 },
    })
    expect(wrapper.find('[data-test="session-tally"]').exists()).toBe(false)
  })
})

describe('PastQuestionRow', () => {
  it('renders "stale (re-imported)" badge when is_stale=true (FR-93)', () => {
    const q = makeQ({ is_stale: true })
    const wrapper = mount(PastQuestionRow, { props: { question: q } })
    expect(wrapper.text()).toContain('stale (re-imported)')
  })

  it('does not render stale badge when is_stale=false', () => {
    const q = makeQ({ is_stale: false })
    const wrapper = mount(PastQuestionRow, { props: { question: q } })
    expect(wrapper.text()).not.toContain('stale (re-imported)')
  })

  it('renders discarded badge when discarded', () => {
    const q = makeQ({ discarded: true })
    const wrapper = mount(PastQuestionRow, { props: { question: q } })
    expect(wrapper.text().toLowerCase()).toContain('discarded')
  })
})

describe('PastSessionGroup', () => {
  it('expanded by default fetches questions and renders rows', async () => {
    const api = await import('@/api/quizSessions')
    vi.mocked(api.getSession).mockResolvedValue({
      session: makeSession({ id: 7, question_count: 2 }),
      questions: [makeQ({ id: 1 }), makeQ({ id: 2, stem: 'Y?' })],
    })
    const wrapper = mount(PastSessionGroup, {
      props: { session: makeSession({ id: 7, question_count: 2 }), defaultExpanded: true },
    })
    await flushPromises()
    expect(api.getSession).toHaveBeenCalledWith(7)
    expect(wrapper.findAllComponents(PastQuestionRow).length).toBe(2)
  })

  it('collapsed by default does not fetch', async () => {
    const api = await import('@/api/quizSessions')
    mount(PastSessionGroup, {
      props: { session: makeSession({ id: 8 }), defaultExpanded: false },
    })
    await flushPromises()
    expect(api.getSession).not.toHaveBeenCalled()
  })
})

describe('PastQAPanel', () => {
  it('groups questions by session with most-recent expanded', async () => {
    const api = await import('@/api/quizSessions')
    vi.mocked(api.getSession).mockResolvedValue({
      session: makeSession({ id: 1 }),
      questions: [makeQ()],
    })
    const sessions = [
      makeSession({ id: 1, created_at: '2026-05-09T00:00:00Z' }),
      makeSession({ id: 2, created_at: '2026-05-08T00:00:00Z' }),
    ]
    const wrapper = mount(PastQAPanel, { props: { sessions } })
    await flushPromises()
    const groups = wrapper.findAllComponents(PastSessionGroup)
    expect(groups.length).toBe(2)
    expect(groups[0].props('defaultExpanded')).toBe(true)
    expect(groups[1].props('defaultExpanded')).toBe(false)
  })

  it('renders empty state when no sessions', () => {
    const wrapper = mount(PastQAPanel, { props: { sessions: [] } })
    expect(wrapper.find('[data-test="past-qa-empty"]').exists()).toBe(true)
  })
})

describe('ThemesCoveredPanel', () => {
  it('renders themes paragraph and emits chips', () => {
    const wrapper = mount(ThemesCoveredPanel, {
      props: { themesSummary: 'Prospect theory and anchoring dominate.' },
    })
    const chips = wrapper.findAll('[data-test="theme-chip"]')
    expect(chips.length).toBeGreaterThan(0)
  })

  it('emits seed-theme on chip click (FR-63)', async () => {
    const wrapper = mount(ThemesCoveredPanel, {
      props: { themesSummary: 'Loss aversion, anchoring, and framing.' },
    })
    const chip = wrapper.findAll('[data-test="theme-chip"]')[0]
    await chip.trigger('click')
    const events = wrapper.emitted('seed-theme')
    expect(events).toBeTruthy()
    expect(typeof events![0][0]).toBe('string')
  })

  it('is hidden when themes_summary is null', () => {
    const wrapper = mount(ThemesCoveredPanel, { props: { themesSummary: null } })
    expect(wrapper.find('[data-test="themes-covered"]').exists()).toBe(false)
  })

  it('is hidden when themes_summary is empty string', () => {
    const wrapper = mount(ThemesCoveredPanel, { props: { themesSummary: '' } })
    expect(wrapper.find('[data-test="themes-covered"]').exists()).toBe(false)
  })
})
