import { test, expect } from '@playwright/test'

test('search: command palette opens with Cmd+K', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  await page.keyboard.press('Meta+k')
  await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()
})

test('search: command palette closes with Escape', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  await page.keyboard.press('Meta+k')
  await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-testid="command-palette"]')).not.toBeVisible()
})
