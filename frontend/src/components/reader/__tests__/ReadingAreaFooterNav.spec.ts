import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ReadingAreaFooterNav from '../ReadingAreaFooterNav.vue'

const prev = { id: 5, title: 'Prev Section' }
const next = { id: 7, title: 'Next Section' }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/books/:id/sections/:sectionId', component: { template: '<div/>' } }],
  })
}

const opts = () => ({ global: { plugins: [makeRouter()] } })

describe('ReadingAreaFooterNav', () => {
  it('renders both links when both prev and next exist', () => {
    const wrapper = mount(ReadingAreaFooterNav, {
      props: { bookId: 3, prev, next, currentTab: 'summary' },
      ...opts(),
    })
    expect(wrapper.text()).toContain('← Previous: Prev Section')
    expect(wrapper.text()).toContain('Next: Next Section →')
    const links = wrapper.findAll('a')
    expect(links.length).toBe(2)
    expect(links[0].attributes('href')).toContain('/books/3/sections/5')
    expect(links[0].attributes('href')).toContain('tab=summary')
    expect(links[1].attributes('href')).toContain('/books/3/sections/7')
  })

  it('renders only Next on first section', () => {
    const wrapper = mount(ReadingAreaFooterNav, {
      props: { bookId: 3, prev: null, next, currentTab: 'original' },
      ...opts(),
    })
    expect(wrapper.text()).not.toContain('Previous')
    expect(wrapper.text()).toContain('Next: Next Section →')
    expect(wrapper.findAll('a').length).toBe(1)
  })

  it('renders only Previous on last section', () => {
    const wrapper = mount(ReadingAreaFooterNav, {
      props: { bookId: 3, prev, next: null, currentTab: 'summary' },
      ...opts(),
    })
    expect(wrapper.text()).toContain('← Previous: Prev Section')
    expect(wrapper.text()).not.toContain('Next:')
  })

  it('renders nothing when both prev and next are null', () => {
    const wrapper = mount(ReadingAreaFooterNav, {
      props: { bookId: 3, prev: null, next: null, currentTab: 'summary' },
      ...opts(),
    })
    expect(wrapper.findAll('a').length).toBe(0)
    expect(wrapper.find('footer').exists()).toBe(false)
  })

  it('preserves currentTab=original in hrefs', () => {
    const wrapper = mount(ReadingAreaFooterNav, {
      props: { bookId: 3, prev, next, currentTab: 'original' },
      ...opts(),
    })
    const links = wrapper.findAll('a')
    links.forEach((link) => expect(link.attributes('href')).toContain('tab=original'))
  })
})
