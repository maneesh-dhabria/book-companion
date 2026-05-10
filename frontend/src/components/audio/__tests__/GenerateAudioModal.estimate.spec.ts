import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/audio', () => ({
  audioApi: { start: vi.fn() },
}))

import GenerateAudioModal from '@/components/audio/GenerateAudioModal.vue'
import { useSettingsStore } from '@/stores/settings'

function withSettingsListenWpm(wpm: number) {
  const store = useSettingsStore()
  // @ts-expect-error — partial mount of AppSettings is fine for test fixtures
  store.settings = { tts: { listen_wpm: wpm }, reading: { reading_wpm: 250 } }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('GenerateAudioModal — FR-13 3-field estimate row', () => {
  it('empty book (17 sections, 0 MP3s): renders 3 estimate spans + subline N of M sections', () => {
    withSettingsListenWpm(200)
    const wrap = mount(GenerateAudioModal, {
      props: {
        open: true,
        bookId: 1,
        totalUnits: 17,
        generatedCount: 0,
        bookSummaryGenerated: true,
        totalAnnotations: 0,
        totalWordCount: 85000,
      },
    })
    const gen = wrap.find('[data-testid="estimate-generate"]')
    const listen = wrap.find('[data-testid="estimate-listen"]')
    const disk = wrap.find('[data-testid="estimate-disk"]')
    expect(gen.exists()).toBe(true)
    expect(listen.exists()).toBe(true)
    expect(disk.exists()).toBe(true)
    expect(gen.text()).toMatch(/^~\d+(\.\d+)?min to generate$/)
    expect(listen.text()).toMatch(/^~\d+min to listen$/)
    expect(disk.text()).toMatch(/^~\d+MB on disk$/)

    // 17 sections × 0.2 min = 3.4 min generation
    expect(gen.text()).toContain('3.4')
    // 85000 words / 200 wpm = 425 min listen
    expect(listen.text()).toContain('425')
    // 17 × 3 MB = 51 MB on disk
    expect(disk.text()).toContain('51')

    const subline = wrap.find('[data-testid="estimate-subline"]')
    expect(subline.text()).toBe('Generating 17 of 17 sections')
    expect(subline.text()).not.toContain('(delta)')
  })

  it('partial (3 of 17 missing): X/Z reflect 3-section delta, Y reflects whole-book listen', () => {
    withSettingsListenWpm(200)
    const wrap = mount(GenerateAudioModal, {
      props: {
        open: true,
        bookId: 1,
        totalUnits: 17,
        generatedCount: 14,
        bookSummaryGenerated: true,
        totalAnnotations: 0,
        totalWordCount: 85000,
      },
    })
    const gen = wrap.find('[data-testid="estimate-generate"]').text()
    const listen = wrap.find('[data-testid="estimate-listen"]').text()
    const disk = wrap.find('[data-testid="estimate-disk"]').text()

    // 3 sections × 0.2 = 0.6 min
    expect(gen).toContain('0.6')
    // Whole-book listen unchanged: 85000/200 = 425
    expect(listen).toContain('425')
    // 3 × 3 = 9 MB
    expect(disk).toContain('9')

    expect(wrap.find('[data-testid="estimate-subline"]').text()).toBe(
      'Generating 3 of 17 sections',
    )
  })

  it('all-already-generated (0 of 17 missing): button label "Nothing to generate" + disabled', () => {
    withSettingsListenWpm(200)
    const wrap = mount(GenerateAudioModal, {
      props: {
        open: true,
        bookId: 1,
        totalUnits: 17,
        generatedCount: 17,
        bookSummaryGenerated: true,
        totalAnnotations: 0,
        totalWordCount: 85000,
      },
    })
    const btn = wrap.find('button[data-testid="confirm"]')
    expect(btn.text()).toBe('Nothing to generate')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)

    // All checkboxes should be disabled when their delta is 0.
    const sectionsCb = wrap.find(
      'input[data-testid="include-section-summaries"]',
    ).element as HTMLInputElement
    const bookCb = wrap.find('input[data-testid="include-book-summary"]')
      .element as HTMLInputElement
    const annCb = wrap.find('input[data-testid="include-annotations"]')
      .element as HTMLInputElement
    expect(sectionsCb.disabled).toBe(true)
    expect(bookCb.disabled).toBe(true)
    expect(annCb.disabled).toBe(true)
  })
})
