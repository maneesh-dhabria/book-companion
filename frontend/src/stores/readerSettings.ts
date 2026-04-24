import {
  activatePreset,
  createPreset,
  deletePreset as deletePresetApi,
  listPresets,
} from '@/api/readingPresets'
import type { ReadingPreset } from '@/types'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

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

// v1.5 — browser-local reader chrome: toggles and a single custom slot
// saved to localStorage. Not persisted server-side (see §11.3 decision).
const CHROME_LS_KEY = 'bookcompanion.reader-chrome.v1'
const CUSTOM_LS_KEY = 'bookcompanion.reader-custom.v1'

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
    /* quota / disabled storage — fall through silently */
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
    /* ignore */
  }
}

export const useReaderSettingsStore = defineStore('readerSettings', () => {
  const presets = ref<ReadingPreset[]>([])
  const activePreset = ref<ReadingPreset | null>(null)
  const currentSettings = ref<ReaderSettingsState>({ ...DEFAULT_SETTINGS })
  const loading = ref(false)
  const popoverOpen = ref(false)

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

  // Apply CSS variables to :root when settings change
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

  async function loadPresets() {
    loading.value = true
    try {
      const resp = await listPresets()
      // FR-F1.1 — defensive normalization: every consumer that runs
      // ``presets.filter(...)`` (PresetCards.vue, ReadingSettings.vue) must
      // survive an API that returns null/undefined/non-array `items`.
      presets.value = Array.isArray(resp?.items) ? resp.items : []
      const active =
        presets.value.find((p) => p.id === resp?.default_id) ??
        presets.value[0] ??
        null
      if (active) {
        activePreset.value = active
        applySettingsFromPreset(active)
      }
    } catch {
      // Use defaults if API unavailable; ensure presets stays as an array.
      presets.value = []
    } finally {
      loading.value = false
    }
  }

  function applySettingsFromPreset(preset: ReadingPreset) {
    currentSettings.value = {
      font_family: preset.font_family,
      font_size_px: preset.font_size_px,
      line_spacing: preset.line_spacing,
      content_width_px: preset.content_width_px,
      theme: preset.theme,
    }
  }

  async function applyPreset(id: number) {
    const preset = presets.value.find((p) => p.id === id)
    if (!preset) return
    activePreset.value = preset
    applySettingsFromPreset(preset)
    await activatePreset(id)
    // Refresh list to update is_active flags
    presets.value = (await listPresets()).items
  }

  function updateSetting<K extends keyof ReaderSettingsState>(key: K, value: ReaderSettingsState[K]) {
    currentSettings.value[key] = value
  }

  async function saveAsPreset(name: string) {
    const newPreset = await createPreset({
      name,
      ...currentSettings.value,
    })
    presets.value.push(newPreset)
    return newPreset
  }

  async function deleteUserPreset(id: number) {
    await deletePresetApi(id)
    presets.value = presets.value.filter((p) => p.id !== id)
    if (activePreset.value?.id === id) {
      // Re-fetch the list and pick the new default.
      const resp = await listPresets()
      presets.value = resp.items
      const active = resp.items.find((p) => p.id === resp.default_id) ?? resp.items[0]
      if (active) {
        activePreset.value = active
        applySettingsFromPreset(active)
      }
    }
  }

  async function detectSystemPreference() {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (prefersDark) {
      const darkPreset = presets.value.find(
        (p) => p.theme === 'dark' || p.name.toLowerCase().includes('night'),
      )
      if (darkPreset) {
        await applyPreset(darkPreset.id)
      }
    }
  }

  return {
    presets,
    activePreset,
    currentSettings,
    loading,
    popoverOpen,
    cssVariables,
    loadPresets,
    applyPreset,
    updateSetting,
    saveAsPreset,
    deletePreset: deleteUserPreset,
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
