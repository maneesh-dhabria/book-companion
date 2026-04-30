import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import OverflowMenu from '../OverflowMenu.vue'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/books/:id/edit-structure',
        name: 'book-edit-structure',
        component: { template: '<div/>' },
      },
    ],
  })
}

const editRoute = { name: 'book-edit-structure', params: { id: '1' } }

describe('OverflowMenu', () => {
  it('trigger has aria-haspopup="menu"', () => {
    const w = mount(OverflowMenu, {
      props: { editRoute },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    expect(w.find('button').attributes('aria-haspopup')).toBe('menu')
    w.unmount()
  })

  it('click opens menu with both items', async () => {
    const w = mount(OverflowMenu, {
      props: { editRoute },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    const items = w.findAll('[role="menuitem"]').map((i) => i.text())
    expect(items).toEqual(['Edit Structure', 'Customize Reader'])
    w.unmount()
  })

  it('Edit Structure is a router-link to editRoute', async () => {
    const router = makeRouter()
    const w = mount(OverflowMenu, {
      props: { editRoute },
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    const editItem = w.findAll('[role="menuitem"]')[0]
    expect(editItem.attributes('href')).toContain('/books/1/edit-structure')
    w.unmount()
  })

  it('Customize Reader emits open-reader-settings and closes menu', async () => {
    const w = mount(OverflowMenu, {
      props: { editRoute },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    const customizeItem = w.findAll('[role="menuitem"]')[1]
    await customizeItem.trigger('click')
    expect(w.emitted('open-reader-settings')).toHaveLength(1)
    await w.vm.$nextTick()
    expect(w.find('[role="menu"]').exists()).toBe(false)
    w.unmount()
  })

  it('Esc closes', async () => {
    const w = mount(OverflowMenu, {
      props: { editRoute },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    await w.find('[role="menu"]').trigger('keydown', { key: 'Escape' })
    await w.vm.$nextTick()
    expect(w.find('[role="menu"]').exists()).toBe(false)
    w.unmount()
  })
})
