import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ScopePicker from '@/components/quiz/ScopePicker.vue'
import ChapterMultiSelect from '@/components/quiz/ChapterMultiSelect.vue'
import { COPY } from '@/components/quiz/copy'
import type { SectionBrief } from '@/types'

const readingStateMocks = vi.hoisted(() => ({
  getReadingStateByBook: vi.fn(),
  getContinueReading: vi.fn(),
  updateReadingState: vi.fn(),
}))
vi.mock('@/api/readingState', () => readingStateMocks)

function makeSection(overrides: Partial<SectionBrief>): SectionBrief {
  return {
    id: 1,
    title: 'Ch 1',
    order_index: 0,
    section_type: 'chapter',
    content_token_count: 5_000,
    content_char_count: 20_000,
    has_summary: true,
    last_failure_type: null,
    ...overrides,
  }
}

const SECTIONS: SectionBrief[] = [
  makeSection({ id: 1, title: 'Ch 1', content_token_count: 5_000 }),
  makeSection({ id: 2, title: 'Ch 2', content_token_count: 5_000 }),
  makeSection({ id: 3, title: 'Ch 3', content_token_count: 5_000 }),
  makeSection({ id: 99, title: 'Glossary', section_type: 'glossary', content_token_count: 1_000 }),
  makeSection({ id: 98, title: 'Notes', section_type: 'notes', content_token_count: 1_000 }),
]

const BIG_SECTIONS: SectionBrief[] = [
  makeSection({ id: 10, title: 'Big A', content_token_count: 35_000 }),
  makeSection({ id: 11, title: 'Big B', content_token_count: 35_000 }),
]

beforeEach(() => {
  setActivePinia(createPinia())
  Object.values(readingStateMocks).forEach((fn) => fn.mockReset())
  readingStateMocks.getReadingStateByBook.mockResolvedValue({ most_recent_section_ids: [] })
  localStorage.clear()
})

async function mountPicker(props: {
  sections?: SectionBrief[]
  bookId?: number
  budgetMax?: number
}) {
  const wrapper = mount(ScopePicker, {
    props: { bookId: 7, sections: SECTIONS, budgetMax: 60_000, ...props },
  })
  await flushPromises()
  return wrapper
}

describe('ScopePicker — D31 default scope', () => {
  it('defaults to recently-read chapters when within 48h', async () => {
    readingStateMocks.getReadingStateByBook.mockResolvedValue({
      most_recent_section_ids: [2, 1],
    })
    const wrapper = await mountPicker({})
    const exposed = wrapper.vm as unknown as {
      scopeMode: string
      selectedSectionIds: number[]
    }
    expect(exposed.scopeMode).toBe('specific_chapters')
    expect(exposed.selectedSectionIds).toEqual([2, 1])
  })

  it('falls back to last-used scope from localStorage when no recent read', async () => {
    localStorage.setItem(
      'quiz.lastScope.book-7',
      JSON.stringify({ mode: 'specific_chapters', section_ids: [3] }),
    )
    const wrapper = await mountPicker({})
    const exposed = wrapper.vm as unknown as {
      scopeMode: string
      selectedSectionIds: number[]
    }
    expect(exposed.scopeMode).toBe('specific_chapters')
    expect(exposed.selectedSectionIds).toEqual([3])
  })

  it('falls back to All Summaries when no signals', async () => {
    const wrapper = await mountPicker({})
    const exposed = wrapper.vm as unknown as { scopeMode: string }
    expect(exposed.scopeMode).toBe('all_summaries')
  })
})

describe('ScopePicker — chapter list filtering', () => {
  it('lists only chapter/part/section section_types', async () => {
    const wrapper = mount(ChapterMultiSelect, {
      props: { sections: SECTIONS, selectedIds: [], budgetMax: 60_000, budgetUsed: 0 },
    })
    const labels = wrapper.findAll('label').map((l) => l.text())
    expect(labels.some((t) => t.includes('Glossary'))).toBe(false)
    expect(labels.some((t) => t.includes('Notes'))).toBe(false)
    expect(labels.some((t) => t.includes('Ch 1'))).toBe(true)
    expect(labels.some((t) => t.includes('Ch 2'))).toBe(true)
    expect(labels.some((t) => t.includes('Ch 3'))).toBe(true)
  })
})

describe('ScopePicker — budget enforcement', () => {
  it('blocks chapter add at >100% budget with verbatim copy', async () => {
    const wrapper = await mountPicker({ sections: BIG_SECTIONS, budgetMax: 60_000 })
    // Switch to specific_chapters mode first
    await wrapper.find('[data-test="scope-mode-specific"]').trigger('change')
    await wrapper.find('[data-test="chapter-cb-10"]').setValue(true) // 35k OK
    await flushPromises()
    await wrapper.find('[data-test="chapter-cb-11"]').setValue(true) // would push to 70k
    await flushPromises()
    expect(wrapper.text()).toContain(COPY.wouldExceedBudget)
    const exposed = wrapper.vm as unknown as { selectedSectionIds: number[] }
    expect(exposed.selectedSectionIds).toEqual([10])
  })

  it('Start button disabled with helper text when 0 chapters in specific-chapters mode', async () => {
    const wrapper = await mountPicker({})
    await wrapper.find('[data-test="scope-mode-specific"]').trigger('change')
    await flushPromises()
    expect(wrapper.find('[data-test="start"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain(COPY.pickAtLeastOneChapter)
  })

  it('budget bar turns indigo <80%, amber 80-95%, red on overflow attempt', async () => {
    // <80%: select 5k of 60k → ~8% indigo
    const wrapper = await mountPicker({})
    await wrapper.find('[data-test="scope-mode-specific"]').trigger('change')
    await wrapper.find('[data-test="chapter-cb-1"]').setValue(true)
    await flushPromises()
    expect(wrapper.find('[data-test="budget-bar"]').attributes('data-state')).toBe('indigo')

    // amber band: bump budget down so 5k = >80% but <100%. budgetMax=6_250 → 5k=80%
    const wrapperAmber = await mountPicker({ budgetMax: 6_250 })
    await wrapperAmber.find('[data-test="scope-mode-specific"]').trigger('change')
    await wrapperAmber.find('[data-test="chapter-cb-1"]').setValue(true)
    await flushPromises()
    expect(wrapperAmber.find('[data-test="budget-bar"]').attributes('data-state')).toBe('amber')

    // red on overflow attempt (BIG_SECTIONS, budget 60k, 35k+35k attempt)
    const wrapperRed = await mountPicker({ sections: BIG_SECTIONS, budgetMax: 60_000 })
    await wrapperRed.find('[data-test="scope-mode-specific"]').trigger('change')
    await wrapperRed.find('[data-test="chapter-cb-10"]').setValue(true)
    await flushPromises()
    await wrapperRed.find('[data-test="chapter-cb-11"]').setValue(true)
    await flushPromises()
    expect(wrapperRed.find('[data-test="budget-bar"]').attributes('data-state')).toBe('red')
  })
})
