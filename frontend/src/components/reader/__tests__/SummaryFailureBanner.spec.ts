import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SummaryFailureBanner from '../SummaryFailureBanner.vue'

describe('SummaryFailureBanner', () => {
  it('renders human-readable failure type + message + retry button', () => {
    const w = mount(SummaryFailureBanner, {
      props: {
        failureType: 'cli_nonzero_exit',
        message: 'exit 1: unauthorized',
        attemptedAt: '2026-04-22T10:00:00Z',
        preset: 'executive_brief',
      },
    })
    expect(w.text()).toContain('Summary failed')
    expect(w.text()).toContain('CLI exited with an error')
    expect(w.text()).toContain('exit 1: unauthorized')
    expect(w.find('[data-testid="retry-btn"]').exists()).toBe(true)
  })

  it('emits retry on button click', async () => {
    const w = mount(SummaryFailureBanner, {
      props: {
        failureType: 'cli_timeout',
        message: null,
        attemptedAt: null,
      },
    })
    await w.find('[data-testid="retry-btn"]').trigger('click')
    expect(w.emitted('retry')).toBeTruthy()
  })

  it('falls back to raw failure_type string when unknown code is provided', () => {
    const w = mount(SummaryFailureBanner, {
      props: {
        failureType: 'weird_custom_type',
        message: 'boom',
        attemptedAt: null,
      },
    })
    expect(w.text()).toContain('weird_custom_type')
  })
})
