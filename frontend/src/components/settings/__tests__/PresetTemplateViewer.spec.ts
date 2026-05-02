import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PresetTemplateViewer from '../PresetTemplateViewer.vue'

const mockResp = {
  name: 'practitioner_bullets',
  is_system: true,
  base_template: { path: 'base/summarize_section.txt', source: '## Base prompt template body' },
  fragments: [
    { dimension: 'style', value: 'bullet_points', path: 'fragments/style/bullet_points.txt', source: 'Use bullets.' },
    { dimension: 'audience', value: 'practitioner', path: 'fragments/audience/practitioner.txt', source: 'Practitioners.' },
    { dimension: 'compression', value: 'standard', path: 'fragments/compression/standard.txt', source: '20%.' },
    { dimension: 'content_focus', value: 'frameworks_examples', path: 'fragments/content_focus/frameworks_examples.txt', source: 'Frameworks.' },
  ],
}

describe('PresetTemplateViewer', () => {
  it('renders base template + fragments after fetch resolves', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResp),
    })
    vi.stubGlobal('fetch', fetchMock)

    const w = mount(PresetTemplateViewer, { props: { name: 'practitioner_bullets' } })
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/summarize/presets/practitioner_bullets/template'),
    )
    const pres = w.findAll('pre')
    expect(pres.length).toBe(5)
    expect(pres[0].text()).toContain('Base prompt template body')
    expect(w.text()).toContain('style: bullet_points')
    expect(w.text()).toContain('audience: practitioner')
  })

  it('renders an error state when fetch returns 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    const w = mount(PresetTemplateViewer, { props: { name: 'missing' } })
    await flushPromises()
    expect(w.text()).toMatch(/not found/i)
  })
})
