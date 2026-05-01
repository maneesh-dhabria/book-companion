import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FontListbox from '../FontListbox.vue'

const FONTS = ['Georgia', 'Inter', 'Merriweather', 'Fira Code', 'Lora', 'Source Serif Pro']

describe('FontListbox', () => {
  it('each option has font-family style applied to its label', async () => {
    const wrapper = mount(FontListbox, {
      props: { modelValue: 'Georgia', options: FONTS },
      attachTo: document.body,
    })
    await wrapper.find('button[aria-haspopup="listbox"]').trigger('click')
    const opts = wrapper.findAll('[role="option"]')
    expect(opts).toHaveLength(FONTS.length)
    FONTS.forEach((f, i) => {
      const style = (opts[i].element as HTMLElement).style.fontFamily
      expect(style.toLowerCase()).toContain(f.toLowerCase())
    })
    wrapper.unmount()
  })

  it('arrow keys move active descendant', async () => {
    const wrapper = mount(FontListbox, {
      props: { modelValue: 'Georgia', options: FONTS },
      attachTo: document.body,
    })
    const trigger = wrapper.find('button[aria-haspopup="listbox"]')
    await trigger.trigger('click')
    const listbox = wrapper.find('[role="listbox"]')
    await listbox.trigger('keydown', { key: 'ArrowDown' })
    expect(listbox.attributes('aria-activedescendant')).toMatch(/inter/i)
    wrapper.unmount()
  })

  it('Enter selects + emits update:modelValue', async () => {
    const wrapper = mount(FontListbox, {
      props: { modelValue: 'Georgia', options: FONTS },
      attachTo: document.body,
    })
    await wrapper.find('button[aria-haspopup="listbox"]').trigger('click')
    const listbox = wrapper.find('[role="listbox"]')
    await listbox.trigger('keydown', { key: 'ArrowDown' })
    await listbox.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['Inter'])
    wrapper.unmount()
  })

  it('Esc closes and returns focus to trigger', async () => {
    const wrapper = mount(FontListbox, {
      props: { modelValue: 'Georgia', options: FONTS },
      attachTo: document.body,
    })
    const trigger = wrapper.find('button[aria-haspopup="listbox"]')
    await trigger.trigger('click')
    const listbox = wrapper.find('[role="listbox"]')
    await listbox.trigger('keydown', { key: 'Escape' })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    await wrapper.vm.$nextTick()
    expect(document.activeElement).toBe(trigger.element)
    wrapper.unmount()
  })

  it('click outside closes', async () => {
    const wrapper = mount(FontListbox, {
      props: { modelValue: 'Georgia', options: FONTS },
      attachTo: document.body,
    })
    await wrapper.find('button[aria-haspopup="listbox"]').trigger('click')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(true)
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('clicking an option emits update:modelValue and closes', async () => {
    const wrapper = mount(FontListbox, {
      props: { modelValue: 'Georgia', options: FONTS },
      attachTo: document.body,
    })
    await wrapper.find('button[aria-haspopup="listbox"]').trigger('click')
    const opts = wrapper.findAll('[role="option"]')
    await opts[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['Merriweather'])
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
