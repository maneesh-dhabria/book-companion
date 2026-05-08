import { beforeEach, describe, expect, it } from 'vitest'

import { _resetForTests, useWebSpeechSupported } from '@/composables/useWebSpeechSupported'

beforeEach(() => _resetForTests())

describe('useWebSpeechSupported', () => {
  it('returns true when speechSynthesis is on window', () => {
    ;(globalThis as unknown as { window: object }).window = { speechSynthesis: {} }
    expect(useWebSpeechSupported().supported.value).toBe(true)
  })

  it('returns false when speechSynthesis is missing', () => {
    ;(globalThis as unknown as { window: object }).window = {}
    expect(useWebSpeechSupported().supported.value).toBe(false)
  })

  it('caches the result across calls', () => {
    ;(globalThis as unknown as { window: object }).window = { speechSynthesis: {} }
    useWebSpeechSupported()
    ;(globalThis as unknown as { window: object }).window = {}
    expect(useWebSpeechSupported().supported.value).toBe(true)
  })
})
