import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { listPresets } from '@/api/readingPresets'
import { themeMap } from '@/components/settings/themeColors'
import { useUiStore } from '@/stores/ui'
import type { ReadingPreset } from '@/types'

export interface ReaderSettingsState {
  font_family: string
  font_size_px: number
  line_spacing: number
  content_width_px: number
  theme: string
}

const DEFAULT_SETTINGS: ReaderSettingsState = {
  font_family: 'Georgia',
  font_size_px: 16,
  line_spacing: 1.6,
  content_width_px: 720,
  theme: 'light',
}

export type AnnotationScope = 'current' | 'all'

// v1.5.1 — appliedPresetKey is the single source of truth for which theme
// the reader is showing. Format: `system:<id>` or `custom`. Validated on
// every read so a tampered/garbage value falls back to null safely.
const APPLIED_LS_KEY = 'bookcompanion.reader-applied.v1'
const APPLIED_REGEX = /^(system:\d+|custom)$/
const CHROME_LS_KEY = 'bookcompanion.reader-chrome.v1'
const CUSTOM_LS_KEY = 'bookcompanion.reader-custom.v1'

// FR-F4.7b / P8: module-level flag so the quota-exceeded toast fires at
// most once per page load. Reset on hard reload, which matches the user's
// mental model of "session". Exposed as a setter for test isolation.
let _quotaToastFired = false

/** Test-only: reset the once-per-session quota-toast guard. */
export function __resetQuotaToastFlag() {
  _quotaToastFired = false
}

interface ReaderChromeState {
  highlightsVisible: boolean
  annotationsScope: AnnotationScope
}

function loadChrome(): ReaderChromeState {
  try {
    const raw = window.localStorage.getItem(CHROME_LS_KEY)
    if (!raw) return { highlightsVisible: true, annotationsScope: 'current' }
    const parsed = JSON.parse(raw)
    return {
      highlightsVisible: parsed?.highlightsVisible !== false,
      annotationsScope: parsed?.annotationsScope === 'all' ? 'all' : 'current',
    }
  } catch {
    return { highlightsVisible: true, annotationsScope: 'current' }
  }
}

function persistChrome(state: ReaderChromeState) {
  try {
    window.localStorage.setItem(CHROME_LS_KEY, JSON.stringify(state))
  } catch {
    // quota / disabled storage — fall through silently
  }
}

interface CustomThemeSlot {
  name: string
  bg: string
  fg: string
  accent: string
}

function loadCustom(): CustomThemeSlot | null {
  try {
    const raw = window.localStorage.getItem(CUSTOM_LS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.bg || !parsed?.fg) return null
    return {
      name: String(parsed.name || 'Custom'),
      bg: String(parsed.bg),
      fg: String(parsed.fg),
      accent: String(parsed.accent || parsed.fg),
    }
  } catch {
    return null
  }
}

function persistCustom(slot: CustomThemeSlot | null) {
  try {
    if (slot === null) window.localStorage.removeItem(CUSTOM_LS_KEY)
    else window.localStorage.setItem(CUSTOM_LS_KEY, JSON.stringify(slot))
  } catch {
    // ignore — caller already showed quota toast
  }
}

function loadAppliedKey(): string | null {
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(APPLIED_LS_KEY)
  } catch {
    return null
  }
  if (!raw) return null
  if (APPLIED_REGEX.test(raw)) return raw
  console.warn(`Invalid ${APPLIED_LS_KEY} value: ${raw}; clearing.`)
  try {
    window.localStorage.removeItem(APPLIED_LS_KEY)
  } catch {
    // ignore
  }
  return null
}

function persistAppliedKey(key: string | null) {
  const ui = useUiStore()
  try {
    if (key === null) {
      window.localStorage.removeItem(APPLIED_LS_KEY)
    } else {
      window.localStorage.setItem(APPLIED_LS_KEY, key)
    }
  } catch (e) {
    if (e instanceof DOMException) {
      if (!_quotaToastFired) {
        _quotaToastFired = true
        ui.showToast(
          "Couldn't save your reader preferences — browser storage may be unavailable.",
          'error',
          8000,
        )
      }
    }
  }
}

function deriveCustomFromPreset(preset: ReadingPreset): CustomThemeSlot {
  const seed = themeMap[preset.theme] ?? themeMap.light
  return { name: 'Custom', ...seed }
}

export const useReaderSettingsStore = defineStore('readerSettings', () => {
  const presets = ref<ReadingPreset[]>([])
  const appliedPresetKey = ref<string | null>(loadAppliedKey())
  const currentSettings = ref<ReaderSettingsState>({ ...DEFAULT_SETTINGS })
  const loading = ref(false)
  const popoverOpen = ref(false)
  const editingCustom = ref(false)
  // FR-F4.7c: per-store-instance flag so the legacy hint is consumed at
  // most once per session, but a fresh Pinia (e.g. tests) gets a fresh flag.
  let _legacyHintConsumed = false

  const initialChrome = loadChrome()
  const highlightsVisible = ref(initialChrome.highlightsVisible)
  const annotationsScope = ref<AnnotationScope>(initialChrome.annotationsScope)
  const customTheme = ref<CustomThemeSlot | null>(loadCustom())
  const dirty = ref(false)
  const pendingCustom = ref<CustomThemeSlot | null>(null)

  watch(
    [highlightsVisible, annotationsScope],
    () => {
      persistChrome({
        highlightsVisible: highlightsVisible.value,
        annotationsScope: annotationsScope.value,
      })
    },
    { deep: true },
  )

  watch(popoverOpen, (open, wasOpen) => {
    if (open && !wasOpen) editingCustom.value = false
  })

  function toggleCustomEditor() {
    editingCustom.value = !editingCustom.value
  }

  function stageCustom(slot: CustomThemeSlot) {
    pendingCustom.value = slot
    dirty.value = true
  }

  function saveCustom() {
    if (!pendingCustom.value) return
    customTheme.value = pendingCustom.value
    persistCustom(customTheme.value)
    pendingCustom.value = null
    dirty.value = false
  }

  function discardCustom() {
    pendingCustom.value = null
    dirty.value = false
  }

  const cssVariables = computed(() => ({
    '--reader-font-family': currentSettings.value.font_family,
    '--reader-font-size': `${currentSettings.value.font_size_px}px`,
    '--reader-line-spacing': String(currentSettings.value.line_spacing),
    '--reader-content-width': `${currentSettings.value.content_width_px}px`,
    '--reader-theme': currentSettings.value.theme,
  }))

  watch(
    currentSettings,
    (settings) => {
      const root = document.documentElement
      root.style.setProperty('--reader-font-family', settings.font_family)
      root.style.setProperty('--reader-font-size', `${settings.font_size_px}px`)
      root.style.setProperty('--reader-line-spacing', String(settings.line_spacing))
      root.style.setProperty('--reader-content-width', `${settings.content_width_px}px`)
      root.dataset.theme = settings.theme
    },
    { deep: true },
  )

  function applySettingsFromPreset(preset: ReadingPreset) {
    currentSettings.value = {
      font_family: preset.font_family,
      font_size_px: preset.font_size_px,
      line_spacing: preset.line_spacing,
      content_width_px: preset.content_width_px,
      theme: preset.theme,
    }
  }

  /** FR-F4.6 / FR-F4.10: apply a system preset by id. No backend call.
   * Clears any pending custom edit + editingCustom flag. Non-existent ids
   * are a silent no-op (with console.warn). */
  function applyPreset(id: number) {
    const preset = presets.value.find((p) => p.id === id)
    if (!preset) {
      console.warn(`applyPreset(${id}): no preset with that id; ignoring.`)
      return
    }
    const key = `system:${id}`
    appliedPresetKey.value = key
    persistAppliedKey(key)
    applySettingsFromPreset(preset)
    pendingCustom.value = null
    dirty.value = false
    editingCustom.value = false
  }

  /** FR-F4.8 / FR-F4.8a: apply the Custom slot. If empty, seed it from
   * the active system preset. If we're already on `custom` but the slot
   * is empty (corrupted state), recover to Light → presets[0] → null. */
  function applyCustom() {
    if (!customTheme.value) {
      // Corrupted-state recovery (G7/G8 simulation finding).
      if (appliedPresetKey.value === 'custom') {
        const light = presets.value.find((p) => p.name === 'Light')
        const fallback = light ?? presets.value[0]
        if (fallback) {
          console.warn(
            `applyCustom(): empty slot but key=custom — falling back to ${fallback.name}.`,
          )
          applyPreset(fallback.id)
          return
        }
        console.warn('applyCustom(): empty slot, key=custom, no fallback presets.')
        appliedPresetKey.value = null
        persistAppliedKey(null)
        return
      }
      // Seed from the currently-applied system preset if any.
      const seedFrom =
        presets.value.find(
          (p) => `system:${p.id}` === appliedPresetKey.value,
        ) ??
        presets.value.find((p) => p.name === 'Light') ??
        presets.value[0]
      if (!seedFrom) {
        console.warn('applyCustom(): no presets to seed Custom slot from.')
        return
      }
      customTheme.value = deriveCustomFromPreset(seedFrom)
      persistCustom(customTheme.value)
    }
    appliedPresetKey.value = 'custom'
    persistAppliedKey('custom')
    // Apply Custom-slot colours into currentSettings (theme stays as a
    // marker; bg/fg/accent live in customTheme).
    if (customTheme.value) {
      currentSettings.value = {
        ...currentSettings.value,
        theme: 'custom',
      }
    }
  }

  /** FR-F4.7c: read the migration sidecar at most once per device. */
  async function consumeLegacyActiveHint() {
    if (appliedPresetKey.value !== null) return
    try {
      const resp = await fetch('/api/v1/reading-presets/legacy-active-hint')
      if (!resp.ok) return
      const body = (await resp.json()) as { name: string | null }
      if (!body?.name) return
      const match = presets.value.find((p) => p.name === body.name)
      if (match) {
        applyPreset(match.id)
      }
    } catch {
      // network failure — sidecar will be tried on next launch only if it
      // wasn't successfully consumed (the backend deletes on first 200).
    }
  }

  async function loadPresets() {
    loading.value = true
    try {
      const resp = await listPresets()
      presets.value = Array.isArray(resp?.items) ? resp.items : []

      // FR-F4.11: if the saved key references a system preset that no
      // longer exists, fall back to the first available system preset.
      // For `custom` and missing-slot, recovery is left to the next
      // explicit applyCustom() call (e.g. on first reader interaction).
      const key = appliedPresetKey.value
      if (key && key.startsWith('system:')) {
        const id = Number(key.slice('system:'.length))
        const stillExists = presets.value.some((p) => p.id === id)
        if (!stillExists) {
          const fallback = presets.value[0]
          if (fallback) applyPreset(fallback.id)
          else {
            appliedPresetKey.value = null
            persistAppliedKey(null)
          }
        } else {
          // Re-apply the settings so currentSettings reflects the live preset.
          const preset = presets.value.find((p) => p.id === id)
          if (preset) applySettingsFromPreset(preset)
        }
      }
    } catch {
      presets.value = []
    } finally {
      loading.value = false
    }

    // Auto-consume the legacy hint once per session, after the first
    // successful preset list load. FR-F4.7c.
    if (!_legacyHintConsumed) {
      _legacyHintConsumed = true
      await consumeLegacyActiveHint()
    }
  }

  function updateSetting<K extends keyof ReaderSettingsState>(
    key: K,
    value: ReaderSettingsState[K],
  ) {
    currentSettings.value[key] = value
  }

  async function detectSystemPreference() {
    if (appliedPresetKey.value !== null) return
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (prefersDark) {
      const darkPreset = presets.value.find(
        (p) => p.theme === 'dark' || p.name.toLowerCase().includes('night'),
      )
      if (darkPreset) {
        applyPreset(darkPreset.id)
      }
    }
  }

  return {
    presets,
    appliedPresetKey,
    currentSettings,
    loading,
    popoverOpen,
    editingCustom,
    cssVariables,
    loadPresets,
    applyPreset,
    applyCustom,
    toggleCustomEditor,
    consumeLegacyActiveHint,
    updateSetting,
    detectSystemPreference,
    // v1.5 reader chrome
    highlightsVisible,
    annotationsScope,
    customTheme,
    dirty,
    pendingCustom,
    stageCustom,
    saveCustom,
    discardCustom,
  }
})
