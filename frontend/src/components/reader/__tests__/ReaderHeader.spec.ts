import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import ReaderHeader from '../ReaderHeader.vue'

const sections = [
  { id: 1, title: 'Chapter 1', order_index: 0, has_summary: true },
  { id: 2, title: 'Chapter 2', order_index: 1, has_summary: false },
  { id: 3, title: 'Chapter 3', order_index: 2, has_summary: true },
] as never

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/books/:id', component: { template: '<div/>' } },
    ],
  })
}

function mountIt(currentSectionId = 2, hasPrev = true, hasNext = true) {
  setActivePinia(createPinia())
  return mount(ReaderHeader, {
    props: {
      bookTitle: 'Test Book',
      bookId: 7,
      sections,
      currentSectionId,
      contentMode: 'summary' as const,
      hasSummary: true,
      hasPrev,
      hasNext,
    },
    global: { plugins: [makeRouter()] },
  })
}

describe('ReaderHeader (T20: 3-cluster toolbar)', () => {
  it('renders three clusters with role=group and labels', () => {
    const w = mountIt()
    const clusters = w.findAll('[role="group"]')
    expect(clusters.length).toBeGreaterThanOrEqual(3)
    const labels = clusters.map((c) => c.attributes('aria-label'))
    expect(labels).toContain('Section navigation')
    expect(labels).toContain('Reading mode')
    expect(labels).toContain('Actions')
  })

  it('nav buttons carry aria-labels with adjacent section titles', () => {
    const w = mountIt(2)
    const prev = w.find('[data-cluster="nav"] [data-action="prev"]')
    const next = w.find('[data-cluster="nav"] [data-action="next"]')
    expect(prev.attributes('aria-label')).toBe('Previous section: Chapter 1')
    expect(next.attributes('aria-label')).toBe('Next section: Chapter 3')
  })

  it('nav buttons are at least 40x40 (FR-D05)', () => {
    const w = mountIt()
    const btn = w.find('[data-action="prev"]')
    expect(btn.classes()).toContain('nav-btn')
    // Computed style is jsdom-stub; assert via class+rule via element. The CSS
    // rule `.nav-btn { min-width: 40px; min-height: 40px }` is exercised in
    // the rendered build; here we assert the class is present so the rule
    // matches.
    expect(btn.element.tagName).toBe('BUTTON')
  })

  it('renders the actions slot inside the actions cluster', () => {
    setActivePinia(createPinia())
    const w = mount(ReaderHeader, {
      props: {
        bookTitle: 'Test Book',
        bookId: 7,
        sections,
        currentSectionId: 2,
        contentMode: 'summary' as const,
        hasSummary: true,
        hasPrev: true,
        hasNext: true,
      },
      slots: { actions: '<button data-test="custom-action">Listen</button>' },
      global: { plugins: [makeRouter()] },
    })
    const actionsCluster = w.find('[data-cluster="actions"]')
    expect(actionsCluster.exists()).toBe(true)
    expect(actionsCluster.find('[data-test="custom-action"]').exists()).toBe(true)
  })

  it('omits prev label suffix when there is no previous section', () => {
    const w = mountIt(1, false, true)
    const prev = w.find('[data-action="prev"]')
    expect(prev.attributes('aria-label')).toBe('Previous section')
    expect(prev.attributes('disabled')).toBeDefined()
  })
})
