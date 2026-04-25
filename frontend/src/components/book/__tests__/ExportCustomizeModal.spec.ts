import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ExportCustomizeModal from '@/components/book/ExportCustomizeModal.vue'

const sampleBook = {
  id: 3,
  title: 'Sample',
  default_summary_id: 1,
  sections: [
    { id: 10, title: 'Ch 1', has_summary: true, section_type: 'chapter' },
    { id: 11, title: 'Ch 2', has_summary: true, section_type: 'chapter' },
    { id: 12, title: 'Pending', has_summary: false, section_type: 'chapter' },
  ],
}

describe('ExportCustomizeModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(globalThis, 'fetch').mockImplementation((url: any) => {
      const u = String(url)
      if (u.includes('/api/v1/books/3'))
        return Promise.resolve(new Response(JSON.stringify(sampleBook)))
      return Promise.resolve(
        new Response('# X', {
          status: 200,
          headers: {
            'content-disposition': 'attachment; filename="x.md"',
            'x-empty-export': 'false',
          },
        }),
      )
    })
  })

  it('lists only sections with summaries and shows hidden count', async () => {
    const wrapper = mount(ExportCustomizeModal, {
      props: { bookId: 3, book: sampleBook },
    })
    await flushPromises()
    const items = wrapper.findAll('[data-testid="section-checkbox-row"]')
    expect(items.length).toBe(2)
    expect(wrapper.text()).toContain('2 of 3 sections summarized')
    expect(wrapper.text()).toContain('1 hidden')
  })

  it('omits the hidden-count clause when hidden = 0', async () => {
    const allSummed = {
      ...sampleBook,
      sections: sampleBook.sections.filter((s) => s.has_summary),
    }
    vi.spyOn(globalThis, 'fetch').mockImplementation((url: any) => {
      const u = String(url)
      if (u.includes('/api/v1/books/3'))
        return Promise.resolve(new Response(JSON.stringify(allSummed)))
      return Promise.resolve(new Response('# X', { status: 200 }))
    })
    const wrapper = mount(ExportCustomizeModal, {
      props: { bookId: 3, book: allSummed },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('2 of 2 sections summarized')
    expect(wrapper.text()).not.toContain('hidden')
  })

  it('Sections master toggle is indeterminate when partial', async () => {
    const wrapper = mount(ExportCustomizeModal, {
      props: { bookId: 3, book: sampleBook },
    })
    await flushPromises()
    await wrapper.find('[data-testid="section-checkbox-10"]').setValue(false)
    const master = wrapper.find('[data-testid="sections-master"]')
      .element as HTMLInputElement
    expect(master.indeterminate).toBe(true)
    expect(master.checked).toBe(false)
  })

  it('Sections master click flips indeterminate -> checked -> unchecked', async () => {
    const wrapper = mount(ExportCustomizeModal, {
      props: { bookId: 3, book: sampleBook },
    })
    await flushPromises()
    await wrapper.find('[data-testid="section-checkbox-10"]').setValue(false)
    const master = wrapper.find('[data-testid="sections-master"]')
    await master.trigger('click')
    expect(
      (
        wrapper.find('[data-testid="section-checkbox-10"]')
          .element as HTMLInputElement
      ).checked,
    ).toBe(true)
    expect(
      (
        wrapper.find('[data-testid="section-checkbox-11"]')
          .element as HTMLInputElement
      ).checked,
    ).toBe(true)
    await master.trigger('click')
    expect(
      (
        wrapper.find('[data-testid="section-checkbox-10"]')
          .element as HTMLInputElement
      ).checked,
    ).toBe(false)
    expect(
      (
        wrapper.find('[data-testid="section-checkbox-11"]')
          .element as HTMLInputElement
      ).checked,
    ).toBe(false)
  })

  it('Export click calls export endpoint with selection', async () => {
    const wrapper = mount(ExportCustomizeModal, {
      props: { bookId: 3, book: sampleBook },
    })
    await flushPromises()
    await wrapper.find('[data-testid="toggle-toc"]').setValue(false)
    await wrapper.find('[data-testid="section-checkbox-10"]').setValue(false)
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    await wrapper.find('[data-testid="modal-export-btn"]').trigger('click')
    await flushPromises()
    const exportCall = fetchSpy.mock.calls.find((c) =>
      String(c[0]).includes('/api/v1/export/book/3'),
    )
    expect(exportCall).toBeDefined()
    const url = String(exportCall![0])
    expect(url).toContain('include_toc=false')
    expect(url).toMatch(/exclude_section=10/)
  })

  it('falls back to cached sections on refresh-fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url: any) => {
      const u = String(url)
      if (u.includes('/api/v1/books/3')) return Promise.reject(new Error('network'))
      return Promise.resolve(new Response('# X', { status: 200 }))
    })
    const wrapper = mount(ExportCustomizeModal, {
      props: { bookId: 3, book: sampleBook },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Could not refresh')
    expect(wrapper.findAll('[data-testid="section-checkbox-row"]').length).toBe(2)
  })

  it('disables Book summary checkbox when book has no default_summary_id', async () => {
    const noSummary = { ...sampleBook, default_summary_id: null }
    const wrapper = mount(ExportCustomizeModal, {
      props: { bookId: 3, book: noSummary },
    })
    await flushPromises()
    const cb = wrapper.find('[data-testid="toggle-book-summary"]')
      .element as HTMLInputElement
    expect(cb.disabled).toBe(true)
  })
})
