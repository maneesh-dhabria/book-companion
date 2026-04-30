import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import { useReaderSettingsStore } from '@/stores/readerSettings'
import * as api from '@/api/readingPresets'
import { useUiStore } from '@/stores/ui'

const SYSTEM_PRESETS = [
  {
    id: 1,
    name: 'Light',
    font_family: 'Georgia',
    font_size_px: 16,
    line_spacing: 1.6,
    content_width_px: 720,
    theme: 'light',
    created_at: '',
  },
  {
    id: 2,
    name: 'Sepia',
    font_family: 'Georgia',
    font_size_px: 16,
    line_spacing: 1.6,
    content_width_px: 720,
    theme: 'sepia',
    created_at: '',
  },
]

function mockListPresets(items = SYSTEM_PRESETS) {
  return vi.spyOn(api, 'listPresets').mockResolvedValue({ items } as never)
}

function mockHintNull() {
  return vi.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ name: null }),
  } as Response)
}

describe('readerSettings store', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('applyPreset(N) sets appliedPresetKey and writes localStorage', async () => {
    mockListPresets()
    mockHintNull()
    const s = useReaderSettingsStore()
    await s.loadPresets()
    s.applyPreset(2)
    expect(s.appliedPresetKey).toBe('system:2')
    expect(s.currentSettings.theme).toBe('sepia')
    expect(window.localStorage.getItem('bookcompanion.reader-applied.v1')).toBe(
      'system:2',
    )
  })

  it('applyPreset(99) (non-existent) is a silent no-op', async () => {
    mockListPresets()
    mockHintNull()
    const s = useReaderSettingsStore()
    await s.loadPresets()
    s.applyPreset(2)
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const before = JSON.stringify({ key: s.appliedPresetKey, settings: { ...s.currentSettings } })
    s.applyPreset(99)
    const after = JSON.stringify({ key: s.appliedPresetKey, settings: { ...s.currentSettings } })
    expect(after).toBe(before)
    expect(warnSpy).toHaveBeenCalled()
  })

  it('applyCustom() seeds from active system preset when slot is empty', async () => {
    mockListPresets()
    mockHintNull()
    const s = useReaderSettingsStore()
    await s.loadPresets()
    s.applyPreset(2)
    s.applyCustom()
    expect(s.appliedPresetKey).toBe('custom')
    expect(s.customTheme).toBeTruthy()
    expect(s.customTheme!.bg).toBeTruthy()
  })

  it('applyCustom() with empty slot AND key=custom recovers to Light', async () => {
    mockListPresets()
    mockHintNull()
    window.localStorage.setItem('bookcompanion.reader-applied.v1', 'custom')
    const s = useReaderSettingsStore()
    await s.loadPresets()
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    s.applyCustom()
    expect(s.appliedPresetKey).toBe('system:1')
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('falling back to Light'),
    )
  })

  it('applyCustom() corrupted-state with NO Light falls back to presets[0]', async () => {
    mockListPresets([
      {
        id: 7,
        name: 'OnlyOption',
        font_family: 'Georgia',
        font_size_px: 16,
        line_spacing: 1.6,
        content_width_px: 720,
        theme: 'sepia',
        created_at: '',
      },
    ])
    mockHintNull()
    window.localStorage.setItem('bookcompanion.reader-applied.v1', 'custom')
    const s = useReaderSettingsStore()
    await s.loadPresets()
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    s.applyCustom()
    expect(s.appliedPresetKey).toBe('system:7')
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('falling back to OnlyOption'),
    )
  })

  it('tampered localStorage value is cleared and warned', async () => {
    mockListPresets()
    mockHintNull()
    window.localStorage.setItem(
      'bookcompanion.reader-applied.v1',
      'system:not-a-number',
    )
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const s = useReaderSettingsStore()
    await s.loadPresets()
    expect(s.appliedPresetKey).toBeNull()
    expect(window.localStorage.getItem('bookcompanion.reader-applied.v1')).toBeNull()
    expect(warnSpy).toHaveBeenCalled()
  })

  it('legacy-active hint applied once on init when no localStorage value present', async () => {
    mockListPresets()
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ name: 'Sepia' }),
    } as Response)
    const s = useReaderSettingsStore()
    await s.loadPresets()
    // Auto-consume runs at the tail of loadPresets — give the microtask a tick.
    await Promise.resolve()
    await Promise.resolve()
    expect(s.appliedPresetKey).toBe('system:2')
  })

  it('localStorage write failure fires toast once per session', async () => {
    mockListPresets()
    mockHintNull()
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    vi.spyOn(window.localStorage.__proto__, 'setItem').mockImplementation(
      () => {
        throw new DOMException('quota')
      },
    )
    const s = useReaderSettingsStore()
    await s.loadPresets()
    s.applyPreset(2)
    s.applyPreset(1) // second write — toast must NOT fire again
    expect(
      toastSpy.mock.calls.filter(([msg]) =>
        String(msg).includes('reader preferences'),
      ).length,
    ).toBe(1)
  })

  it('applyPreset clears pendingCustom and editingCustom state', async () => {
    mockListPresets()
    mockHintNull()
    const s = useReaderSettingsStore()
    await s.loadPresets()
    s.applyCustom()
    s.stageCustom({ name: 'Custom', bg: '#000', fg: '#fff', accent: '#333' })
    s.editingCustom = true
    s.applyPreset(2)
    expect(s.pendingCustom).toBeNull()
    expect(s.dirty).toBe(false)
    expect(s.editingCustom).toBe(false)
  })

  it('toggleCustomEditor flips editingCustom', async () => {
    mockListPresets()
    mockHintNull()
    const s = useReaderSettingsStore()
    await s.loadPresets()
    expect(s.editingCustom).toBe(false)
    s.toggleCustomEditor()
    expect(s.editingCustom).toBe(true)
    s.toggleCustomEditor()
    expect(s.editingCustom).toBe(false)
  })

  it('opening the popover resets editingCustom to false', async () => {
    mockListPresets()
    mockHintNull()
    const s = useReaderSettingsStore()
    await s.loadPresets()
    s.editingCustom = true
    s.popoverOpen = false
    await Promise.resolve()
    s.popoverOpen = true
    await Promise.resolve()
    expect(s.editingCustom).toBe(false)
  })

  it('applyCustom() does not mutate editingCustom (regression for D11/FR-24)', async () => {
    mockListPresets()
    mockHintNull()
    const s = useReaderSettingsStore()
    await s.loadPresets()
    s.applyPreset(1)
    s.editingCustom = false
    s.applyCustom()
    expect(s.editingCustom).toBe(false)
    s.editingCustom = true
    s.applyCustom()
    expect(s.editingCustom).toBe(true)
  })

  it('openCustomPicker is no longer exported', async () => {
    const s = useReaderSettingsStore()
    // @ts-expect-error - removed API
    expect(s.openCustomPicker).toBeUndefined()
  })
})
