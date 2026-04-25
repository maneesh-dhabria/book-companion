import { apiClient } from './client'

export interface AppSettings {
  network: {
    host: string
    port: number
    allow_lan: boolean
    access_token: string | null
  }
  llm: {
    provider: string
    cli_command: string
    model: string
    timeout_seconds: number
    max_retries: number
    max_budget_usd: number
  }
  summarization: {
    default_preset: string
  }
  web: {
    show_cost_estimates: boolean
  }
}

export interface DatabaseStats {
  books: number
  book_sections: number
  summaries: number
  annotations: number
  concepts: number
  eval_traces: number
}

export interface MigrationStatus {
  current: string | null
  latest: string | null
  is_behind: boolean
}

export function getSettings() {
  return apiClient.get<AppSettings>('/settings')
}

export function updateSettings(updates: Partial<AppSettings>) {
  return apiClient.patch<AppSettings>('/settings', updates)
}

export function getDatabaseStats() {
  return apiClient.get<DatabaseStats>('/settings/database-stats')
}

export function getMigrationStatus() {
  return apiClient.get<MigrationStatus>('/settings/migration-status')
}

export function runMigrations() {
  return apiClient.post<{ status: string; output: string }>('/settings/run-migrations')
}
