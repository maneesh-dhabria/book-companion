import { describe, expect, it } from 'vitest'

import type { SseEvent } from '@/composables/useBufferedJobStream'

/**
 * Regression: backend `audio_gen_service` emits SSE events named
 * `section_audio_completed`, `section_audio_failed`, `section_audio_already_stale`.
 * `useBufferedJobStream`'s `SseEvent.event` union must include them or the
 * switch case in `applyEvent` will silently drop progress.
 *
 * See: docs/features/2026-05-02-audiobook-mode/verify (multi-agent review,
 * cross-file consistency reviewer, ≥85 confidence finding).
 */
describe('useBufferedJobStream — audio job event names (regression)', () => {
  it('SseEvent.event union admits audio job events', () => {
    const ev1: SseEvent = {
      event: 'section_audio_completed',
      data: { last_event_at: '0' },
    }
    const ev2: SseEvent = {
      event: 'section_audio_failed',
      data: { error: 'too_large' },
    }
    const ev3: SseEvent = {
      event: 'section_audio_already_stale',
      data: { last_event_at: '0' },
    }
    expect([ev1.event, ev2.event, ev3.event]).toEqual([
      'section_audio_completed',
      'section_audio_failed',
      'section_audio_already_stale',
    ])
  })
})
