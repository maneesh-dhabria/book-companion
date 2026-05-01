import { describe, it, expect } from 'vitest'
import { annotationContentTypeFor } from '../annotationContentType'

describe('annotationContentTypeFor', () => {
  it('returns section_summary on summary tab', () => {
    expect(annotationContentTypeFor('summary')).toBe('section_summary')
  })
  it('returns section_content on original tab', () => {
    expect(annotationContentTypeFor('original')).toBe('section_content')
  })
})
