import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import { useReaderStore, _setRouterForTests } from '@/stores/reader'

vi.mock('@/api/books', () => ({
  getBook: vi.fn(),
}))
vi.mock('@/api/sections', () => ({
  getSection: vi.fn(),
  listSections: vi.fn(),
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/books/:id/sections/:sectionId',
        name: 'section-detail',
        component: { template: '<div/>' },
      },
    ],
  })
}

const BOOK = {
  id: 1,
  title: 'B',
  status: 'ready',
  file_format: 'epub',
  file_size_bytes: 0,
  file_hash: 'x',
  authors: [],
  sections: [
    {
      id: 10,
      title: 'A',
      order_index: 0,
      section_type: 'chapter',
      has_summary: true,
      content_token_count: null,
      content_char_count: null,
    },
    {
      id: 11,
      title: 'B',
      order_index: 1,
      section_type: 'chapter',
      has_summary: false,
      content_token_count: null,
      content_char_count: null,
    },
  ],
  section_count: 2,
  cover_url: null,
  created_at: '',
  updated_at: '',
}

const SECTIONS_BY_ID: Record<number, unknown> = {
  10: {
    id: 10,
    book_id: 1,
    title: 'A',
    order_index: 0,
    section_type: 'chapter',
    content_token_count: null,
    content_md: 'orig',
    has_summary: true,
    summary_count: 1,
    annotation_count: 0,
    default_summary: { id: 1, preset_name: 'p', model_used: 'm', summary_char_count: 100, created_at: '', summary_md: 'sum' },
  },
  11: {
    id: 11,
    book_id: 1,
    title: 'B',
    order_index: 1,
    section_type: 'chapter',
    content_token_count: null,
    content_md: 'orig',
    has_summary: false,
    summary_count: 0,
    annotation_count: 0,
    default_summary: null,
  },
}

describe('reader store tab URL sync', () => {
  let router: Router

  beforeEach(async () => {
    setActivePinia(createPinia())
    router = makeRouter()
    _setRouterForTests(router)
    const books = await import('@/api/books')
    const sections = await import('@/api/sections')
    vi.mocked(books.getBook).mockResolvedValue(BOOK as never)
    vi.mocked(sections.getSection).mockImplementation(
      async (_b: number, sid: number) => SECTIONS_BY_ID[sid] as never,
    )
    vi.mocked(sections.listSections).mockResolvedValue(BOOK.sections as never)
  })

  afterEach(() => {
    _setRouterForTests(null)
  })

  it('loadSection reads ?tab=summary from route.query', async () => {
    await router.push({ name: 'section-detail', params: { id: '1', sectionId: '10' }, query: { tab: 'summary' } })
    const store = useReaderStore()
    await store.loadSection(1, 10)
    expect(store.contentMode).toBe('summary')
  })

  it('loadSection falls back to original when has_summary is false', async () => {
    await router.push({ name: 'section-detail', params: { id: '1', sectionId: '11' } })
    const store = useReaderStore()
    await store.loadSection(1, 11)
    expect(store.contentMode).toBe('original')
  })

  it('loadSection rewrites URL to ?tab=original when ?tab=summary on no-summary section', async () => {
    await router.push({ name: 'section-detail', params: { id: '1', sectionId: '11' }, query: { tab: 'summary' } })
    const store = useReaderStore()
    await store.loadSection(1, 11)
    expect(store.contentMode).toBe('original')
    expect(router.currentRoute.value.query.tab).toBe('original')
  })

  it('toggleContent calls router.replace with new tab param', async () => {
    await router.push({ name: 'section-detail', params: { id: '1', sectionId: '10' }, query: { tab: 'original' } })
    const store = useReaderStore()
    await store.loadSection(1, 10)
    const replaceSpy = vi.spyOn(router, 'replace')
    await store.toggleContent()
    expect(store.contentMode).toBe('summary')
    expect(replaceSpy).toHaveBeenCalled()
    const lastCall = replaceSpy.mock.calls.at(-1)![0] as { query?: { tab?: string } }
    expect(lastCall.query?.tab).toBe('summary')
  })

  it('loadSection dedupes concurrent calls for the same (book, section)', async () => {
    // Regression: BookDetailView's route watcher and navigateSection both
    // call loadSection on every navigation. Without dedupe this resulted
    // in two getSection() round-trips per navigation.
    await router.push({ name: 'section-detail', params: { id: '1', sectionId: '10' } })
    const store = useReaderStore()
    const sections = await import('@/api/sections')
    vi.mocked(sections.getSection).mockClear()
    await Promise.all([store.loadSection(1, 10), store.loadSection(1, 10)])
    expect(sections.getSection).toHaveBeenCalledTimes(1)
  })

  it('navigateSection preserves tab in destination URL (no-summary rewrite)', async () => {
    await router.push({ name: 'section-detail', params: { id: '1', sectionId: '10' }, query: { tab: 'summary' } })
    const store = useReaderStore()
    await store.loadBook(1, { routeSectionId: 10 })
    await store.navigateSection('next')
    expect(router.currentRoute.value.params.sectionId).toBe('11')
    expect(router.currentRoute.value.query.tab).toBe('original')
    expect(store.contentMode).toBe('original')
  })
})

