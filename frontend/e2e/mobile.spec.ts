import { test, expect } from '@playwright/test'

// These tests run with mobile-chrome project (Pixel 5: 393x851px)

test('mobile: bottom tab bar is visible at small viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('[data-testid="bottom-tab-bar"]')).toBeVisible()
})

test('mobile: bottom tab bar has 5 tabs', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  const tabs = page.locator('[data-testid="bottom-tab-bar"] [data-testid="tab-item"]')
  await expect(tabs).toHaveCount(5)
})

test('mobile: icon rail is hidden at small viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('[data-testid="icon-rail-sidebar"]')).not.toBeVisible()
})

test('mobile: tab touch targets are at least 44px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  const tabs = page.locator('[data-testid="bottom-tab-bar"] [data-testid="tab-item"]')
  const count = await tabs.count()
  for (let i = 0; i < count; i++) {
    const box = await tabs.nth(i).boundingBox()
    expect(box!.height, `Tab ${i} must be >= 44px`).toBeGreaterThanOrEqual(44)
  }
})
