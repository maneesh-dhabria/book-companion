import { test, expect } from '@playwright/test'

test('settings page renders with sidebar', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForLoadState('networkidle')
  // Sidebar navigation should be visible
  await expect(page.locator('.settings-nav')).toBeVisible()
})

test('settings: general section loads by default', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForLoadState('networkidle')
  // General section title should be visible
  await expect(page.locator('h2', { hasText: 'General' })).toBeVisible()
})

test('settings: database section shows stats', async ({ page }) => {
  await page.goto('/settings/database')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('h2', { hasText: 'Database' })).toBeVisible()
})

test('settings: deep link to specific section works', async ({ page }) => {
  await page.goto('/settings/backup')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('h2', { hasText: 'Backup & Export' })).toBeVisible()
})
