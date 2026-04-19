import { useSummarizationJobStore } from '@/stores/summarizationJob'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
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
})
