import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import UploadFileCard from '../UploadFileCard.vue'

const makeFile = () => new File([new Uint8Array(100)], 'book.epub', { type: 'application/epub+zip' })

describe('UploadFileCard', () => {
  it('renders determinate progress bar driven by uploadProgress prop', () => {
    const wrapper = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'uploading', uploadProgress: 42 },
    })
    const bar = wrapper.find('[data-test="upload-progress-bar"]')
    expect(bar.exists()).toBe(true)
    expect(bar.attributes('style')).toContain('42%')
    expect(wrapper.text()).toContain('Uploading')
  })

  it('clamps out-of-range progress values', () => {
    const high = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'uploading', uploadProgress: 200 },
    })
    expect(high.find('[data-test="upload-progress-bar"]').attributes('style')).toContain('100%')
    const low = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'uploading', uploadProgress: -50 },
    })
    expect(low.find('[data-test="upload-progress-bar"]').attributes('style')).toContain('0%')
  })

  it('shows indeterminate spinner with parse text in parse phase', () => {
    const wrapper = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'parsing' },
    })
    expect(wrapper.find('[data-test="parse-spinner"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Parsing')
  })

  it('Cancel button enabled in upload phase, disabled in parse phase', () => {
    const uploading = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'uploading' },
    })
    const cancelUpload = uploading.find('[data-test="cancel-btn"]')
    expect(cancelUpload.attributes('disabled')).toBeUndefined()

    const parsing = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'parsing' },
    })
    expect(parsing.find('[data-test="cancel-btn"]').attributes('disabled')).toBeDefined()
  })

  it('emits cancel on button click during upload', async () => {
    const wrapper = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'uploading' },
    })
    await wrapper.find('[data-test="cancel-btn"]').trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
  })

  it('renders error state with Retry button', () => {
    const wrapper = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'error', error: 'Network glitch' },
    })
    expect(wrapper.text()).toContain('Network glitch')
    expect(wrapper.find('[data-test="retry-btn"]').exists()).toBe(true)
  })

  it('emits retry from error state', async () => {
    const wrapper = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'error', error: 'oops' },
    })
    await wrapper.find('[data-test="retry-btn"]').trigger('click')
    expect(wrapper.emitted('retry')).toBeTruthy()
  })

  it('shows success indicator without cancel button', () => {
    const wrapper = mount(UploadFileCard, {
      props: { file: makeFile(), phase: 'success' },
    })
    expect(wrapper.text()).toContain('Uploaded')
    expect(wrapper.find('[data-test="cancel-btn"]').exists()).toBe(false)
  })
})
