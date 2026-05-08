import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import BookSummaryTab from '../BookSummaryTab.vue'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/books/:id/sections/:sectionId', component: { template: '<div/>' } }],
  })
}

const opts = () => ({ global: { plugins: [createPinia(), makeRouter()] } })

beforeEach(() => {
  setActivePinia(createPinia())
})

const baseBook = (overrides: Record<string, unknown> = {}): never =>
  ({
    id: 3,
    sections: [
      { id: 1, order_index: 0, has_summary: true, default_summary_id: 10 },
      { id: 2, order_index: 1, has_summary: false, default_summary_id: null },
    ],
    default_summary: null,
    last_summary_failure: null,
    ...overrides,
  }) as never

describe('BookSummaryTab', () => {
  it('Empty state with N>=1 sections summarized: enabled Generate CTA', () => {
    const wrapper = mount(BookSummaryTab, { props: { book: baseBook() }, ...opts() })
    expect(wrapper.text()).toMatch(/1 of 2 sections summarized/)
    const cta = wrapper.find('button.generate-cta')
    expect(cta.attributes('disabled')).toBeUndefined()
  })

  it('Empty state with 0 sections summarized: Generate CTA disabled', () => {
    const wrapper = mount(BookSummaryTab, {
      props: {
        book: baseBook({
          sections: [{ id: 1, has_summary: false }],
        }) as never,
      },
      ...opts(),
    })
    const cta = wrapper.find('button.generate-cta')
    expect(cta.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toMatch(/at least one section/i)
  })

  it('Populated state: renders Markdown body and Read Section Summaries action', () => {
    const wrapper = mount(BookSummaryTab, {
      props: {
        book: baseBook({
          default_summary: { summary_md: '# Title\n\nBody.', generated_at: '2026-05-01T00:00:00Z' },
        }) as never,
      },
      ...opts(),
    })
    expect(wrapper.find('.markdown-body').exists()).toBe(true)
    expect(wrapper.text()).toContain('Read Section Summaries')
    expect(wrapper.text()).toContain('Regenerate')
  })

  it('Read Section Summaries skips front-matter and routes to first chapter (FR-B03)', async () => {
    const router = makeRouter()
    const wrapper = mount(BookSummaryTab, {
      props: {
        book: baseBook({
          status: 'PARSED',
          default_summary: { summary_md: '# Title', generated_at: '2026-05-01T00:00:00Z' },
          sections: [
            { id: 50, order_index: 0, section_type: 'copyright', has_summary: false },
            { id: 51, order_index: 1, section_type: 'chapter', has_summary: true, default_summary_id: 99 },
          ],
        }) as never,
      },
      global: { plugins: [createPinia(), router] },
    })
    const buttons = wrapper.findAll('button.btn-secondary')
    const cta = buttons.find((b) => b.text().includes('Read Section Summaries'))
    expect(cta).toBeDefined()
    await cta!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/books/3/sections/51')
  })

  it('Failed state: shows error and Retry CTA', () => {
    const wrapper = mount(BookSummaryTab, {
      props: {
        book: baseBook({
          last_summary_failure: {
            code: 'LLM_TIMEOUT',
            stderr: 'Provider timeout',
            at: '2026-05-01T00:00:00Z',
          },
        }) as never,
      },
      ...opts(),
    })
    expect(wrapper.text()).toContain('Provider timeout')
    expect(wrapper.find('button.retry-cta').exists()).toBe(true)
  })
})
