import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AppSettings, DatabaseStats, MigrationStatus } from '@/api/settings'
import * as settingsApi from '@/api/settings'

/**
 * TTS playback settings (FR-18 / plan T5).
 *
 * Fetched separately from /api/v1/settings/tts; consumed by useTtsEngine
 * to honor the user's saved Web Speech voice + rate.
 */
export interface TtsSettings {
  engine: 'web-speech' | 'kokoro'
  voice: string | null
  default_speed: number
  auto_advance: boolean
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSettings | null>(null)
  const tts = ref<TtsSettings | null>(null)
  const dbStats = ref<DatabaseStats | null>(null)
  const migrationStatus = ref<MigrationStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSettings() {
    loading.value = true
    error.value = null
    try {
      settings.value = await settingsApi.getSettings()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load settings'
    } finally {
      loading.value = false
    }
  }

  async function saveSettings(updates: Partial<AppSettings>) {
    error.value = null
    try {
      settings.value = await settingsApi.updateSettings(updates)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to save settings'
      throw e
    }
  }

  async function fetchDatabaseStats() {
    try {
      dbStats.value = await settingsApi.getDatabaseStats()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load database stats'
    }
  }

  async function fetchMigrationStatus() {
    try {
      migrationStatus.value = await settingsApi.getMigrationStatus()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load migration status'
    }
  }

  async function triggerMigrations() {
    try {
      await settingsApi.runMigrations()
      await fetchMigrationStatus()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Migration failed'
    }
  }

  async function fetchTtsSettings() {
    try {
      const r = await fetch('/api/v1/settings/tts')
      if (!r.ok) return
      const j = (await r.json()) as TtsSettings
      tts.value = {
        engine: j.engine ?? 'web-speech',
        voice: j.voice ?? null,
        default_speed: j.default_speed ?? 1.0,
        auto_advance: j.auto_advance ?? true,
      }
    } catch {
      /* silent — useTtsEngine falls back to defaults */
    }
  }

  return {
    settings,
    tts,
    dbStats,
    migrationStatus,
    loading,
    error,
    fetchSettings,
    saveSettings,
    fetchDatabaseStats,
    fetchMigrationStatus,
    triggerMigrations,
    fetchTtsSettings,
  }
})
