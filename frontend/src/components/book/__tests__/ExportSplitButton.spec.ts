import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ExportSplitButton from '../ExportSplitButton.vue'

describe('ExportSplitButton', () => {
  it('default body click emits download', async () => {
    const w = mount(ExportSplitButton, { attachTo: document.body })
    await w.find('[data-role="body"]').trigger('click')
    expect(w.emitted('download')).toHaveLength(1)
    expect(w.emitted('copy')).toBeFalsy()
    w.unmount()
  })

  it('chevron opens menu and toggles aria-expanded', async () => {
    const w = mount(ExportSplitButton, { attachTo: document.body })
    const chev = w.find('[data-role="chevron"]')
    expect(chev.attributes('aria-expanded')).toBe('false')
    await chev.trigger('click')
    expect(chev.attributes('aria-expanded')).toBe('true')
    expect(w.find('[role="menu"]').exists()).toBe(true)
    const items = w.findAll('[role="menuitem"]').map((i) => i.text())
    expect(items).toEqual(expect.arrayContaining(['Download Markdown', 'Copy to Clipboard']))
    w.unmount()
  })

  it('Copy menu item emits copy and closes menu', async () => {
    const w = mount(ExportSplitButton, { attachTo: document.body })
    await w.find('[data-role="chevron"]').trigger('click')
    const copyItem = w
      .findAll('[role="menuitem"]')
      .find((i) => i.text() === 'Copy to Clipboard')!
    await copyItem.trigger('click')
    expect(w.emitted('copy')).toHaveLength(1)
    await w.vm.$nextTick()
    expect(w.find('[role="menu"]').exists()).toBe(false)
    w.unmount()
  })

  it('disabled state suppresses clicks and shows tooltip', async () => {
    const w = mount(ExportSplitButton, {
      props: {
        disabled: true,
        disabledReason: 'No summaries to export yet — summarize sections first.',
      },
      attachTo: document.body,
    })
    await w.find('[data-role="body"]').trigger('click')
    expect(w.emitted('download')).toBeFalsy()
    const body = w.find('[data-role="body"]')
    expect(body.attributes('aria-disabled')).toBe('true')
    expect(body.attributes('title')).toContain('No summaries to export yet')
    w.unmount()
  })

  it('Esc closes menu and refocuses chevron', async () => {
    const w = mount(ExportSplitButton, { attachTo: document.body })
    const chev = w.find('[data-role="chevron"]')
    await chev.trigger('click')
    await w.find('[role="menu"]').trigger('keydown', { key: 'Escape' })
    await w.vm.$nextTick()
    expect(w.find('[role="menu"]').exists()).toBe(false)
    await w.vm.$nextTick()
    expect(document.activeElement).toBe(chev.element)
    w.unmount()
  })

  it('ArrowDown moves focus to next menu item', async () => {
    const w = mount(ExportSplitButton, { attachTo: document.body })
    await w.find('[data-role="chevron"]').trigger('click')
    const menu = w.find('[role="menu"]')
    const items = w.findAll('[role="menuitem"]')
    ;(items[0].element as HTMLElement).focus()
    await menu.trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(items[1].element)
    w.unmount()
  })

  it('loading prop renders spinner', () => {
    const w = mount(ExportSplitButton, { props: { loading: true }, attachTo: document.body })
    expect(w.find('[data-role="body"] .spinner').exists()).toBe(true)
    w.unmount()
  })
})
