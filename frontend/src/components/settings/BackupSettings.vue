<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as backupApi from '@/api/backup'
import * as exportApi from '@/api/export'
import type { BackupItem } from '@/api/backup'
import { useUiStore } from '@/stores/ui'

const backups = ref<BackupItem[]>([])
const creating = ref(false)
const exporting = ref(false)

onMounted(loadBackups)

function errorText(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback
}

async function loadBackups() {
  try {
    backups.value = await backupApi.listBackups()
  } catch {
    // Backup service may not be available
  }
}

async function handleCreateBackup() {
  creating.value = true
  const ui = useUiStore()
  try {
    await backupApi.createBackup()
    ui.showToast('Backup created', 'success')
    await loadBackups()
  } catch (e: unknown) {
    ui.showToast(`Backup failed: ${errorText(e, 'unknown error')}`, 'error')
  } finally {
    creating.value = false
  }
}

async function handleDownload(backupId: string) {
  try {
    await backupApi.downloadBackup(backupId)
  } catch (e: unknown) {
    useUiStore().showToast(`Download failed: ${errorText(e, 'unknown error')}`, 'error')
  }
}

async function handleDelete(backupId: string) {
  if (!confirm('This backup will be permanently deleted. Continue?')) return
  try {
    await backupApi.deleteBackup(backupId)
    await loadBackups()
  } catch (e: unknown) {
    useUiStore().showToast(`Delete failed: ${errorText(e, 'unknown error')}`, 'error')
  }
}

async function handleExportLibrary() {
  exporting.value = true
  try {
    await exportApi.exportLibrary({ format: 'json' })
  } catch (e: unknown) {
    useUiStore().showToast(`Export failed: ${errorText(e, 'unknown error')}`, 'error')
  } finally {
    exporting.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}
</script>

<template>
  <div class="backup-settings">
    <h2 class="section-title">Backup & Export</h2>

    <!-- Create Backup -->
    <div class="setting-group">
      <h3 class="group-title">Database Backup</h3>
      <p class="group-description">Create a full database backup (pg_dump SQL format).</p>
      <button
        class="btn-primary"
        :disabled="creating"
        data-testid="create-backup-btn"
        @click="handleCreateBackup"
      >
        {{ creating ? 'Creating...' : 'Create Backup' }}
      </button>
    </div>

    <!-- Backup History -->
    <div class="setting-group">
      <h3 class="group-title">Backup History</h3>
      <div v-if="backups.length > 0" class="backup-table">
        <div
          v-for="b in backups"
          :key="b.backup_id"
          class="backup-row"
          data-testid="backup-history-row"
        >
          <div class="backup-info">
            <span class="backup-name">{{ b.filename }}</span>
            <span class="backup-meta">
              <span data-testid="backup-size">{{ formatSize(b.size_bytes) }}</span>
              <span v-if="b.created_at"> &middot; {{ b.created_at }}</span>
            </span>
          </div>
          <div class="backup-actions">
            <button class="btn-sm" data-testid="download-backup-btn" @click="handleDownload(b.backup_id)">Download</button>
            <button class="btn-sm btn-danger" data-testid="delete-backup-btn" @click="handleDelete(b.backup_id)">Delete</button>
          </div>
        </div>
      </div>
      <p v-else class="empty-text">No backups yet.</p>
    </div>

    <!-- Export Library -->
    <div class="setting-group">
      <h3 class="group-title">Export Library</h3>
      <p class="group-description">Export your entire library as JSON.</p>
      <div class="export-controls">
        <button
          class="btn-primary"
          :disabled="exporting"
          data-testid="export-library-btn"
          @click="handleExportLibrary"
        >
          {{ exporting ? 'Exporting...' : 'Export library (JSON)' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 1.5rem; }
.setting-group { margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--color-border, #e5e7eb); }
.group-title { font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted, #888); margin-bottom: 0.5rem; }
.group-description { font-size: 0.8125rem; color: var(--color-text-muted, #888); margin-bottom: 0.75rem; }

.backup-table { display: flex; flex-direction: column; gap: 0.5rem; }
.backup-row { display: flex; align-items: center; justify-content: space-between; padding: 0.75rem; background: var(--color-bg-muted, #f9fafb); border-radius: 0.375rem; }
.backup-info { display: flex; flex-direction: column; gap: 0.125rem; }
.backup-name { font-size: 0.8125rem; font-family: monospace; }
.backup-meta { font-size: 0.75rem; color: var(--color-text-muted, #888); }
.backup-actions { display: flex; gap: 0.5rem; }

.export-controls { display: flex; gap: 0.75rem; align-items: center; }
.select-input { padding: 0.5rem 0.75rem; border: 1px solid var(--color-border, #d1d5db); border-radius: 0.375rem; font-size: 0.875rem; }
.empty-text { font-size: 0.875rem; color: var(--color-text-muted, #888); }

.btn-primary { padding: 0.5rem 1rem; background: var(--color-accent, #2563eb); color: white; border: none; border-radius: 0.375rem; font-size: 0.875rem; font-weight: 500; cursor: pointer; }
.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm { padding: 0.25rem 0.625rem; border: 1px solid var(--color-border, #d1d5db); border-radius: 0.25rem; font-size: 0.75rem; background: white; cursor: pointer; }
.btn-sm:hover { background: var(--color-bg-muted, #f3f4f6); }
.btn-danger { color: #dc2626; border-color: #fca5a5; }
.btn-danger:hover { background: #fef2f2; }
</style>
