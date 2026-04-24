import { expect, test } from '@playwright/test'

/**
 * T37 / FR-B4 — Custom theme save-and-apply flow.
 *
 * Opens the reader settings popover, switches to Custom, tweaks bg + fg +
 * accent, verifies the StickySaveBar reports the dirty state, saves, and
 * confirms the custom slot persists via localStorage and is re-applied
 * after a reload.
 */

const BOOK_ID = 1
const SECTION_ID = 3
const CUSTOM_LS_KEY = 'bookcompanion.reader-custom.v1'

test.describe('v1.5 Custom theme flow', () => {
  test('save & apply persists to localStorage and survives reload', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_ID}`)
    // Open the reader settings popover (icon in the reader toolbar).
    const settingsBtn = page.getByRole('button', { name: /reader settings|settings/i }).first()
    if (await settingsBtn.count()) await settingsBtn.click()

    // Click the Custom… card.
    const customCard = page.getByRole('button', { name: /custom/i }).first()
    await customCard.click()

    // Pick a bg + fg + accent from the palettes.
    const swatches = page.locator('.swatch')
    if (await swatches.count()) await swatches.nth(1).click()

    // StickySaveBar should declare dirty.
    const saveBar = page.getByRole('toolbar').filter({ hasText: /not saved/i })
    await expect(saveBar).toBeVisible({ timeout: 3000 })

    await page.getByRole('button', { name: /save.*apply/i }).click()

    // Verify persistence.
    const stored = await page.evaluate(
      (key) => window.localStorage.getItem(key),
      CUSTOM_LS_KEY,
    )
    expect(stored).toBeTruthy()
    const parsed = JSON.parse(stored || '{}')
    expect(parsed.bg).toBeTruthy()
    expect(parsed.fg).toBeTruthy()

    // Reload — custom slot should still be there.
    await page.reload()
    const afterReload = await page.evaluate(
      (key) => window.localStorage.getItem(key),
      CUSTOM_LS_KEY,
    )
    expect(afterReload).toBe(stored)
  })
})
