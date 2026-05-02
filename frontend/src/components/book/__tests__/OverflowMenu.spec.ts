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

  it('renders the canonical menu items (T12)', async () => {
    const w = mount(OverflowMenu, {
      props: { editRoute, hasBookSummary: false },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    const items = w.findAll('[role="menuitem"]').map((i) => i.text())
    expect(items).toContain('Generate book summary')
    expect(items).toContain('Customize reader…')
    expect(items).toContain('Edit structure')
    expect(items).toContain('Re-import')
    expect(items).toContain('Export Markdown')
    expect(items).toContain('Delete book')
    expect(items).not.toContain('Customize text')
    expect(items).not.toContain('Customize text…')
    w.unmount()
  })

  it('shows Read book summary when hasBookSummary=true', async () => {
    const w = mount(OverflowMenu, {
      props: { editRoute, hasBookSummary: true },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    const items = w.findAll('[role="menuitem"]').map((i) => i.text())
    expect(items).toContain('Read book summary')
    expect(items).not.toContain('Generate book summary')
    w.unmount()
  })

  it('Edit structure is a router-link to editRoute', async () => {
    const router = makeRouter()
    const w = mount(OverflowMenu, {
      props: { editRoute },
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    const editItem = w.findAll('[role="menuitem"]').find((i) => i.text() === 'Edit structure')
    expect(editItem!.attributes('href')).toContain('/books/1/edit-structure')
    w.unmount()
  })

  it('Customize reader emits open-reader-settings and closes menu', async () => {
    const w = mount(OverflowMenu, {
      props: { editRoute },
      global: { plugins: [makeRouter()] },
      attachTo: document.body,
    })
    await w.find('button').trigger('click')
    const customizeItem = w.findAll('[role="menuitem"]').find((i) => i.text() === 'Customize reader…')
    await customizeItem!.trigger('click')
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
