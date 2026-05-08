import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

import SummaryTOCRail from '../SummaryTOCRail.vue'

class StubObserver {
  static lastCallback: ((records: unknown[]) => void) | null = null
  static instances: StubObserver[] = []
  callback: (records: unknown[]) => void
  observed: Element[] = []
  constructor(cb: (records: unknown[]) => void) {
    this.callback = cb
    StubObserver.lastCallback = cb
    StubObserver.instances.push(this)
  }
  observe(el: Element) {
    this.observed.push(el)
  }
  disconnect() {
    this.observed = []
  }
  unobserve() {}
  takeRecords() {
    return []
  }
}

beforeEach(() => {
  StubObserver.lastCallback = null
  StubObserver.instances = []
  vi.stubGlobal('IntersectionObserver', StubObserver)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SummaryTOCRail (FR-C08)', () => {
  it('extracts H2 + H3 headings with id slugs into a sticky nav', async () => {
    const html = `
      <h2 id="alpha">Alpha</h2>
      <p>x</p>
      <h2 id="bravo">Bravo</h2>
      <h3 id="bravo-detail">Bravo detail</h3>
      <h2 id="charlie">Charlie</h2>
      <h3 id="charlie-one">Charlie One</h3>
    `
    const w = mount(SummaryTOCRail, { props: { html } })
    await flushPromises()
    const links = w.findAll('a')
    expect(links).toHaveLength(5)
    expect(links.map((a) => a.attributes('href'))).toEqual([
      '#alpha',
      '#bravo',
      '#bravo-detail',
      '#charlie',
      '#charlie-one',
    ])
    expect(w.find('nav.toc-rail').exists()).toBe(true)
  })

  it('renders a single "Top" entry when html has no headings', async () => {
    const w = mount(SummaryTOCRail, { props: { html: '<p>just paragraphs</p>' } })
    await flushPromises()
    const items = w.findAll('.toc-item')
    expect(items).toHaveLength(1)
    expect(items[0].text()).toBe('Top')
    expect(w.findAll('a')).toHaveLength(0)
  })

  it('highlights the active heading when IntersectionObserver fires', async () => {
    const html = `<h2 id="one">One</h2><h2 id="two">Two</h2>`

    // Plant DOM nodes for observer targets.
    const a = document.createElement('h2')
    a.id = 'one'
    const b = document.createElement('h2')
    b.id = 'two'
    document.body.appendChild(a)
    document.body.appendChild(b)

    const w = mount(SummaryTOCRail, { props: { html } })
    await flushPromises()
    expect(StubObserver.lastCallback).toBeTruthy()
    StubObserver.lastCallback!([{ isIntersecting: true, target: b }])
    await flushPromises()

    const activeItem = w.find('.toc-item--active')
    expect(activeItem.exists()).toBe(true)
    expect(activeItem.text()).toBe('Two')

    a.remove()
    b.remove()
  })
})
