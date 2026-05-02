import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import Playbar from '@/components/audio/Playbar.vue'
import { useTtsPlayerStore } from '@/stores/ttsPlayer'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('Playbar mid-listen regen banner', () => {
  it('shows banner when pendingRegenBanner true and status=paused', () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.status = 'paused'
    store.pendingRegenBanner = true
    const wrap = mount(Playbar)
    expect(wrap.find('[data-testid="mid-listen-regen"]').exists()).toBe(true)
    expect(wrap.text()).toContain('Summary updated since this audio')
  })

  it('does not show banner during playback', () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.status = 'playing'
    store.pendingRegenBanner = true
    const wrap = mount(Playbar)
    expect(wrap.find('[data-testid="mid-listen-regen"]').exists()).toBe(false)
  })

  it('does not show banner when pendingRegenBanner false', () => {
    const store = useTtsPlayerStore()
    store.open({ contentType: 'section_summary', contentId: 1 })
    store.status = 'paused'
    store.pendingRegenBanner = false
    const wrap = mount(Playbar)
    expect(wrap.find('[data-testid="mid-listen-regen"]').exists()).toBe(false)
  })
})
