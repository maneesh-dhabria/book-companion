import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PresetPicker from '../PresetPicker.vue'

const mockListPresets = vi.fn()
const mockStartProcessing = vi.fn()

vi.mock('@/api/presets', () => ({
  listSummarizerPresets: (...args: unknown[]) => mockListPresets(...args),
}))

vi.mock('@/api/processing', () => ({
  startProcessing: (...args: unknown[]) => mockStartProcessing(...args),
}))

const presetsFixture = {
  presets: [
    { id: 'practitioner_bullets', label: 'Practitioner', description: 'Bullets', facets: {}, system: true },
    { id: 'executive_brief', label: 'Executive', description: 'Brief prose', facets: {}, system: true },
  ],
  default_id: 'practitioner_bullets',
}

describe('PresetPicker', () => {
  afterEach(() => {
    mockListPresets.mockReset()
    mockStartProcessing.mockReset()
  })

  it('fetches presets on mount and renders them', async () => {
    mockListPresets.mockResolvedValueOnce(presetsFixture)
    const w = mount(PresetPicker, { props: { bookId: 1 } })
    await flushPromises()
    const cards = w.findAll('[data-testid="preset-card"]')
    expect(cards).toHaveLength(2)
    expect(cards[0].classes()).toContain('selected')
  })

  it('shows PresetsFetchError on fetch failure and retries on click', async () => {
    mockListPresets
      .mockRejectedValueOnce(new Error('500: server error'))
      .mockResolvedValueOnce(presetsFixture)
    const w = mount(PresetPicker, { props: { bookId: 1 } })
    await flushPromises()
    expect(w.find('[data-testid="presets-fetch-retry"]').exists()).toBe(true)
    expect(w.text()).toContain('Could not load summarization presets')

    await w.find('[data-testid="presets-fetch-retry"]').trigger('click')
    await flushPromises()
    expect(w.findAll('[data-testid="preset-card"]')).toHaveLength(2)
  })

  it('disables Start button while fetch error is active', async () => {
    mockListPresets.mockRejectedValueOnce(new Error('500'))
    const w = mount(PresetPicker, { props: { bookId: 1 } })
    await flushPromises()
    const btn = w.find('[data-testid="start-processing"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('surfaces POST /summarize error inline', async () => {
    mockListPresets.mockResolvedValueOnce(presetsFixture)
    mockStartProcessing.mockRejectedValueOnce(new Error('Preset not found'))
    const w = mount(PresetPicker, { props: { bookId: 1 } })
    await flushPromises()
    await w.find('[data-testid="start-processing"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="start-error"]').text()).toContain('Preset not found')
    // Button is re-enabled after failure so the user can retry.
    expect(w.find('[data-testid="start-processing"]').attributes('disabled')).toBeUndefined()
  })

  it('emits select on successful POST', async () => {
    mockListPresets.mockResolvedValueOnce(presetsFixture)
    mockStartProcessing.mockResolvedValueOnce({ job_id: 7 })
    const w = mount(PresetPicker, { props: { bookId: 1 } })
    await flushPromises()
    await w.find('[data-testid="start-processing"]').trigger('click')
    await flushPromises()
    expect(w.emitted('select')?.[0]).toEqual(['practitioner_bullets'])
  })
})
