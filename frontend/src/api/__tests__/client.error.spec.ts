/**
 * FR-07: ApiError must expose `llmStderrTail` when the server returns the
 * 502 LLM-error envelope (`{detail: {detail: "...", llm_stderr_tail: "..."}}`)
 * while keeping `.message` faithful (no JSON.stringify of the wrapper).
 *
 * Decision D15: substitution for empty/HTML messages lives in the store
 * layer, NOT in `ApiError`. The constructor stays faithful.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import { apiClient, ApiError } from '@/api/client'

describe('ApiError 502 envelope (FR-07)', () => {
  const realFetch = globalThis.fetch

  beforeEach(() => {
    // no-op — each test installs its own fetch stub
  })
  afterEach(() => {
    globalThis.fetch = realFetch
    vi.restoreAllMocks()
  })

  it('parses {detail: {detail, llm_stderr_tail}} into faithful message + tail', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => ({
        detail: {
          detail: 'LLM provider error: boom',
          llm_stderr_tail: 'trace',
        },
      }),
    } as unknown as Response)

    let caught: unknown
    try {
      await apiClient.post('/quiz/start', {})
    } catch (e) {
      caught = e
    }
    expect(caught).toBeInstanceOf(ApiError)
    const err = caught as ApiError
    expect(err.status).toBe(502)
    expect(err.message).toBe('LLM provider error: boom')
    expect(err.llmStderrTail).toBe('trace')
  })

  it('legacy {detail: "string"} shape — message is the string, llmStderrTail null', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'preset_name required' }),
    } as unknown as Response)

    let caught: unknown
    try {
      await apiClient.post('/quiz/start', {})
    } catch (e) {
      caught = e
    }
    const err = caught as ApiError
    expect(err.status).toBe(400)
    expect(err.message).toBe('preset_name required')
    expect(err.llmStderrTail).toBeNull()
  })

  it('pydantic validation array — message joins msg fields, llmStderrTail null', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable',
      json: async () => ({
        detail: [
          { loc: ['body', 'preset_name'], msg: 'field required', type: 'value_error.missing' },
          { loc: ['body', 'count'], msg: 'must be > 0', type: 'value_error' },
        ],
      }),
    } as unknown as Response)

    let caught: unknown
    try {
      await apiClient.post('/quiz/start', {})
    } catch (e) {
      caught = e
    }
    const err = caught as ApiError
    expect(err.status).toBe(422)
    expect(err.message).toContain('field required')
    expect(err.message).toContain('must be > 0')
    expect(err.llmStderrTail).toBeNull()
  })
})
