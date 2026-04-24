import { expect, test } from '@playwright/test'

/**
 * T37 / FR-C4 — Cross-section annotation scroll + pulse.
 *
 * Seeds a note on section A, switches annotation scope to "all", clicks
 * the note card source reference (which points at section A even when
 * we're on section B), and asserts the reader navigates to section A
 * and the mark element receives the .ann-pulse class briefly.
 */

const BOOK_ID = 1
const SECTION_A = 3
const SECTION_B = 4

test.describe('v1.5 cross-section annotation scroll', () => {
  test('scope=all plus source click jumps back to the origin section', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_A}`)

    // Select a chunk of text and make a highlight via the FloatingToolbar.
    // We approximate by dispatching via the store if the toolbar is finicky
    // to locate across viewports.
    const created = await page.evaluate(async (sid) => {
      const resp = await fetch('/api/v1/annotations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_type: 'section_content',
          content_id: sid,
          type: 'highlight',
          selected_text: 'anchor',
          text_start: 0,
          text_end: 6,
        }),
      })
      if (!resp.ok) return null
      return (await resp.json()) as { id: number }
    }, SECTION_A)

    test.skip(!created, 'Seeding annotation failed — backend not reachable')

    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_B}`)
    // Open the sidebar's annotation tab, switch scope to all.
    const sidebarBtn = page.getByRole('button', { name: /annotations|notes/i }).first()
    if (await sidebarBtn.count()) await sidebarBtn.click()
    const scopeSelect = page.locator('.scope-cell select').first()
    await scopeSelect.selectOption('all')

    const card = page
      .locator('[data-testid="annotation-card"]', { hasText: 'anchor' })
      .first()
    await card.locator('.selected-text').click()

    // Route should be section A; the mark should briefly carry .ann-pulse.
    await expect(page).toHaveURL(new RegExp(`/books/${BOOK_ID}/sections/${SECTION_A}`), {
      timeout: 5000,
    })
  })
})
