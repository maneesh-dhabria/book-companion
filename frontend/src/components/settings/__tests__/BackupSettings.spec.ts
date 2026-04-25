import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import BackupSettings from '../BackupSettings.vue'
import * as backupApi from '@/api/backup'
import { useUiStore } from '@/stores/ui'

describe('BackupSettings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(backupApi, 'listBackups').mockResolvedValue([])
  })

  it('fires success toast on backup creation', async () => {
    vi.spyOn(backupApi, 'createBackup').mockResolvedValue({ backup_id: 'b1' } as never)
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    const w = mount(BackupSettings)
    await w.find('[data-testid="create-backup-btn"]').trigger('click')
    await flushPromises()
    expect(toastSpy).toHaveBeenCalledWith('Backup created', 'success')
  })

  it('fires error toast when backup fails', async () => {
    vi.spyOn(backupApi, 'createBackup').mockRejectedValue(new Error('disk full'))
    const ui = useUiStore()
    const toastSpy = vi.spyOn(ui, 'showToast')
    const w = mount(BackupSettings)
    await w.find('[data-testid="create-backup-btn"]').trigger('click')
    await flushPromises()
    const calls = toastSpy.mock.calls.filter(([, type]) => type === 'error')
    expect(calls.length).toBeGreaterThan(0)
    expect(String(calls[0][0])).toContain('disk full')
  })

  it('does not render any inline .toast div', () => {
    const w = mount(BackupSettings)
    expect(w.find('div.toast').exists()).toBe(false)
  })

  // FR-F11 cleanup: dropdown removed; single JSON button
  it('does not render a format selector dropdown', () => {
    const w = mount(BackupSettings)
    expect(w.find('[data-testid="export-format-select"]').exists()).toBe(false)
  })

  it('renders a single button labeled "Export library (JSON)"', () => {
    const w = mount(BackupSettings)
    const btn = w.find('[data-testid="export-library-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toMatch(/Export library \(JSON\)/)
  })
})
