import { describe, it, expect } from 'vitest'
import { firstChapter } from '@/stores/reader'
import type { Section } from '@/types'

function s(id: number, type: string, order = id): Section {
  return {
    id,
    book_id: 1,
    title: `s${id}`,
    section_type: type,
    order_index: order,
    content_md: '',
    has_summary: false,
    char_count: 0,
    word_count: 0,
    image_count: 0,
  } as unknown as Section
}

describe('firstChapter', () => {
  it('returns null for empty array', () => {
    expect(firstChapter([], 'PARSED')).toBeNull()
  })

  it('returns null for null/undefined sections', () => {
    expect(firstChapter(null, 'PARSED')).toBeNull()
    expect(firstChapter(undefined, 'PARSED')).toBeNull()
  })

  it('returns null when only front-matter sections and book is still PARSING', () => {
    const sections = [s(1, 'copyright'), s(2, 'cover')]
    expect(firstChapter(sections, 'PARSING')).toBeNull()
  })

  it('returns sections[0] when only front-matter and book is PARSED (last-resort fallback)', () => {
    const sections = [s(1, 'copyright'), s(2, 'cover')]
    expect(firstChapter(sections, 'PARSED')).toEqual(sections[0])
  })

  it('returns first chapter when mixed front-matter + chapters', () => {
    const sections = [s(1, 'copyright'), s(2, 'chapter'), s(3, 'chapter')]
    expect(firstChapter(sections, 'PARSED')?.id).toBe(2)
  })

  it('treats introduction as a qualifying chapter', () => {
    const sections = [s(1, 'copyright'), s(2, 'introduction'), s(3, 'chapter')]
    expect(firstChapter(sections, 'PARSED')?.id).toBe(2)
  })

  it('does NOT treat glossary as a chapter', () => {
    const sections = [s(1, 'copyright'), s(2, 'glossary')]
    // No SUMMARIZABLE match: only front-matter qualifies if PARSED → fallback to sections[0].
    // glossary is not in FRONT_MATTER_TYPES either, so PARSED-fallback returns sections[0].
    expect(firstChapter(sections, 'PARSED')?.id).toBe(1)
  })

  it('prefers chapter over introduction when chapter comes first', () => {
    const sections = [s(1, 'chapter'), s(2, 'introduction')]
    expect(firstChapter(sections, 'PARSED')?.id).toBe(1)
  })
})
