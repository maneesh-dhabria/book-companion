import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EngineChip from '@/components/audio/EngineChip.vue'
import { useEngineCopy } from '@/composables/audio/useEngineCopy'

describe('EngineChip', () => {
  it('shows kokoro chip with voice name', () => {
    const wrap = mount(EngineChip, { props: { engine: 'kokoro', voice: 'af_sarah' } })
    expect(wrap.text()).toContain('Kokoro · af_sarah')
    expect(wrap.classes()).toContain('bc-engine-chip--kokoro')
  })

  it('shows web-speech chip', () => {
    const wrap = mount(EngineChip, { props: { engine: 'web-speech', voice: 'Samantha' } })
    expect(wrap.text()).toContain('Web Speech · Samantha')
    expect(wrap.classes()).toContain('bc-engine-chip--web-speech')
  })

  it('renders tooltip when active != default', () => {
    const wrap = mount(EngineChip, {
      props: {
        engine: 'web-speech',
        defaultEngine: 'kokoro',
        reason: 'no_pregen',
      },
    })
    expect(wrap.find('[role="tooltip"]').text()).toContain('no pre-generated')
  })
})

describe('useEngineCopy', () => {
  it('returns reason copy for each kind', () => {
    expect(useEngineCopy('no_pregen', 'kokoro')).toContain('no pre-generated')
    expect(useEngineCopy('model_not_downloaded', 'kokoro')).toContain('not downloaded')
    expect(useEngineCopy('model_loading', 'kokoro')).toContain('loading')
    expect(useEngineCopy('engine_unavailable', 'kokoro')).toContain('unavailable')
  })
})
