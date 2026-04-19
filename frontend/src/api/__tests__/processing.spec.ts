import { describe, expect, it } from 'vitest'
import type {
  ProcessingOptions,
  ProcessingStartedPayload,
  SSEHandlers,
  SectionCompletedPayload,
  SectionFailedPayload,
  SectionSkippedPayload,
} from '../processing'

describe('ProcessingOptions', () => {
  it('accepts scope and section_id', () => {
    const opts: ProcessingOptions = {
      preset_name: 'practitioner_bullets',
      scope: 'section',
      section_id: 42,
    }
    expect(opts.scope).toBe('section')
    expect(opts.section_id).toBe(42)
  })
})

describe('SSEHandlers', () => {
  it('has the full set of typed handler slots', () => {
    const h: SSEHandlers = {
      onProcessingStarted: (d: ProcessingStartedPayload) => {
        void d.book_id
      },
      onSectionCompleted: (d: SectionCompletedPayload) => {
        void d.section_id
      },
      onSectionFailed: (d: SectionFailedPayload) => {
        void d.section_id
        void d.error
      },
      onSectionSkipped: (d: SectionSkippedPayload) => {
        void d.section_id
        void d.reason
      },
      onSectionRetrying: (d) => {
        void d.section_id
      },
    }
    expect(h.onProcessingStarted).toBeDefined()
    expect(h.onSectionFailed).toBeDefined()
  })
})
