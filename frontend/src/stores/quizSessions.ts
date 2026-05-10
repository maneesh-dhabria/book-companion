import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import * as api from '@/api/quizSessions'
import { ApiError } from '@/api/client'
import { useUiStore } from '@/stores/ui'

const QUIZ_START_FALLBACK =
  "Couldn't start quiz — the server returned an unexpected error. Retry?"
const HTML_BODY = /^<!?(DOCTYPE|html|HTML)/
import type {
  QuizLifetimeTally,
  QuizQuestion,
  QuizScope,
  QuizSelfAssessment,
  QuizSessionListItem,
  QuizSessionTally,
} from '@/types'

export interface QuizToast {
  kind: 'warn' | 'error' | 'info'
  message: string
}

export interface BookQuizState {
  sessions: QuizSessionListItem[]
  lifetimeTally: QuizLifetimeTally
  themesSummary: string | null
  activeSession: QuizSessionListItem | null
  currentQuestion: QuizQuestion | null
  loading: boolean
  loaded: boolean
}

const EMPTY_TALLY: QuizSessionTally = {
  got_it: 0,
  partial: 0,
  missed: 0,
  skipped: 0,
  discarded: 0,
}

const EMPTY_LIFETIME: QuizLifetimeTally = {
  total_questions: 0,
  got_it: 0,
  partial: 0,
  missed: 0,
  session_count: 0,
  themes_summary: null,
}

function emptyState(): BookQuizState {
  return {
    sessions: [],
    lifetimeTally: { ...EMPTY_LIFETIME },
    themesSummary: null,
    activeSession: null,
    currentQuestion: null,
    loading: false,
    loaded: false,
  }
}

export const useQuizSessionsStore = defineStore('quizSessions', () => {
  const byBook = reactive(new Map<number, BookQuizState>())
  const lastToast = ref<QuizToast | null>(null)
  const inlineDiagnostic = ref<{ reason: string; stderrTail: string | null } | null>(null)

  function clearInlineDiagnostic(): void {
    inlineDiagnostic.value = null
  }

  function ensureBook(bookId: number): BookQuizState {
    let state = byBook.get(bookId)
    if (!state) {
      state = reactive(emptyState()) as BookQuizState
      byBook.set(bookId, state)
    }
    return state
  }

  async function loadForBook(bookId: number): Promise<void> {
    const state = ensureBook(bookId)
    state.loading = true
    try {
      const [list, lifetime] = await Promise.all([
        api.listSessions(bookId),
        api.getLifetimeTally(bookId),
      ])
      state.sessions = list.sessions
      // §9.9 wins over §9.1's mirrored lifetime_tally (G34)
      state.lifetimeTally = lifetime
      state.themesSummary = lifetime.themes_summary ?? null
      // Active session = newest in_progress
      state.activeSession = list.sessions.find((s) => s.status === 'in_progress') ?? null
      state.loaded = true
    } finally {
      state.loading = false
    }
  }

  async function startSession(
    bookId: number,
    scope: QuizScope,
    theme: string | null,
  ): Promise<void> {
    const state = ensureBook(bookId)
    try {
      const resp = await api.startSession(bookId, { scope, theme })
      state.activeSession = resp.session
      state.currentQuestion = resp.first_question
      // Prepend so the list reflects reality immediately; loadForBook can re-sort.
      state.sessions = [resp.session, ...state.sessions.filter((s) => s.id !== resp.session.id)]
    } catch (e) {
      if (e instanceof ApiError) {
        // FR-05/FR-07/D15: surface as actionable toast + inline diagnostic.
        // Empty/HTML messages get the friendly fallback; structured detail is
        // passed through verbatim from ApiError.message.
        let message = e.message
        if (!message || HTML_BODY.test(message)) {
          message = QUIZ_START_FALLBACK
        }
        inlineDiagnostic.value = { reason: message, stderrTail: e.llmStderrTail ?? null }
        const ui = useUiStore()
        ui.showToast(message, 'error', {
          actionable: true,
          dedupeKey: 'quiz-start',
          dismissible: false,
          action: {
            label: 'Retry',
            onClick: async () => {
              await startSession(bookId, scope, theme)
              ui.clearByKey('quiz-start')
              inlineDiagnostic.value = null
            },
          },
        })
      }
      throw e
    }
  }

  async function loadNextQuestion(bookId: number): Promise<void> {
    const state = ensureBook(bookId)
    if (!state.activeSession) return
    const resp = await api.nextQuestion(state.activeSession.id)
    state.currentQuestion = resp.question
  }

  async function submitAnswer(bookId: number, answer: string): Promise<void> {
    const state = ensureBook(bookId)
    if (!state.activeSession || !state.currentQuestion) return
    const resp = await api.submitAnswer(
      state.activeSession.id,
      state.currentQuestion.id,
      answer,
    )
    state.currentQuestion = resp.question
  }

  async function recordSelfAssessment(
    bookId: number,
    sa: QuizSelfAssessment,
  ): Promise<void> {
    const state = ensureBook(bookId)
    if (!state.activeSession || !state.currentQuestion) return
    const prev = state.currentQuestion.self_assessment ?? null
    const prevTally: QuizSessionTally = state.activeSession
      ? { ...state.activeSession.tally }
      : { ...EMPTY_TALLY }
    // Optimistic update
    state.currentQuestion.self_assessment = sa
    state.activeSession.tally = applySelfAssessmentDelta(prevTally, prev, sa)
    try {
      const updated = await api.recordSelfAssessment(
        state.activeSession.id,
        state.currentQuestion.id,
        sa,
      )
      // Reconcile from server (covers cases where server normalised the value).
      state.currentQuestion = { ...state.currentQuestion, ...updated }
    } catch (err) {
      // Rollback
      state.currentQuestion.self_assessment = prev
      if (state.activeSession) state.activeSession.tally = prevTally
      if (err instanceof ApiError && err.status === 409) {
        const recordedAs = extractRecordedAs(err.detail)
        lastToast.value = {
          kind: 'warn',
          message: recordedAs
            ? `Already recorded as ${recordedAs} — refresh to see latest.`
            : 'Already recorded — refresh to see latest.',
        }
      } else {
        lastToast.value = { kind: 'error', message: "Couldn't save — try again." }
      }
      // Re-fetch authoritative state for this question
      await reloadActiveSession(bookId)
    }
  }

  async function reloadActiveSession(bookId: number): Promise<void> {
    const state = ensureBook(bookId)
    if (!state.activeSession) return
    const detail = await api.getSession(state.activeSession.id)
    state.activeSession = detail.session
    // Refresh currentQuestion if it's in the new detail.
    const cur = state.currentQuestion
    if (cur) {
      const fresh = detail.questions.find((q) => q.id === cur.id)
      if (fresh) state.currentQuestion = fresh
    }
  }

  function clearToast(): void {
    lastToast.value = null
  }

  function reset(): void {
    byBook.clear()
    lastToast.value = null
  }

  // Convenience computed for current book's state — callers pass bookId
  function stateFor(bookId: number) {
    return computed(() => byBook.get(bookId) ?? null)
  }

  return {
    byBook,
    lastToast,
    inlineDiagnostic,
    clearInlineDiagnostic,
    loadForBook,
    startSession,
    loadNextQuestion,
    submitAnswer,
    recordSelfAssessment,
    reloadActiveSession,
    clearToast,
    reset,
    stateFor,
  }
})

function applySelfAssessmentDelta(
  tally: QuizSessionTally,
  prev: QuizSelfAssessment | null,
  next: QuizSelfAssessment,
): QuizSessionTally {
  const out = { ...tally }
  if (prev && prev in out) {
    out[prev as keyof QuizSessionTally] = Math.max(0, out[prev as keyof QuizSessionTally] - 1)
  }
  if (next in out) {
    out[next as keyof QuizSessionTally] = out[next as keyof QuizSessionTally] + 1
  }
  return out
}

function extractRecordedAs(detail: unknown): string | null {
  if (detail && typeof detail === 'object' && 'recordedAs' in (detail as object)) {
    const v = (detail as { recordedAs?: unknown }).recordedAs
    if (typeof v === 'string') return v
  }
  if (typeof detail === 'string') {
    const m = detail.match(/Already recorded as (\w+)/)
    if (m) return m[1]
  }
  return null
}
