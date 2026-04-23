import { describe, expect, it } from 'vitest'
import { labelize } from '../labelize'

describe('labelize', () => {
  it('converts snake_case to Title Case with stop words lowercased', () => {
    expect(labelize('table_of_contents')).toBe('Table of Contents')
  })

  it('handles preset identifiers', () => {
    expect(labelize('practitioner_bullets')).toBe('Practitioner Bullets')
    expect(labelize('executive_brief')).toBe('Executive Brief')
  })

  it('preserves well-known acronyms', () => {
    expect(labelize('EPUB')).toBe('EPUB')
    expect(labelize('epub')).toBe('EPUB')
    expect(labelize('frankenstein_epub')).toBe('Frankenstein EPUB')
  })

  it('handles kebab-case and mixed separators', () => {
    expect(labelize('chapter-one')).toBe('Chapter One')
    expect(labelize('some  multi_word name')).toBe('Some Multi Word Name')
  })

  it('returns empty for nullish input', () => {
    expect(labelize(null)).toBe('')
    expect(labelize(undefined)).toBe('')
    expect(labelize('')).toBe('')
  })
})
