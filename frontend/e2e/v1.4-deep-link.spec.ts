import { expect, test } from '@playwright/test'

/**
 * T14a — Deep-link reproducer (FR-B1.1, FR-B1.2).
 *
 * Triage outcome (code-study): the reader store's `loadBook` receives
 * `routeSectionId` via `loadFromRoute` in `BookDetailView.vue` and the
 * selection chain
 *   routeSectionId || savedSectionId || first summarizable || sections[0]
 * already gives route precedence (see `src/stores/reader.ts:44-66`). On a
 * cold tab the route-param parse + loadBook round-trip should land on the
 * requested section. If this spec FAILS against the current codebase,
 * T14b's triage-note captures the real fix site.
 *
 * The Porter book with id=1 / section 3 = "Introduction" is seeded in the
 * dev data directory from prior workflow fixtures. The backend must be
 * running on localhost:8000.
 */

const BOOK_ID = 1
const SECTION_ID = 3
const SECTION_TITLE = 'Introduction'

test.describe('Reader deep-link', () => {
  test('cold-tab deep-link renders the requested chapter', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_ID}`)
    await expect(page.locator('article').first()).toContainText(
      SECTION_TITLE,
      { timeout: 5000 },
    )
  })

  test('reload preserves the section under the deep-link URL', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_ID}`)
    await expect(page.locator('article').first()).toContainText(
      SECTION_TITLE,
      { timeout: 5000 },
    )
    await page.reload()
    await expect(page.locator('article').first()).toContainText(
      SECTION_TITLE,
      { timeout: 5000 },
    )
  })

  test('browser back preserves the originating section', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_ID}`)
    await expect(page.locator('article').first()).toContainText(SECTION_TITLE)
    // Navigate away (book summary view) and back — the deep-link section must
    // still be current when we pop.
    await page.goto(`/books/${BOOK_ID}/summary`)
    await page.goBack()
    await expect(page.locator('article').first()).toContainText(SECTION_TITLE)
  })
})
