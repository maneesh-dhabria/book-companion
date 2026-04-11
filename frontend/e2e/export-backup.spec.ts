import { test, expect } from '@playwright/test'

test('backup: settings page shows backup section', async ({ page }) => {
  await page.goto('/settings/backup')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('h2', { hasText: 'Backup & Export' })).toBeVisible()
  await expect(page.locator('[data-testid="create-backup-btn"]')).toBeVisible()
})

test('export: settings page shows export controls', async ({ page }) => {
  await page.goto('/settings/backup')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('[data-testid="export-format-select"]')).toBeVisible()
  await expect(page.locator('[data-testid="export-library-btn"]')).toBeVisible()
})
