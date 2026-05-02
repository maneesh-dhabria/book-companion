import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ProcessingBar from '@/components/app/ProcessingBar.vue'

describe('ProcessingBar audio step', () => {
  it('renders audio job with completed/total + already_stale', () => {
    const wrap = mount(ProcessingBar, {
      props: {
        jobs: [],
        audioJob: {
          jobId: 187,
          step: 'audio',
          completed: 12,
          total: 47,
          current_kind: 'section_summary',
          current_ref: '42',
          already_stale: 1,
        },
      },
    })
    expect(wrap.text()).toContain('Generating audio')
    expect(wrap.text()).toContain('12 / 47')
    expect(wrap.text()).toContain('1 already stale')
  })

  it('does not render audio block when audioJob is null', () => {
    const wrap = mount(ProcessingBar, { props: { jobs: [] } })
    expect(wrap.text()).not.toContain('Generating audio')
  })
})
