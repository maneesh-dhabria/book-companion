import { apiClient } from './client'

export interface BackupItem {
  backup_id: string
  filename: string
  size_bytes: number
  size_mb: number
  created_at: string | null
}

export interface BackupCreateResponse {
  backup_id: string
  filename: string
  size_bytes: number
  created_at: string | null
}

export function createBackup() {
  return apiClient.post<BackupCreateResponse>('/backup/create')
}

export function listBackups() {
  return apiClient.get<BackupItem[]>('/backup/list')
}

export async function downloadBackup(backupId: string) {
  const response = await fetch(`/api/v1/backup/${backupId}/download`)
  if (!response.ok) throw new Error('Download failed')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${backupId}.sql`
  a.click()
  URL.revokeObjectURL(url)
}

export function deleteBackup(backupId: string) {
  return apiClient.delete(`/backup/${backupId}`)
}

export async function restoreBackup(file: File) {
  return apiClient.upload<{ status: string; filename: string }>('/backup/restore', file)
}
