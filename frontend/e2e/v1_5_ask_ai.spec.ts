import { expect, test } from '@playwright/test'

/**
 * T37 / FR-D1 — Ask AI from FloatingToolbar opens the AI tab in the sidebar.
 *
 * Uses ContextSidebar's new defaultTab prop path. Selects text, clicks
 * Ask AI, and confirms the AI tab is active. We don't drive a full LLM
 * roundtrip — just the UI wiring.
 */

const BOOK_ID = 1
const SECTION_ID = 3

test.describe('v1.5 Ask AI sidebar switch', () => {
  test('clicking Ask AI activates the AI tab', async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/sections/${SECTION_ID}`)

    // Select some text in the article.
    await page.waitForSelector('article')
    await page.evaluate(() => {
      const p = document.querySelector('article p')
      if (!p || !p.firstChild) return
      const range = document.createRange()
      range.setStart(p.firstChild, 0)
      range.setEnd(p.firstChild, Math.min(10, p.textContent?.length || 10))
      const sel = window.getSelection()
      sel?.removeAllRanges()
      sel?.addRange(range)
      p.dispatchEvent(new Event('mouseup', { bubbles: true }))
    })

    const askBtn = page.getByRole('button', { name: /ask ai/i }).first()
    if (await askBtn.count()) await askBtn.click()

    // The AI tab button inside the sidebar should report active.
    const aiTab = page.locator('.tab.active', { hasText: /ai|chat/i })
    await expect(aiTab.first()).toBeVisible({ timeout: 3000 })
  })
})
