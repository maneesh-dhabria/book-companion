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

  it('emits stable id slugs on h2 and h3, with collisions suffixed (FR-C07)', () => {
    const w = mount(MarkdownRenderer, {
      props: {
        content: '## Foo\n\n## Foo\n\n### Foo Bar\n\n### Foo Bar',
      },
    })
    const html = w.html()
    expect(html).toMatch(/<h2[^>]*id="foo"/)
    expect(html).toMatch(/<h2[^>]*id="foo-1"/)
    expect(html).toMatch(/<h3[^>]*id="foo-bar"/)
    expect(html).toMatch(/<h3[^>]*id="foo-bar-1"/)
  })

  it('falls back to section-N when heading has no slugifiable text (FR-C07)', () => {
    const w = mount(MarkdownRenderer, {
      props: { content: '## ✨\n\n## More text' },
    })
    const html = w.html()
    expect(html).toMatch(/<h2[^>]*id="section-0"/)
    expect(html).toMatch(/<h2[^>]*id="more-text"/)
  })

  it('does NOT emit ids on h1, h4, h5, h6 (only h2/h3 per FR-C07)', () => {
    const w = mount(MarkdownRenderer, {
      props: { content: '# Title\n\n## Sub\n\n#### Deep' },
    })
    const html = w.html()
    expect(html).not.toMatch(/<h1[^>]*id=/)
    expect(html).not.toMatch(/<h4[^>]*id=/)
    expect(html).toMatch(/<h2[^>]*id="sub"/)
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
