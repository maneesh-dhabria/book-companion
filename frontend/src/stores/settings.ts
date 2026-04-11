import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AppSettings, DatabaseStats, MigrationStatus } from '@/api/settings'
import * as settingsApi from '@/api/settings'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSettings | null>(null)
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

  return {
    settings,
    dbStats,
    migrationStatus,
    loading,
    error,
    fetchSettings,
    saveSettings,
    fetchDatabaseStats,
    fetchMigrationStatus,
    triggerMigrations,
  }
})
