import { test, expect } from '@playwright/test'

test('LIB-01: library page loads and shows content', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  // Page should render without errors
  await expect(page.locator('body')).toBeVisible()
})

test('LIB-02: library grid shows book cards or empty state', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  const cards = page.locator('[data-testid="book-card"]')
  const emptyState = page.locator('[data-testid="empty-state-title"]')
  // Either books or empty state should be visible
  const hasCards = await cards.count() > 0
  const hasEmpty = await emptyState.isVisible().catch(() => false)
  expect(hasCards || hasEmpty).toBeTruthy()
})

test('LIB-03: navigation tabs are visible', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  // The navigation should be present (icon rail or bottom tab bar)
  const nav = page.locator('nav')
  await expect(nav.first()).toBeVisible()
})
