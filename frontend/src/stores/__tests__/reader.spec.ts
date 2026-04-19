import { describe, expect, it } from 'vitest'
import { FRONT_MATTER_TYPES, SUMMARIZABLE_TYPES } from '../reader'

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
