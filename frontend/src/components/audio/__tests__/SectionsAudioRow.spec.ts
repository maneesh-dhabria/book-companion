import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SectionsAudioRow from '@/components/audio/SectionsAudioRow.vue'

const STATUSES: Array<'none' | 'ready' | 'stale' | 'generating'> = [
  'none',
  'ready',
  'stale',
  'generating',
]

describe('SectionsAudioRow', () => {
  it.each(STATUSES)('renders status pill: %s', (status) => {
    const wrap = mount(SectionsAudioRow, {
      props: { bookId: 1, sectionId: 42, sectionTitle: 'Ch1', audioStatus: status },
    })
    expect(wrap.find(`[data-testid="audio-status-${status}"]`).exists()).toBe(true)
  })

  it('Play button visible only when status=ready or stale', () => {
    expect(
      mount(SectionsAudioRow, {
        props: { bookId: 1, sectionId: 1, sectionTitle: 'a', audioStatus: 'ready' },
      })
        .find('button[data-testid="play"]')
        .exists(),
    ).toBe(true)
    expect(
      mount(SectionsAudioRow, {
        props: { bookId: 1, sectionId: 1, sectionTitle: 'a', audioStatus: 'stale' },
      })
        .find('button[data-testid="play"]')
        .exists(),
    ).toBe(true)
    expect(
      mount(SectionsAudioRow, {
        props: { bookId: 1, sectionId: 1, sectionTitle: 'a', audioStatus: 'none' },
      })
        .find('button[data-testid="play"]')
        .exists(),
    ).toBe(false)
  })

  it('Regenerate visible when status=stale', () => {
    const wrap = mount(SectionsAudioRow, {
      props: { bookId: 1, sectionId: 1, sectionTitle: 'a', audioStatus: 'stale' },
    })
    expect(wrap.find('button[data-testid="regenerate"]').exists()).toBe(true)
  })

  it('Delete-row visible when status=ready', () => {
    const wrap = mount(SectionsAudioRow, {
      props: { bookId: 1, sectionId: 1, sectionTitle: 'a', audioStatus: 'ready' },
    })
    expect(wrap.find('button[data-testid="delete-row"]').exists()).toBe(true)
  })

  it('shows checkbox when selectable', () => {
    const wrap = mount(SectionsAudioRow, {
      props: {
        bookId: 1,
        sectionId: 1,
        sectionTitle: 'a',
        audioStatus: 'ready',
        selectable: true,
      },
    })
    expect(wrap.find('input[type="checkbox"][data-testid="bulk-select"]').exists()).toBe(true)
  })

  it('clicking Play emits play with sectionId', async () => {
    const wrap = mount(SectionsAudioRow, {
      props: { bookId: 1, sectionId: 42, sectionTitle: 'a', audioStatus: 'ready' },
    })
    await wrap.find('button[data-testid="play"]').trigger('click')
    expect(wrap.emitted().play?.[0]).toEqual([42])
  })
})
