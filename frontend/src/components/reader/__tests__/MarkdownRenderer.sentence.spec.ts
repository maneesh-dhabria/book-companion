import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import MarkdownRenderer from '@/components/reader/MarkdownRenderer.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('MarkdownRenderer sentence-wrap', () => {
  it('wraps sentences with data-sentence-index', () => {
    const wrap = mount(MarkdownRenderer, {
      props: {
        content: 'First. Second. Third.',
        sentenceOffsetsChars: [0, 7, 15],
      },
    })
    const sentences = wrap.findAll('span.bc-sentence')
    expect(sentences.length).toBeGreaterThanOrEqual(3)
    expect(sentences[0].attributes('data-sentence-index')).toBe('0')
    const last = sentences[sentences.length - 1]
    expect(last.attributes('data-sentence-index')).toBe('2')
  })

  it('does not span across block boundaries', () => {
    const wrap = mount(MarkdownRenderer, {
      props: {
        content: 'First.\n\nSecond.',
        sentenceOffsetsChars: [0, 7],
      },
    })
    const paragraphs = wrap.findAll('p')
    expect(paragraphs.length).toBe(2)
    expect(paragraphs[0].findAll('span.bc-sentence').length).toBeGreaterThanOrEqual(1)
    expect(paragraphs[1].findAll('span.bc-sentence').length).toBeGreaterThanOrEqual(1)
  })

  it('applies bc-sentence-active to current sentenceIndex', async () => {
    const store = useTtsPlayerStore()
    const wrap = mount(MarkdownRenderer, {
      props: {
        content: 'A. B. C.',
        sentenceOffsetsChars: [0, 3, 6],
      },
    })
    store.sentenceIndex = 1
    await flushPromises()
    await flushPromises()
    const active = wrap.find('span.bc-sentence-active')
    expect(active.exists()).toBe(true)
    expect(active.attributes('data-sentence-index')).toBe('1')
  })
})
