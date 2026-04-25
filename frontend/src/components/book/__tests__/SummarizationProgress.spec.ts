import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { useUiStore } from '@/stores/ui'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SummarizationProgress from '../SummarizationProgress.vue'

describe('SummarizationProgress', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders N of M text', () => {
    const w = mount(SummarizationProgress, {
      props: { bookId: 1, summarized: 4, total: 12 },
    })
    expect(w.text()).toMatch(/4 of 12 sections summarized/)
  })

  it('shows Summarize pending button when summarized < total', () => {
    const w = mount(SummarizationProgress, {
      props: { bookId: 1, summarized: 4, total: 12 },
    })
    expect(w.find('button').text()).toMatch(/Summarize pending/)
  })

  it('hides when total=0', () => {
    const w = mount(SummarizationProgress, {
      props: { bookId: 1, summarized: 0, total: 0 },
    })
    expect(w.html()).toBe('<!--v-if-->')
  })

  it('button disabled + re-labeled during active job', async () => {
    const w = mount(SummarizationProgress, {
      props: { bookId: 1, summarized: 4, total: 12 },
    })
    const s = useSummarizationJobStore()
    s.jobId = 99
    await w.vm.$nextTick()
    const btn = w.find('button')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.text()).toMatch(/Summarizing…/)
  })

  // FR-F2.5 — starting state spinner + error toast
  it('disables button + shows inline spinner while POST is in flight', async () => {
    const job = useSummarizationJobStore()
    let resolve: (v?: unknown) => void = () => {}
    vi.spyOn(job, 'startJob').mockImplementation(
      () => new Promise((r) => { resolve = r as never }),
    )
    const w = mount(SummarizationProgress, {
      props: { bookId: 1, summarized: 0, total: 5, failedAndPending: 0 },
    })
    const btn = w.find('button.btn')
    await btn.trigger('click')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
    expect(w.find('.inline-spinner').exists()).toBe(true)
    resolve!()
    await flushPromises()
    expect(w.find('.inline-spinner').exists()).toBe(false)
  })

  it('fires error toast if startJob rejects', async () => {
    const job = useSummarizationJobStore()
    vi.spyOn(job, 'startJob').mockRejectedValue(new Error('upstream 503'))
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    const w = mount(SummarizationProgress, {
      props: { bookId: 1, summarized: 0, total: 5, failedAndPending: 0 },
    })
    await w.find('button.btn').trigger('click')
    await flushPromises()
    const errCall = toastSpy.mock.calls.find((c) => c[1] === 'error')
    expect(errCall).toBeDefined()
    expect(String(errCall![0])).toContain('upstream 503')
  })
})
