import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: { start: vi.fn() },
}))

import GenerateAudioModal from '@/components/audio/GenerateAudioModal.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('GenerateAudioModal — FR-15 estimate-subline reactivity', () => {
  it('subline updates synchronously when annotations checkbox toggles', async () => {
    const wrap = mount(GenerateAudioModal, {
      props: {
        open: true,
        bookId: 1,
        totalUnits: 17,
        generatedCount: 0,
        bookSummaryGenerated: true,
        totalAnnotations: 5,
        totalWordCount: 0,
      },
    })

    // Initial: section_summaries=true, book=true, annotations=true (default ON).
    // delta = 17 (sections) + 0 (book; already generated) + 5 (annotations) = 22
    const subline = () => wrap.find('[data-testid="estimate-subline"]').text()
    expect(subline()).toBe('Generating 22 of 17 sections')

    // Toggle annotations OFF: 17 + 0 + 0 = 17
    const annCb = wrap.find('input[data-testid="include-annotations"]')
    await annCb.setValue(false)
    expect(subline()).toBe('Generating 17 of 17 sections')

    // Toggle back ON: 22 again
    await annCb.setValue(true)
    expect(subline()).toBe('Generating 22 of 17 sections')
  })

  it('estimate-generate (X) and estimate-disk (Z) update reactively on checkbox toggle', async () => {
    const wrap = mount(GenerateAudioModal, {
      props: {
        open: true,
        bookId: 1,
        totalUnits: 10,
        generatedCount: 0,
        bookSummaryGenerated: true,
        totalAnnotations: 5,
        totalWordCount: 0,
      },
    })
    // Default all on: delta = 10 + 0 + 5 = 15 → 3.0 min, 45 MB
    const gen = () => wrap.find('[data-testid="estimate-generate"]').text()
    const disk = () => wrap.find('[data-testid="estimate-disk"]').text()
    expect(gen()).toContain('3') // 15 * 0.2 = 3.0
    expect(disk()).toContain('45')

    // Annotations off: 10 + 0 + 0 = 10 → 2.0 min, 30 MB
    await wrap.find('input[data-testid="include-annotations"]').setValue(false)
    expect(gen()).toContain('2') // 10 * 0.2 = 2.0
    expect(disk()).toContain('30')
  })
})
