import { expect, test } from '@playwright/test'

/**
 * T37 / FR-E2 — Tag CRUD across book + section scopes.
 *
 * Exercises the new /api/v1/books/:id/tags + /api/v1/sections/:id/tags
 * endpoints through the UI: add a book tag from the overview page,
 * confirm it appears, navigate to the reader, add a section tag, and
 * remove one of each.
 */

const BOOK_ID = 1
const SECTION_ID = 3

test.describe('v1.5 tag CRUD UI', () => {
  test('add + remove book-scope tag on the overview page', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}`)
    // TagChipInput on the overview header.
    const input = page.locator('.book-tags .chip-field').first()
    await input.fill('strategy-e2e')
    await input.press('Enter')
    await expect(page.locator('.book-tags').getByText('strategy-e2e')).toBeVisible({
      timeout: 3000,
    })

    // Remove it.
    const chip = page.locator('.book-tags .tag-chip', { hasText: 'strategy-e2e' })
    await chip.locator('button.remove').click()
    await expect(page.locator('.book-tags').getByText('strategy-e2e')).not.toBeVisible()
  })

  test('add + remove section-scope tag in the reader', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_ID}`)
    const input = page.locator('.section-tag-row .chip-field').first()
    await input.fill('section-e2e')
    await input.press('Enter')
    await expect(
      page.locator('.section-tag-row').getByText('section-e2e'),
    ).toBeVisible({ timeout: 3000 })

    const chip = page.locator('.section-tag-row .tag-chip', { hasText: 'section-e2e' })
    await chip.locator('button.remove').click()
    await expect(
      page.locator('.section-tag-row').getByText('section-e2e'),
    ).not.toBeVisible()
  })
})
