import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AnnotationPlaylistRow from '@/components/audio/AnnotationPlaylistRow.vue'

describe('AnnotationPlaylistRow', () => {
  it('renders highlight + audible cue + note when annotation has note', () => {
    const wrap = mount(AnnotationPlaylistRow, {
      props: {
        annotation: { id: 1, selected_text: 'highlighted text', note: 'my thought' },
        index: 0,
      },
    })
    expect(wrap.text()).toContain('highlighted text')
    expect(wrap.find('[data-testid="audible-cue"]').exists()).toBe(true)
    expect(wrap.text()).toContain('my thought')
  })

  it('hides cue when no note', () => {
    const wrap = mount(AnnotationPlaylistRow, {
      props: {
        annotation: { id: 1, selected_text: 'just hl', note: null },
        index: 0,
      },
    })
    expect(wrap.find('[data-testid="audible-cue"]').exists()).toBe(false)
  })

  it('applies bc-sentence-active to playing row', () => {
    const wrap = mount(AnnotationPlaylistRow, {
      props: {
        annotation: { id: 1, selected_text: 'a', note: null },
        index: 0,
        isActive: true,
      },
    })
    expect(wrap.classes()).toContain('bc-sentence-active')
  })

  it('clicking row emits jump-to with index', async () => {
    const wrap = mount(AnnotationPlaylistRow, {
      props: {
        annotation: { id: 1, selected_text: 'a', note: null },
        index: 5,
      },
    })
    await wrap.trigger('click')
    expect(wrap.emitted()['jump-to']?.[0]).toEqual([5])
  })
})
