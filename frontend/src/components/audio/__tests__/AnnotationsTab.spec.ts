import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AnnotationsTab from '@/components/audio/AnnotationsTab.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('AnnotationsTab', () => {
  it('renders Play-as-audio CTA when book has highlights', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            annotations: [
              { id: 1, selected_text: 'a', note: null },
              { id: 2, selected_text: 'b', note: 'n' },
              { id: 3, selected_text: 'c', note: null },
            ],
          }),
          { status: 200 },
        ),
      ),
    )
    const wrap = mount(AnnotationsTab, { props: { bookId: 1 } })
    await flushPromises()
    expect(wrap.find('button[data-testid="play-all-annotations"]').exists()).toBe(true)
    expect(wrap.text()).toMatch(/3 highlight/)
  })

  it('hides Play-as-audio when zero highlights', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ annotations: [] }), { status: 200 }),
      ),
    )
    const wrap = mount(AnnotationsTab, { props: { bookId: 1 } })
    await flushPromises()
    expect(wrap.find('button[data-testid="play-all-annotations"]').exists()).toBe(false)
    expect(wrap.text()).toContain('No highlights yet')
  })

  it('clicking Play-as-audio opens annotations playlist', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ annotations: [{ id: 1, selected_text: 'a', note: null }] }),
          { status: 200 },
        ),
      ),
    )
    const store = useTtsPlayerStore()
    const spy = vi.spyOn(store, 'open')
    const wrap = mount(AnnotationsTab, { props: { bookId: 1 } })
    await flushPromises()
    await wrap.find('button[data-testid="play-all-annotations"]').trigger('click')
    expect(spy).toHaveBeenCalledWith({
      contentType: 'annotations_playlist',
      contentId: 1,
    })
  })
})
