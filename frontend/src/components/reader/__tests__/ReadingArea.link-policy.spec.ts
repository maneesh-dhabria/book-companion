import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReadingArea from '../ReadingArea.vue'

const render = (md: string) => {
  const w = mount(ReadingArea, {
    props: { content: md, hasPrev: false, hasNext: false },
  })
  return w.html()
}

describe('ReadingArea link policy', () => {
  it('relative anchor → span', () => {
    const html = render('See [the intro](#intro) above.')
    expect(html).not.toMatch(/<a[^>]+href="#intro"/)
    expect(html).toMatch(/<span[^>]*>the intro<\/span>/)
  })

  it('external https → target=_blank rel=noopener noreferrer', () => {
    const html = render('Visit [site](https://example.com).')
    expect(html).toMatch(
      /<a[^>]+href="https:\/\/example\.com"[^>]+target="_blank"[^>]+rel="noopener noreferrer"/,
    )
  })

  it('javascript: scheme never renders as <a>', () => {
    // markdown-it rejects the javascript: scheme at parse time, so the
    // link never reaches DOMPurify / link-policy. Either outcome is safe:
    // anchor stripped by markdown-it or (hypothetically) span-wrapped by us.
    const html = render('[click](javascript:alert(1))')
    expect(html).not.toMatch(/<a[^>]*href="javascript:/i)
  })

  it('relative path (./ch2.xhtml) → span', () => {
    const html = render('[next](./ch2.xhtml)')
    expect(html).not.toMatch(/<a[^>]*href="\.\/ch2\.xhtml"/)
    expect(html).toMatch(/<span[^>]*>next<\/span>/)
  })
})
