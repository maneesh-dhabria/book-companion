import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PresetPickerModal from '../PresetPickerModal.vue'

const mockListPresets = vi.fn()

vi.mock('@/api/presets', () => ({
  listSummarizerPresets: (...args: unknown[]) => mockListPresets(...args),
}))

const fixture = {
  presets: [
    { id: 'practitioner_bullets', label: 'Practitioner', description: 'Bullets', facets: {}, system: true },
    { id: 'academic_detailed', label: 'Academic', description: 'Detailed', facets: {}, system: true },
  ],
  default_id: 'practitioner_bullets',
}

describe('PresetPickerModal', () => {
  afterEach(() => mockListPresets.mockReset())

  it('pre-selects the given preset when available', async () => {
    mockListPresets.mockResolvedValueOnce(fixture)
    const w = mount(PresetPickerModal, { props: { preselect: 'academic_detailed' } })
    await flushPromises()
    const cards = w.findAll('[data-testid="preset-card"]')
    expect(cards[1].classes()).toContain('selected')
  })

  it('falls back to default_id when preselect is absent', async () => {
    mockListPresets.mockResolvedValueOnce(fixture)
    const w = mount(PresetPickerModal, { props: {} })
    await flushPromises()
    const cards = w.findAll('[data-testid="preset-card"]')
    expect(cards[0].classes()).toContain('selected')
  })

  it('emits submit with the selected preset id', async () => {
    mockListPresets.mockResolvedValueOnce(fixture)
    const w = mount(PresetPickerModal, { props: { preselect: 'academic_detailed' } })
    await flushPromises()
    await w.find('[data-testid="submit"]').trigger('click')
    expect(w.emitted('submit')?.[0]).toEqual(['academic_detailed'])
  })

  it('emits cancel on backdrop click', async () => {
    mockListPresets.mockResolvedValueOnce(fixture)
    const w = mount(PresetPickerModal, {})
    await flushPromises()
    await w.find('.modal-overlay').trigger('click')
    expect(w.emitted('cancel')).toBeTruthy()
  })

  it('disables submit when fetch fails', async () => {
    mockListPresets.mockRejectedValueOnce(new Error('500'))
    const w = mount(PresetPickerModal, {})
    await flushPromises()
    expect(w.find('[data-testid="submit"]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-testid="presets-fetch-retry"]').exists()).toBe(true)
  })
})
