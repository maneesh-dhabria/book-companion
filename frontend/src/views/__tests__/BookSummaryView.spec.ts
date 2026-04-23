import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

const mockGetBook = vi.fn()
const mockStartBookSummary = vi.fn()
const mockListPresets = vi.fn()
const mockConnectSSE = vi.fn(() => ({ close: vi.fn() }))

vi.mock('@/api/books', () => ({
  getBook: (...args: unknown[]) => mockGetBook(...args),
}))
vi.mock('@/api/bookSummary', () => ({
  startBookSummary: (...args: unknown[]) => mockStartBookSummary(...args),
}))
vi.mock('@/api/presets', () => ({
  listSummarizerPresets: (...args: unknown[]) => mockListPresets(...args),
}))
vi.mock('@/api/processing', () => ({
  connectSSE: () => mockConnectSSE(),
}))

async function loadView() {
  const mod = await import('../BookSummaryView.vue')
  return mod.default
}

function makeRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/books/:id/summary', name: 'book-summary', component: { template: '<div />' } },
    ],
  })
  return router
}

describe('BookSummaryView', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    mockListPresets.mockResolvedValue({
      presets: [
        { id: 'practitioner_bullets', label: 'Practitioner', description: '', facets: {}, system: true },
        { id: 'executive_brief', label: 'Executive', description: '', facets: {}, system: true },
      ],
      default_id: 'practitioner_bullets',
    })
  })

  afterEach(() => {
    mockGetBook.mockReset()
    mockStartBookSummary.mockReset()
    mockListPresets.mockReset()
    mockConnectSSE.mockReset()
  })

  it('renders book-level summary markdown when present', async () => {
    mockGetBook.mockResolvedValue({
      id: 1,
      title: 'Test Book',
      summary_progress: { summarized: 3, total: 5 },
      default_summary: { id: 99, preset_name: 'executive_brief', summary_md: '# Book summary' },
    })
    const router = makeRouter()
    await router.push('/books/1/summary')
    await router.isReady()
    const View = await loadView()
    const w = mount(View, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('Book summary')
    expect(w.text()).toContain('3 of 5 sections summarized')
  })

  it('disables Generate button with tooltip when no section summaries', async () => {
    mockGetBook.mockResolvedValue({
      id: 1,
      title: 'Test',
      summary_progress: { summarized: 0, total: 5 },
      default_summary: null,
    })
    const router = makeRouter()
    await router.push('/books/1/summary')
    await router.isReady()
    const View = await loadView()
    const w = mount(View, { global: { plugins: [router] } })
    await flushPromises()
    const btn = w.find('[data-testid="generate-btn"]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('title')).toContain('Summarize sections first')
  })

  it('opens modal on Generate click and POSTs on submit', async () => {
    mockGetBook.mockResolvedValue({
      id: 1,
      title: 'Test',
      summary_progress: { summarized: 3, total: 5 },
      default_summary: null,
      last_used_preset: 'executive_brief',
    })
    mockStartBookSummary.mockResolvedValue({ job_id: 42 })
    const router = makeRouter()
    await router.push('/books/1/summary')
    await router.isReady()
    const View = await loadView()
    const w = mount(View, { global: { plugins: [router] } })
    await flushPromises()
    await w.find('[data-testid="generate-btn"]').trigger('click')
    await flushPromises()
    // Modal is mounted, pre-select should be executive_brief.
    const cards = w.findAll('[data-testid="preset-card"]')
    expect(cards.length).toBeGreaterThan(0)
    await w.find('[data-testid="submit"]').trigger('click')
    await flushPromises()
    expect(mockStartBookSummary).toHaveBeenCalledWith(1, {
      preset_name: 'executive_brief',
    })
  })
})
