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
      config_dir: null,
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
    // Mock /api/v1/llm/status (called on mount), /api/v1/config/models, and
    // any other GET. Distinguish by URL.
    vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.includes('/llm/status') || url.includes('/llm/recheck')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            configured_provider: 'auto',
            provider: 'claude',
            preflight: {
              ok: true,
              provider: 'claude',
              binary: 'claude',
              binary_resolved: true,
              version: '2.1.123',
              version_ok: true,
              reason: null,
            },
          }),
        } as Response
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({
          providers: { claude: [{ id: 'sonnet', label: 'Sonnet' }] },
        }),
      } as Response
    })
  })

  it('renders a Config Directory input, not cli_command', () => {
    seedSettings()
    const w = mount(LlmSettings)
    expect(w.find('[data-testid="config-dir-input"]').exists()).toBe(true)
    expect(w.text()).not.toMatch(/CLI Command/i)
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
