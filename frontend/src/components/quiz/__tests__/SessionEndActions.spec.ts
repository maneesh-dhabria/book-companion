import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import SessionEndActions from '@/components/quiz/SessionEndActions.vue'
import ExportSessionModal from '@/components/quiz/ExportSessionModal.vue'
import { COPY } from '@/components/quiz/copy'
import type { QuizSessionListItem } from '@/types'

vi.mock('@/api/quizSessions', () => ({
  stopSession: vi.fn(),
}))

const baseSession: QuizSessionListItem = {
  id: 42,
  book_id: 1,
  scope: { mode: 'all_summaries', section_ids: null },
  theme: null,
  status: 'in_progress',
  created_at: '2026-05-09T00:00:00Z',
  ended_at: null,
  question_count: 1,
  tally: { got_it: 1, partial: 0, missed: 0, skipped: 0, discarded: 0 },
  is_warm_up_session: false,
}

beforeEach(() => {
  setActivePinia(createPinia())
})
afterEach(() => vi.clearAllMocks())

describe('SessionEndActions', () => {
  it('Stop button disables on click and calls stopSession', async () => {
    const api = await import('@/api/quizSessions')
    let resolve!: (v: QuizSessionListItem) => void
    vi.mocked(api.stopSession).mockReturnValue(
      new Promise<QuizSessionListItem>((r) => {
        resolve = r
      }),
    )
    const wrapper = mount(SessionEndActions, {
      props: { session: baseSession, bookSlug: 'book' },
    })
    const stop = wrapper.find('button[data-test="stop"]')
    expect(stop.attributes('disabled')).toBeUndefined()
    await stop.trigger('click')
    expect(stop.attributes('disabled')).toBeDefined()
    resolve({ ...baseSession, status: 'completed' })
    await flushPromises()
    // Emits stopped after success
    expect(wrapper.emitted('stopped')).toBeTruthy()
  })

  it('Export button disabled when session.status === "abandoned" (E15 / FR-105)', () => {
    const wrapper = mount(SessionEndActions, {
      props: { session: { ...baseSession, status: 'abandoned' }, bookSlug: 'book' },
    })
    expect(wrapper.find('button[data-test="export"]').attributes('disabled')).toBeDefined()
  })

  it('Export button shown but enabled for in_progress with at least one tally', () => {
    const wrapper = mount(SessionEndActions, {
      props: { session: baseSession, bookSlug: 'book' },
    })
    expect(wrapper.find('button[data-test="export"]').attributes('disabled')).toBeUndefined()
  })

  it('clicking Export opens the ExportSessionModal', async () => {
    const wrapper = mount(SessionEndActions, {
      props: { session: { ...baseSession, status: 'completed' }, bookSlug: 'book' },
    })
    expect(wrapper.findComponent(ExportSessionModal).exists()).toBe(false)
    await wrapper.find('button[data-test="export"]').trigger('click')
    expect(wrapper.findComponent(ExportSessionModal).exists()).toBe(true)
  })

  it('shows abandoned-export error microcopy when export disabled', () => {
    const wrapper = mount(SessionEndActions, {
      props: { session: { ...baseSession, status: 'abandoned' }, bookSlug: 'book' },
    })
    expect(wrapper.text()).toContain(COPY.abandonedExportError)
  })
})

describe('ExportSessionModal', () => {
  it('triggers download with correct filename on confirm', async () => {
    // Stub anchor + click + URL
    const stubAnchor = {
      href: '',
      download: '',
      target: '',
      rel: '',
      click: vi.fn(),
      remove: vi.fn(),
      style: {} as Record<string, string>,
      setAttribute: vi.fn(),
    } as unknown as HTMLAnchorElement
    const origCreate = document.createElement
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'a') return stubAnchor
      return origCreate.call(document, tag)
    })
    const appendSpy = vi
      .spyOn(document.body, 'appendChild')
      .mockImplementation((node) => node as Node)
    vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node as Node)

    const wrapper = mount(ExportSessionModal, {
      props: {
        session: { ...baseSession, status: 'completed' },
        bookSlug: 'art-of-war',
      },
    })
    await wrapper.find('button[data-test="confirm-export"]').trigger('click')
    expect((stubAnchor as unknown as { download: string }).download).toBe(
      'art-of-war_quiz_session_42.md',
    )
    expect((stubAnchor as unknown as { href: string }).href).toContain(
      '/api/v1/quiz-sessions/42/export?fmt=markdown',
    )
    expect(stubAnchor.click).toHaveBeenCalled()
    appendSpy.mockRestore()
  })

  it('emits close on cancel', async () => {
    const wrapper = mount(ExportSessionModal, {
      props: {
        session: { ...baseSession, status: 'completed' },
        bookSlug: 'book',
      },
    })
    await wrapper.find('button[data-test="cancel-export"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
