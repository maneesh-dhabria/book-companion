import {
  activatePreset,
  createPreset,
  deletePreset as deletePresetApi,
  getActivePreset,
  listPresets,
  updatePreset,
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

export const useReaderSettingsStore = defineStore('readerSettings', () => {
  const presets = ref<ReadingPreset[]>([])
  const activePreset = ref<ReadingPreset | null>(null)
  const currentSettings = ref<ReaderSettingsState>({ ...DEFAULT_SETTINGS })
  const loading = ref(false)
  const popoverOpen = ref(false)

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
      presets.value = await listPresets()
      const active = await getActivePreset()
      activePreset.value = active
      applySettingsFromPreset(active)
    } catch {
      // Use defaults if API unavailable
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
    presets.value = await listPresets()
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
      // Re-fetch active (falls back to Comfortable)
      const active = await getActivePreset()
      activePreset.value = active
      applySettingsFromPreset(active)
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
  }
})
