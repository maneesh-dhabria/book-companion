import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAudioApiError } from '@/composables/audio/useAudioApiError'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('useAudioApiError', () => {
  it('503 maps to engine-unavailable toast', () => {
    const spy = vi.fn()
    useAudioApiError(spy)({ status: 503 })
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'warning',
        text: expect.stringContaining('temporarily unavailable'),
        action: 'Retry',
      }),
    )
  })

  it('network error maps to reconnecting toast', () => {
    const spy = vi.fn()
    useAudioApiError(spy)({ status: 0, code: 'NETWORK' })
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ text: expect.stringContaining('Reconnecting') }),
    )
  })

  it('429 maps to rate-limit toast', () => {
    const spy = vi.fn()
    useAudioApiError(spy)({ status: 429 })
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ text: expect.stringContaining('Rate limit') }),
    )
  })

  it('500 maps to generic error toast', () => {
    const spy = vi.fn()
    useAudioApiError(spy)({ status: 500 })
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'error', action: 'Retry' }),
    )
  })

  it('409 maps to info toast (no Retry action)', () => {
    const spy = vi.fn()
    useAudioApiError(spy)({ status: 409 })
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'info' }),
    )
  })
})
