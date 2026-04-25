import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import LlmSettings from '../LlmSettings.vue'
import { useSettingsStore } from '@/stores/settings'
import { useUiStore } from '@/stores/ui'

function seedSettings() {
  const settings = useSettingsStore()
  settings.settings = {
    llm: {
      provider: 'auto',
      cli_command: 'claude',
      model: 'sonnet',
      timeout_seconds: 300,
      max_retries: 2,
      max_budget_usd: 5,
    },
    network: {} as never,
    summarization: {} as never,
    web: {} as never,
  } as never
  return settings
}

describe('LlmSettings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        providers: { claude: [{ id: 'sonnet', label: 'Sonnet' }] },
      }),
    } as Response)
  })

  it('does not render a Config Directory field', () => {
    seedSettings()
    const w = mount(LlmSettings)
    expect(w.text()).not.toMatch(/Config Directory/i)
  })

  it('fires success toast on successful save', async () => {
    const settings = seedSettings()
    vi.spyOn(settings, 'saveSettings').mockResolvedValue(undefined)
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    const w = mount(LlmSettings)
    await w.find('button[data-testid="save-llm"]').trigger('click')
    await flushPromises()
    expect(toastSpy).toHaveBeenCalledWith('Settings saved', 'success')
  })

  it('fires error toast on failed save', async () => {
    const settings = seedSettings()
    vi.spyOn(settings, 'saveSettings').mockRejectedValue(new Error('boom'))
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    const w = mount(LlmSettings)
    await w.find('button[data-testid="save-llm"]').trigger('click')
    await flushPromises()
    const errCall = toastSpy.mock.calls.find((c) => c[1] === 'error')
    expect(errCall).toBeDefined()
    expect(String(errCall![0])).toContain('boom')
  })

  it('disables Save while in-flight', async () => {
    const settings = seedSettings()
    let resolve: () => void = () => {}
    vi.spyOn(settings, 'saveSettings').mockImplementation(
      () => new Promise<void>((r) => { resolve = r }),
    )
    const w = mount(LlmSettings)
    const btn = w.find('button[data-testid="save-llm"]')
    await btn.trigger('click')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
    resolve!()
    await flushPromises()
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('FastAPI 400 with array detail surfaces a joined toast message', async () => {
    const settings = seedSettings()
    const detail = [
      { loc: ['llm', 'timeout_seconds'], msg: 'Input should be a valid integer', type: 'int_parsing' },
      { loc: ['llm', 'foo'], msg: 'Extra inputs are not permitted', type: 'extra_forbidden' },
    ]
    const { ApiError } = await import('@/api/client')
    vi.spyOn(settings, 'saveSettings').mockImplementation(async () => {
      throw new ApiError(400, detail as unknown)
    })
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    const w = mount(LlmSettings)
    await w.find('button[data-testid="save-llm"]').trigger('click')
    await flushPromises()
    const lastCall = toastSpy.mock.calls[toastSpy.mock.calls.length - 1]
    const [msg, type] = lastCall
    expect(type).toBe('error')
    expect(String(msg)).toContain('Input should be a valid integer')
    expect(String(msg)).toContain('Extra inputs are not permitted')
  })
})
