import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import ScopePicker from '../ScopePicker.vue'
import { useSettingsStore } from '@/stores/settings'
import type { SectionBrief } from '@/types'

vi.mock('@/api/readingState', () => ({
  getReadingStateByBook: vi.fn().mockResolvedValue({ sections: [] }),
}))

function makeSection(id: number, words: number, tokens: number): SectionBrief {
  return {
    id,
    book_id: 1,
    parent_id: null,
    order_index: id,
    section_type: 'chapter',
    title: `Ch ${id}`,
    word_count: words,
    content_char_count: words * 5,
    content_token_count: tokens,
    image_count: 0,
    has_summary: true,
    image_ids: [],
  } as never
}

function setReadingWpm(wpm: number) {
  const settings = useSettingsStore()
  // partial AppSettings is enough — ScopePicker only reads `reading.reading_wpm`
  settings.settings = {
    network: { host: '', port: 0, allow_lan: false, access_token: null },
    llm: { provider: '', config_dir: null, model: '', timeout_seconds: 0, max_retries: 0, max_budget_usd: 0 },
    summarization: { default_preset: '' },
    web: { show_cost_estimates: false },
    tts: { listen_wpm: 200 },
    reading: { reading_wpm: wpm },
  } as never
}

describe('ScopePicker chapter+reading metric (FR-21)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function mountAt(sections: SectionBrief[]) {
    return mount(ScopePicker, {
      props: { bookId: 1, sections },
    })
  }

  it('all_summaries default: shows total chapters and reading minutes (no tokens substring)', async () => {
    setReadingWpm(250)
    const sections = [makeSection(1, 1250, 500), makeSection(2, 2500, 1000)]
    const wrapper = mountAt(sections)
    // all_summaries → all selected
    const text = wrapper.text()
    // 2 of 2 chapters · ~15 min reading (3750 / 250 = 15)
    expect(text).toMatch(/2 of 2 chapters · ~15 min reading/)
    expect(text).not.toContain('tokens · ')
  })

  it('singular form when total === 1', async () => {
    setReadingWpm(250)
    const sections = [makeSection(1, 1250, 500)]
    const wrapper = mountAt(sections)
    expect(wrapper.text()).toMatch(/1 of 1 chapter · ~5 min reading/)
    expect(wrapper.text()).not.toMatch(/1 of 1 chapters/)
  })

  it('plural denominator + 0 selected case for specific_chapters', async () => {
    setReadingWpm(200)
    const sections = [makeSection(1, 200, 100), makeSection(2, 400, 200), makeSection(3, 600, 300)]
    const wrapper = mountAt(sections)
    await wrapper.find('[data-test="scope-mode-specific"]').setValue(true)
    expect(wrapper.text()).toMatch(/0 of 3 chapters · ~0 min reading/)
  })

  it('budget label has token tooltip via title attribute', async () => {
    setReadingWpm(250)
    const sections = [makeSection(1, 500, 500), makeSection(2, 500, 500)]
    const wrapper = mountAt(sections)
    await wrapper.find('[data-test="scope-mode-specific"]').setValue(true)
    const labelEl = wrapper.find('[data-test="scope-budget-label"]')
    expect(labelEl.exists()).toBe(true)
    expect(labelEl.attributes('title')).toMatch(/\d+ \/ 60,000 tokens/)
  })

  it('scope-mode tabstrip has ARIA tablist semantics', async () => {
    setReadingWpm(250)
    const sections = [makeSection(1, 100, 50)]
    const wrapper = mountAt(sections)
    expect(wrapper.find('[role="tablist"]').exists()).toBe(true)
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(2)
    const selected = tabs.find((t) => t.attributes('aria-selected') === 'true')
    expect(selected?.text()).toContain('All summaries')
  })
})
