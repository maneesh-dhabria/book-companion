import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PresetCreateEditForm from '../PresetCreateEditForm.vue'

const facetOptions = {
  style: ['bullet_points', 'narrative'],
  audience: ['practitioner', 'academic'],
  compression: ['brief', 'standard', 'detailed'],
  content_focus: ['frameworks_examples', 'key_concepts'],
}

describe('PresetCreateEditForm', () => {
  it('disables Save when name is empty', () => {
    const w = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } })
    expect(w.find('button.save').attributes('disabled')).toBeDefined()
  })

  it('disables Save when name has invalid chars and shows error text', async () => {
    const w = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } })
    await w.find('input[name="name"]').setValue('Invalid Name!')
    expect(w.text()).toMatch(/lowercase|underscore/i)
    expect(w.find('button.save').attributes('disabled')).toBeDefined()
  })

  it('disables Save when label is empty', async () => {
    const w = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } })
    await w.find('input[name="name"]').setValue('valid_name')
    expect(w.find('button.save').attributes('disabled')).toBeDefined()
  })

  it('emits save with full payload when valid', async () => {
    const w = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } })
    await w.find('input[name="name"]').setValue('my_preset')
    await w.find('input[name="label"]').setValue('My Preset')
    const grids = w.findAll('.facet-grid')
    for (const grid of grids) {
      await grid.find('button.facet-card').trigger('click')
    }
    await w.find('button.save').trigger('click')
    const emitted = w.emitted('save')
    expect(emitted).toBeTruthy()
    const payload = emitted![0][0] as { name: string; label: string; facets: Record<string, string> }
    expect(payload.name).toBe('my_preset')
    expect(payload.label).toBe('My Preset')
    expect(payload.facets).toHaveProperty('style')
    expect(payload.facets).toHaveProperty('audience')
    expect(payload.facets).toHaveProperty('compression')
    expect(payload.facets).toHaveProperty('content_focus')
  })

  it('emits cancel when cancel clicked', async () => {
    const w = mount(PresetCreateEditForm, { props: { mode: 'create', facetOptions } })
    await w.find('button.cancel').trigger('click')
    expect(w.emitted('cancel')).toBeTruthy()
  })

  it('mode=edit prefills from initial and makes name read-only', () => {
    const initial = {
      name: 'foo',
      label: 'Foo',
      description: 'desc',
      facets: {
        style: 'narrative',
        audience: 'practitioner',
        compression: 'brief',
        content_focus: 'key_concepts',
      },
    }
    const w = mount(PresetCreateEditForm, { props: { mode: 'edit', facetOptions, initial } })
    expect((w.find('input[name="name"]').element as HTMLInputElement).value).toBe('foo')
    expect(w.find('input[name="name"]').attributes('readonly')).toBeDefined()
  })
})
