import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MarkdownRenderer from '../MarkdownRenderer.vue'

describe('MarkdownRenderer', () => {
  it('renders bold and lists from markdown', () => {
    const w = mount(MarkdownRenderer, {
      props: { content: '**bold** and\n\n- item 1\n- item 2' },
    })
    expect(w.html()).toContain('<strong>bold</strong>')
    expect(w.html()).toContain('<ul>')
    expect(w.findAll('li')).toHaveLength(2)
  })

  it('sanitizes script tags', () => {
    const w = mount(MarkdownRenderer, {
      props: { content: '<script>alert(1)</script>safe' },
    })
    expect(w.html()).not.toContain('<script>')
    expect(w.text()).toContain('safe')
  })

  it('external links get target=_blank rel=noopener noreferrer', () => {
    const w = mount(MarkdownRenderer, {
      props: { content: 'See [site](https://example.com).' },
    })
    const a = w.find('a[href="https://example.com"]')
    expect(a.exists()).toBe(true)
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toContain('noopener')
  })

  it('internal anchor links become spans', () => {
    const w = mount(MarkdownRenderer, {
      props: { content: 'Jump to [here](#anchor).' },
    })
    expect(w.html()).not.toMatch(/<a[^>]*href="#anchor"/)
    expect(w.html()).toMatch(/<span[^>]*>here<\/span>/)
  })

  it('empties alt for decorative image placeholder', () => {
    const w = mount(MarkdownRenderer, {
      props: { content: '![image](https://example.com/foo.png)' },
    })
    const img = w.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('alt')).toBe('')
  })
})
