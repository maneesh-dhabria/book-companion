import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownRenderer from '../MarkdownRenderer.vue'

describe('MarkdownRenderer scoped styles', () => {
  it('renders root with markdown-body class', () => {
    const wrapper = mount(MarkdownRenderer, { props: { content: '- a\n- b\n' } })
    expect(wrapper.element.classList.contains('markdown-body')).toBe(true)
  })

  it('renders <ul> with list items', () => {
    const wrapper = mount(MarkdownRenderer, { props: { content: '- a\n- b\n' } })
    const ul = wrapper.element.querySelector('ul')
    expect(ul).toBeTruthy()
    expect(ul!.querySelectorAll('li').length).toBe(2)
  })

  it('renders nested <ul>', () => {
    const md = '- a\n  - b\n'
    const wrapper = mount(MarkdownRenderer, { props: { content: md } })
    const nested = wrapper.element.querySelector('ul ul')
    expect(nested).toBeTruthy()
  })

  it('renders <table> from pipe markdown', () => {
    const md = '| a | b |\n|---|---|\n| 1 | 2 |\n'
    const wrapper = mount(MarkdownRenderer, { props: { content: md } })
    const tbl = wrapper.element.querySelector('table')
    expect(tbl).toBeTruthy()
    expect(tbl!.querySelectorAll('th').length).toBe(2)
    expect(tbl!.querySelectorAll('td').length).toBe(2)
  })
})
