import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import BookCard from '@/components/library/BookCard.vue'
import BookTable from '@/components/library/BookTable.vue'
import FilterRow from '@/components/library/FilterRow.vue'
import { useUiStore } from '@/stores/ui'

const BOOK = {
  id: 1,
  title: 'Art of War',
  authors: [{ id: 1, name: 'Sun Tzu' }],
  status: 'completed',
  file_format: 'epub',
  section_count: 13,
  eval_passed: 12,
  eval_total: 13,
  updated_at: '2026-05-01T00:00:00Z',
  cover_url: null,
  tags: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('Bulk select gate (FR-F03)', () => {
  it('FilterRow exposes a Select toggle with bulk-select-toggle test id', () => {
    const w = mount(FilterRow)
    const btn = w.find('[data-testid="bulk-select-toggle"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('aria-pressed')).toBe('false')
  })

  it('toggling Select flips ui.bulkSelectMode', async () => {
    const w = mount(FilterRow)
    const ui = useUiStore()
    expect(ui.bulkSelectMode).toBe(false)
    await w.find('[data-testid="bulk-select-toggle"]').trigger('click')
    expect(ui.bulkSelectMode).toBe(true)
  })

  it('BookCard hides checkbox when ui.bulkSelectMode === false', () => {
    const w = mount(BookCard, {
      props: { book: BOOK as never, selected: false },
      global: { stubs: { 'router-link': { template: '<a><slot/></a>' } } },
    })
    expect(w.find('.book-card-select').exists()).toBe(false)
  })

  it('BookCard renders checkbox when ui.bulkSelectMode === true', async () => {
    const ui = useUiStore()
    ui.toggleBulkSelect(true)
    const w = mount(BookCard, {
      props: { book: BOOK as never, selected: false },
      global: { stubs: { 'router-link': { template: '<a><slot/></a>' } } },
    })
    expect(w.find('.book-card-select').exists()).toBe(true)
  })

  it('BookTable hides checkbox columns when ui.bulkSelectMode === false', () => {
    const w = mount(BookTable, {
      props: { books: [BOOK as never], loading: false, selectedIds: [] },
      global: { stubs: { 'router-link': { template: '<a><slot/></a>' } } },
    })
    expect(w.find('.col-checkbox').exists()).toBe(false)
  })

  it('BookTable renders checkbox columns when ui.bulkSelectMode === true', () => {
    const ui = useUiStore()
    ui.toggleBulkSelect(true)
    const w = mount(BookTable, {
      props: { books: [BOOK as never], loading: false, selectedIds: [] },
      global: { stubs: { 'router-link': { template: '<a><slot/></a>' } } },
    })
    expect(w.findAll('.col-checkbox').length).toBeGreaterThan(0)
  })
})
