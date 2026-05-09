import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as api from '@/api/quizSessions'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('quizSessions REST client', () => {
  it('listSessions issues GET to /api/v1/books/:id/quiz-sessions', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ sessions: [], lifetime_tally: {} }))
    await api.listSessions(7)
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toBe('/api/v1/books/7/quiz-sessions')
  })

  it('getLifetimeTally issues GET to lifetime-tally subpath', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({
        total_questions: 0,
        got_it: 0,
        partial: 0,
        missed: 0,
        session_count: 0,
        themes_summary: null,
      }),
    )
    await api.getLifetimeTally(7)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/books/7/quiz-sessions/lifetime-tally')
  })

  it('startSession POSTs scope+theme', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ session: {}, first_question: {}, warm_up_count: 0 }))
    await api.startSession(7, { scope: { mode: 'all_summaries' }, theme: 'banks' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/books/7/quiz-sessions')
    expect((init as RequestInit).method).toBe('POST')
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body).toEqual({ scope: { mode: 'all_summaries' }, theme: 'banks' })
  })

  it('getSession issues GET to /quiz-sessions/:id', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ session: {}, questions: [] }))
    await api.getSession(42)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/quiz-sessions/42')
  })

  it('nextQuestion issues POST', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ question: {} }))
    await api.nextQuestion(42)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/quiz-sessions/42/next-question')
    expect((init as RequestInit).method).toBe('POST')
  })

  it('submitAnswer POSTs { answer }', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ question: {} }))
    await api.submitAnswer(42, 100, 'because of loss aversion')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/quiz-sessions/42/questions/100/answer')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      answer: 'because of loss aversion',
    })
  })

  it('recordSelfAssessment PATCHes { self_assessment }', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({}))
    await api.recordSelfAssessment(42, 100, 'got_it')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/quiz-sessions/42/questions/100')
    expect((init as RequestInit).method).toBe('PATCH')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      self_assessment: 'got_it',
    })
  })

  it('skipQuestion POSTs to /skip', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({}))
    await api.skipQuestion(42, 100)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/quiz-sessions/42/questions/100/skip')
  })

  it('explainQuestion POSTs to /explain', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ explanation: 'x', question: {} }))
    await api.explainQuestion(42, 100)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/quiz-sessions/42/questions/100/explain')
  })

  it('overrideQuestion POSTs { override_note }', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({}))
    await api.overrideQuestion(42, 100, 'I think I got this')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/quiz-sessions/42/questions/100/override')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      override_note: 'I think I got this',
    })
  })

  it('discardQuestion POSTs to /discard', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ question: {}, replacement: {} }))
    await api.discardQuestion(42, 100)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/quiz-sessions/42/questions/100/discard')
  })

  it('stopSession POSTs to /stop', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({}))
    await api.stopSession(42)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/quiz-sessions/42/stop')
  })

  it('throws on !response.ok with detail message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ detail: 'Already recorded as got_it' }, 409),
    )
    await expect(api.recordSelfAssessment(42, 100, 'partial')).rejects.toMatchObject({
      status: 409,
      message: 'Already recorded as got_it',
    })
  })
})
