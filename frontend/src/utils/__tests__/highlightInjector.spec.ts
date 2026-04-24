import { describe, expect, it } from 'vitest'
import { applyHighlights } from '../highlightInjector'

describe('applyHighlights', () => {
  it('returns input unchanged when showInline=false', () => {
    const html = '<p>text</p>'
    expect(
      applyHighlights(
        html,
        [{ id: 1, text_start: 0, text_end: 4, selected_text: 'text' }],
        { showInline: false },
      ),
    ).toBe(html)
  })

  it('returns input unchanged when annotations are empty', () => {
    expect(applyHighlights('<p>x</p>', [], { showInline: true })).toBe('<p>x</p>')
  })

  it('wraps a single annotation in a <mark> with id + data-annotation-id', () => {
    const html = '<p>The value proposition is core.</p>'
    const out = applyHighlights(
      html,
      [
        {
          id: 1,
          text_start: 4,
          text_end: 21,
          selected_text: 'value proposition',
          prefix: 'The ',
          suffix: ' is',
        },
      ],
      { showInline: true },
    )
    expect(out).toContain('data-annotation-id="1"')
    expect(out).toContain('id="ann-1"')
    expect(out).toContain('value proposition')
  })

  it('falls back to prefix/suffix match when offsets mismatch', () => {
    const html = '<p>strategy then strategy again.</p>'
    const out = applyHighlights(
      html,
      [
        {
          id: 1,
          text_start: 999,
          text_end: 1007,
          selected_text: 'strategy',
          prefix: 'then ',
          suffix: ' again',
        },
      ],
      { showInline: true },
    )
    expect(out).toContain('data-annotation-id="1"')
    const thenIdx = out.indexOf('then')
    const markIdx = out.indexOf('<mark')
    expect(markIdx).toBeGreaterThan(thenIdx)
  })

  it('skips annotation when neither offset nor selected_text matches', () => {
    const html = '<p>unrelated</p>'
    const out = applyHighlights(
      html,
      [{ id: 1, text_start: 0, text_end: 7, selected_text: 'missing' }],
      { showInline: true },
    )
    expect(out).not.toContain('<mark')
  })

  it('wraps cross-block selection (uses selected_text fallback)', () => {
    const html = '<p>hello world.</p><p>next paragraph.</p>'
    // The plaintext view is 'hello world.next paragraph.' — no whitespace
    // between the two blocks. Picking a range that straddles them exercises
    // the block-split branch of the injector.
    const out = applyHighlights(
      html,
      [
        {
          id: 1,
          text_start: 6,
          text_end: 17,
          selected_text: 'world.next p',
        },
      ],
      { showInline: true },
    )
    expect(out).toContain('data-annotation-id="1"')
    const idAttrs = out.match(/id="ann-1"/g) || []
    expect(idAttrs.length).toBeLessThanOrEqual(1)
  })
})
