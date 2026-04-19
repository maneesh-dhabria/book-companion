import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  FRONT_MATTER_TYPES,
  SUMMARIZABLE_TYPES,
  useReaderStore,
} from '../reader'

import type { Section } from '@/types'

const mkSection = (
  id: number,
  order: number,
  type = 'chapter',
  has_summary = false,
): Section =>
  ({
    id,
    order_index: order,
    title: `S${id}`,
    section_type: type,
    has_summary,
    book_id: 1,
    content_token_count: null,
    content_md: null,
    default_summary: null,
    summary_count: 0,
    annotation_count: 0,
  }) as Section

describe('reader constants', () => {
  it('exports FRONT_MATTER_TYPES matching backend', () => {
    expect(FRONT_MATTER_TYPES).toEqual(
      new Set([
        'copyright',
        'acknowledgments',
        'dedication',
        'title_page',
        'table_of_contents',
        'colophon',
        'cover',
        'part_header',
      ]),
    )
  })

  it('exports SUMMARIZABLE_TYPES matching backend', () => {
    expect(SUMMARIZABLE_TYPES).toEqual(
      new Set(['chapter', 'introduction', 'preface', 'foreword', 'epilogue', 'conclusion']),
    )
  })

  it('sets are disjoint', () => {
    for (const t of FRONT_MATTER_TYPES) {
      expect(SUMMARIZABLE_TYPES.has(t)).toBe(false)
    }
  })
})

describe('updateSection', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('splices updated section into sections array', () => {
    const s = useReaderStore()
    s.sections = [mkSection(1, 0), mkSection(2, 1)]
    s.updateSection({ ...mkSection(2, 1), has_summary: true } as never)
    expect(s.sections[1].has_summary).toBe(true)
  })

  it('updates currentSection if ID matches', () => {
    const s = useReaderStore()
    const target = mkSection(2, 1)
    s.sections = [mkSection(1, 0), target]
    s.currentSection = target
    s.updateSection({ ...target, has_summary: true } as never)
    expect(s.currentSection?.has_summary).toBe(true)
  })

  it('no-ops with console.warn when section id not found', () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const s = useReaderStore()
    s.sections = [mkSection(1, 0)]
    s.updateSection(mkSection(99, 99))
    expect(spy).toHaveBeenCalled()
    expect(s.sections.length).toBe(1)
  })
})

describe('setBook', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('setBook replaces the book ref', () => {
    const s = useReaderStore()
    s.setBook({ id: 1, title: 'a' } as never)
    expect(s.book?.title).toBe('a')
    s.setBook({ id: 1, title: 'b' } as never)
    expect(s.book?.title).toBe('b')
  })
})
