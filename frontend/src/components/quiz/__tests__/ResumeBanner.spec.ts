import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ResumeBanner from '@/components/quiz/ResumeBanner.vue'
import { COPY } from '@/components/quiz/copy'

describe('ResumeBanner', () => {
  it('renders verbatim "You have a session in progress —"', () => {
    const wrapper = mount(ResumeBanner, {
      props: { session: { id: 11 } },
    })
    expect(wrapper.text()).toContain(COPY.resumeBanner)
    expect(wrapper.text()).toContain(COPY.resumeButton)
    expect(wrapper.text()).toContain(COPY.stopAndStartButton)
  })

  it('emits resume event on Resume click', async () => {
    const wrapper = mount(ResumeBanner, { props: { session: { id: 11 } } })
    await wrapper.find('[data-test="resume-btn"]').trigger('click')
    expect(wrapper.emitted('resume')).toHaveLength(1)
  })

  it('emits stop event on Stop & start a new one click', async () => {
    const wrapper = mount(ResumeBanner, { props: { session: { id: 11 } } })
    await wrapper.find('[data-test="stop-btn"]').trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
  })
})
