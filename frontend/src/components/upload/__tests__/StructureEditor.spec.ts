import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import StructureEditor from '../StructureEditor.vue'

vi.mock('@/api/sections', () => ({
  listSections: vi.fn(async () => [
    { id: 1, book_id: 99, title: 'A', order_index: 0, section_type: 'chapter' },
    { id: 2, book_id: 99, title: 'B', order_index: 1, section_type: 'chapter' },
    { id: 3, book_id: 99, title: 'C', order_index: 2, section_type: 'chapter' },
  ]),
  patchSection: vi.fn(async (_b, _id, p) => ({ id: 1, title: p.title, order_index: 0, section_type: 'chapter', book_id: 99 })),
  deleteSection: vi.fn(async () => undefined),
  mergeSections: vi.fn(async () => ({ id: 99, title: 'merged', order_index: 0, section_type: 'chapter', book_id: 99 })),
  reorderSections: vi.fn(async (_b, ids: number[]) =>
    ids.map((id, i) => ({ id, title: `S${id}`, order_index: i, section_type: 'chapter', book_id: 99 })),
  ),
  getEditImpact: vi.fn(async () => ({
    summaries_to_invalidate: [],
    invalidate_book_summary: false,
    summarized_section_count: 0,
  })),
  getSplitPreview: vi.fn(async () => ({ candidates: [], mode: 'heading' })),
  splitSection: vi.fn(async () => []),
}))

describe('StructureEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders sections after load', async () => {
    const w = mount(StructureEditor, {
      props: { bookId: 99, mode: 'wizard' },
    })
    await flushPromises()
    const list = w.find('[data-testid="section-list"]')
    expect(list.exists()).toBe(true)
    expect(list.text()).toContain('A')
    expect(list.text()).toContain('B')
    expect(list.text()).toContain('C')
  })

  it('disables Merge unless 2+ sections selected', async () => {
    const w = mount(StructureEditor, { props: { bookId: 99, mode: 'wizard' } })
    await flushPromises()
    const mergeBtn = w.find('[data-testid="merge-btn"]')
    expect(mergeBtn.attributes('disabled')).toBeDefined()
  })

  it('disables Bulk Delete when no selection', async () => {
    const w = mount(StructureEditor, { props: { bookId: 99, mode: 'wizard' } })
    await flushPromises()
    const btn = w.find('[data-testid="bulk-delete-btn"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('disables Split unless exactly 1 section selected', async () => {
    const w = mount(StructureEditor, { props: { bookId: 99, mode: 'wizard' } })
    await flushPromises()
    const splitBtn = w.find('[data-testid="split-btn"]')
    expect(splitBtn.attributes('disabled')).toBeDefined()
  })

  it('emits complete when Continue clicked', async () => {
    const w = mount(StructureEditor, { props: { bookId: 99, mode: 'wizard' } })
    await flushPromises()
    await w.find('[data-testid="structure-continue"]').trigger('click')
    expect(w.emitted('complete')).toBeTruthy()
  })

  it('shows undo banner after delete', async () => {
    const w = mount(StructureEditor, { props: { bookId: 99, mode: 'wizard' } })
    await flushPromises()
    await w.find('[data-testid="delete-1"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="undo-stack"]').exists()).toBe(true)
    expect(w.text()).toContain('Undo')
  })
})
