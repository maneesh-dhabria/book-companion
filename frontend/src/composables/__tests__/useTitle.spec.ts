import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import { useTitle } from '../useTitle'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

function mountWithTitle(source: Parameters<typeof useTitle>[0]) {
  const Comp = defineComponent({
    setup() {
      useTitle(source)
      return () => h('div')
    },
  })
  return mount(Comp)
}

describe('useTitle', () => {
  it('sets document.title with app suffix', () => {
    mountWithTitle('Library')
    expect(document.title).toBe('Library — Book Companion')
  })

  it('falls back to app name when source is null', () => {
    mountWithTitle(null)
    expect(document.title).toBe('Book Companion')
  })

  it('reacts to ref updates', async () => {
    const t = ref('One')
    mountWithTitle(t)
    expect(document.title).toBe('One — Book Companion')
    t.value = 'Two'
    await Promise.resolve()
    expect(document.title).toBe('Two — Book Companion')
  })
})
